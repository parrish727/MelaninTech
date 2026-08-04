#!/usr/bin/env python3
"""
Migrate pgvector data → Qdrant.

Sources:
  - task_memory (60 rows) — from PostgreSQL pgvector table
  - conversation_memory (134 rows) — from PostgreSQL pgvector table
  - graph_nodes (257 nodes) — from graphify-out/graph.json (no pgvector embeddings)
  - context_summaries (4 rows) — from darius_context_summaries pgvector table

Target: Qdrant collections via integrations/qdrant_client.SemanticLayer.

Idempotent: Qdrant upserts by deterministic UUID, safe to re-run.
Graph nodes are embedded on-the-fly via Ollama nomic-embed-text.

Usage:
    python scripts/migrate_pgvector_to_qdrant.py [--dry-run] [--batch-size 32]

Env vars required:
    POSTGRES_DSN — PostgreSQL connection string
    QDRANT_URL — Qdrant API endpoint (default: http://qdrant:6333)
    OLLAMA_URL — Ollama API endpoint (default: http://ollama:11434)
"""
import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from psycopg2.extras import RealDictCursor
from integrations.qdrant_client import SemanticLayer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("migrate_pgvector_to_qdrant")

GRAPHIFY_PATH = Path(__file__).resolve().parent.parent / "graphify-out" / "graph.json"


def get_pg_conn():
    """Connect to PostgreSQL."""
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        logger.error("POSTGRES_DSN env var required")
        sys.exit(1)
    conn = psycopg2.connect(dsn)
    return conn


def migrate_task_memory(sl: SemanticLayer, conn, dry_run: bool, batch_size: int) -> int:
    """Migrate task_memory rows from pgvector to Qdrant."""
    logger.info("─── Migrating task_memory ───")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, task, proposal, agent, decision, created_at
            FROM task_memory
            ORDER BY id
        """)
        rows = cur.fetchall()

    logger.info(f"  Found {len(rows)} rows in task_memory")

    if dry_run:
        logger.info("  [DRY RUN] Would upsert {len(rows)} points to task_memory collection")
        return len(rows)

    # Build batch points
    points = []
    for row in rows:
        text = f"{row['task']} | {row['proposal'] or ''} | {row['decision'] or ''}"
        points.append({
            "id": f"task_memory_{row['id']}",
            "text": text.strip(),
            "metadata": {
                "task": row["task"] or "",
                "proposal": row["proposal"] or "",
                "agent": row["agent"] or "",
                "decision": row["decision"] or "",
                "created_at": str(row["created_at"]) if row.get("created_at") else "",
                "source": "pgvector_migration",
            },
        })

    # Upsert in batches
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        sl.upsert_batch("task_memory", batch)
        logger.info(f"  Upserted batch {i // batch_size + 1} ({len(batch)} points)")
        time.sleep(0.5)  # Rate limit Ollama embeddings

    logger.info(f"  ✓ task_memory: {len(points)} points migrated")
    return len(points)


def migrate_conversation_memory(sl: SemanticLayer, conn, dry_run: bool, batch_size: int) -> int:
    """Migrate conversation_memory rows from pgvector to Qdrant."""
    logger.info("─── Migrating conversation_memory ───")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, role, content, created_at
            FROM conversation_memory
            ORDER BY id
        """)
        rows = cur.fetchall()

    logger.info(f"  Found {len(rows)} rows in conversation_memory")

    if dry_run:
        logger.info(f"  [DRY RUN] Would upsert {len(rows)} points to conversation_memory collection")
        return len(rows)

    points = []
    for row in rows:
        text = row["content"] or ""
        if not text.strip():
            continue  # Skip empty content

        points.append({
            "id": f"conversation_memory_{row['id']}",
            "text": text,
            "metadata": {
                "role": row["role"] or "",
                "content": text[:5000],
                "created_at": str(row["created_at"]) if row.get("created_at") else "",
                "source": "pgvector_migration",
            },
        })

    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        sl.upsert_batch("conversation_memory", batch)
        logger.info(f"  Upserted batch {i // batch_size + 1} ({len(batch)} points)")
        time.sleep(0.5)

    logger.info(f"  ✓ conversation_memory: {len(points)} points migrated")
    return len(points)


def migrate_graph_nodes(sl: SemanticLayer, dry_run: bool, batch_size: int) -> int:
    """
    Migrate graph nodes from graphify-out/graph.json → Qdrant graph_nodes collection.
    These are NOT in pgvector — they come from graphify's JSON export.
    Embeddings are generated on-the-fly via Ollama.
    """
    logger.info("─── Migrating graph_nodes ───")

    if not GRAPHIFY_PATH.exists():
        logger.warning(f"  Graphify output not found at {GRAPHIFY_PATH} — skipping")
        return 0

    with open(GRAPHIFY_PATH) as f:
        graph_data = json.load(f)

    nodes = graph_data.get("nodes", [])
    logger.info(f"  Found {len(nodes)} nodes in graph.json")

    if dry_run:
        logger.info(f"  [DRY RUN] Would upsert {len(nodes)} points to graph_nodes collection")
        return len(nodes)

    points = []
    for node in nodes:
        # Build searchable text from node fields
        label = node.get("label", "")
        community_name = node.get("community_name", "")
        source_file = node.get("source_file", "")
        file_type = node.get("file_type", "")
        node_id = node.get("id", "")

        # Compose text for embedding — label + community for semantic richness
        text = f"{label} ({community_name})"
        if source_file:
            text += f" — {source_file}"

        if not text.strip():
            continue

        points.append({
            "id": f"graph_node_{node_id}" if node_id else f"graph_node_{label}",
            "text": text,
            "metadata": {
                "label": label,
                "content": text,
                "file_type": file_type,
                "community_name": community_name,
                "source_file": source_file,
                "source": "graphify_migration",
            },
        })

    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        sl.upsert_batch("graph_nodes", batch)
        logger.info(f"  Upserted batch {i // batch_size + 1} ({len(batch)} points)")
        time.sleep(1.0)  # Longer pause — 257 embeddings is heavy on CPU

    logger.info(f"  ✓ graph_nodes: {len(points)} points migrated")
    return len(points)


def migrate_context_summaries(sl: SemanticLayer, conn, dry_run: bool, batch_size: int) -> int:
    """Migrate darius_context_summaries from pgvector to Qdrant."""
    logger.info("─── Migrating context_summaries ───")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id, session_id, summary, turn_start, turn_end, created_at
            FROM darius_context_summaries
            ORDER BY id
        """)
        rows = cur.fetchall()

    logger.info(f"  Found {len(rows)} rows in darius_context_summaries")

    if dry_run:
        logger.info(f"  [DRY RUN] Would upsert {len(rows)} points to context_summaries collection")
        return len(rows)

    points = []
    for row in rows:
        text = row["summary"] or ""
        if not text.strip():
            continue

        points.append({
            "id": f"context_summary_{row['id']}",
            "text": text,
            "metadata": {
                "session_id": row["session_id"] or "",
                "summary": text[:5000],
                "turn_start": row["turn_start"],
                "turn_end": row["turn_end"],
                "created_at": str(row["created_at"]) if row.get("created_at") else "",
                "source": "pgvector_migration",
            },
        })

    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        sl.upsert_batch("context_summaries", batch)
        logger.info(f"  Upserted batch {i // batch_size + 1} ({len(batch)} points)")
        time.sleep(0.5)

    logger.info(f"  ✓ context_summaries: {len(points)} points migrated")
    return len(points)


def main():
    parser = argparse.ArgumentParser(description="Migrate pgvector data to Qdrant")
    parser.add_argument("--dry-run", action="store_true", help="Preview counts without migrating")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for Qdrant upserts (default: 32)")
    parser.add_argument("--collection", type=str, default=None,
                        choices=["task_memory", "conversation_memory", "graph_nodes", "context_summaries"],
                        help="Migrate only a specific collection")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("pgvector → Qdrant Migration")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("MODE: DRY RUN (no writes)")
    else:
        logger.info("MODE: LIVE MIGRATION")

    # Initialize SemanticLayer and ensure collections exist
    sl = SemanticLayer()

    if not sl.health():
        logger.error("Qdrant is not reachable — check QDRANT_URL")
        sys.exit(1)

    logger.info("Qdrant health: OK")

    if not args.dry_run:
        sl.ensure_collections()
        logger.info("All collections ensured")

    # Connect to PostgreSQL (needed for all except graph_nodes)
    conn = None
    if args.collection != "graph_nodes":
        conn = get_pg_conn()
        logger.info("PostgreSQL connected")

    # Run migrations
    totals = {}
    start_time = time.time()

    if args.collection is None or args.collection == "task_memory":
        totals["task_memory"] = migrate_task_memory(sl, conn, args.dry_run, args.batch_size)

    if args.collection is None or args.collection == "conversation_memory":
        totals["conversation_memory"] = migrate_conversation_memory(sl, conn, args.dry_run, args.batch_size)

    if args.collection is None or args.collection == "graph_nodes":
        totals["graph_nodes"] = migrate_graph_nodes(sl, args.dry_run, args.batch_size)

    if args.collection is None or args.collection == "context_summaries":
        totals["context_summaries"] = migrate_context_summaries(sl, conn, args.dry_run, args.batch_size)

    elapsed = time.time() - start_time

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 60)
    total_points = 0
    for collection, count in totals.items():
        logger.info(f"  {collection}: {count} points")
        total_points += count
    logger.info(f"  ────────────────────────────")
    logger.info(f"  TOTAL: {total_points} points")
    logger.info(f"  Time: {elapsed:.1f}s")
    logger.info(f"  Status: {'DRY RUN' if args.dry_run else 'COMPLETE'}")
    logger.info("=" * 60)

    if conn:
        conn.close()


if __name__ == "__main__":
    main()
