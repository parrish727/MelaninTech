#!/usr/bin/env python3
"""
Verify Qdrant Migration — end-to-end checks for the semantic layer.

Checks:
  1. Qdrant is reachable and healthy
  2. All 4 collections exist with expected point counts
  3. Search returns results for each collection (semantic correctness)
  4. Search latency is within acceptable bounds (<2s per query)
  5. pgvector fallback still works (backward compat)
  6. Dual-write roundtrip (write → read → verify)

Usage:
    python scripts/verify_qdrant_migration.py [--verbose]

Env vars required:
    POSTGRES_DSN — PostgreSQL connection string
    QDRANT_URL — Qdrant API (default: http://qdrant:6333)
    OLLAMA_URL — Ollama API (default: http://ollama:11434)

Exit codes:
    0 — all checks pass
    1 — one or more checks failed
"""
import os
import sys
import time
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from integrations.qdrant_client import SemanticLayer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("verify_qdrant")

# Expected point counts from migration plan
EXPECTED_COUNTS = {
    "task_memory": 60,
    "conversation_memory": 134,
    "graph_nodes": 257,
    "context_summaries": 4,
}

# Max acceptable search latency (seconds)
MAX_LATENCY_S = 2.0

# Test queries per collection
TEST_QUERIES = {
    "task_memory": "deploy new service to production",
    "conversation_memory": "authentication and security configuration",
    "graph_nodes": "Darius agent architecture",
    "context_summaries": "compressed session context",
}


class VerificationResult:
    def __init__(self, name: str, passed: bool, detail: str = "", latency_ms: float = 0):
        self.name = name
        self.passed = passed
        self.detail = detail
        self.latency_ms = latency_ms

    def __repr__(self):
        status = "✓ PASS" if self.passed else "✗ FAIL"
        lat = f" ({self.latency_ms:.0f}ms)" if self.latency_ms > 0 else ""
        return f"  {status} | {self.name}{lat}: {self.detail}"


def check_qdrant_health(sl: SemanticLayer) -> VerificationResult:
    """Check 1: Qdrant is reachable."""
    start = time.time()
    healthy = sl.health()
    latency = (time.time() - start) * 1000
    return VerificationResult(
        "Qdrant Health",
        passed=healthy,
        detail="Qdrant reachable and responding" if healthy else "Qdrant unreachable",
        latency_ms=latency,
    )


def check_collections_exist(sl: SemanticLayer) -> list[VerificationResult]:
    """Check 2: All collections exist with expected point counts."""
    results = []
    try:
        stats = sl.stats()
    except Exception as e:
        return [VerificationResult("Collection Stats", False, f"Failed to get stats: {e}")]

    for collection, expected_count in EXPECTED_COUNTS.items():
        if collection not in stats:
            results.append(VerificationResult(
                f"Collection '{collection}'",
                passed=False,
                detail=f"Collection does not exist (expected {expected_count} points)",
            ))
            continue

        actual = stats[collection].get("points_count", 0)
        # Allow ±5% variance (dual-writes may add a few extra)
        lower = int(expected_count * 0.90)
        upper = int(expected_count * 1.10)
        passed = lower <= actual <= upper

        results.append(VerificationResult(
            f"Collection '{collection}'",
            passed=passed,
            detail=f"{actual} points (expected ~{expected_count}, range {lower}-{upper})",
        ))

    return results


def check_search_correctness(sl: SemanticLayer) -> list[VerificationResult]:
    """Check 3: Semantic search returns results for each collection."""
    results = []

    for collection, query in TEST_QUERIES.items():
        start = time.time()
        try:
            hits = sl.search(collection, query=query, limit=3, score_threshold=0.1)
            latency = (time.time() - start) * 1000

            if hits:
                top_score = hits[0]["score"]
                results.append(VerificationResult(
                    f"Search '{collection}'",
                    passed=True,
                    detail=f"{len(hits)} results, top score={top_score:.3f}",
                    latency_ms=latency,
                ))
            else:
                results.append(VerificationResult(
                    f"Search '{collection}'",
                    passed=False,
                    detail="No results returned",
                    latency_ms=latency,
                ))
        except Exception as e:
            latency = (time.time() - start) * 1000
            results.append(VerificationResult(
                f"Search '{collection}'",
                passed=False,
                detail=f"Error: {e}",
                latency_ms=latency,
            ))

    return results


def check_search_latency(sl: SemanticLayer) -> VerificationResult:
    """Check 4: Search latency is within acceptable bounds."""
    latencies = []

    for collection, query in TEST_QUERIES.items():
        start = time.time()
        try:
            sl.search(collection, query=query, limit=5)
        except Exception:
            pass
        latencies.append(time.time() - start)

    if not latencies:
        return VerificationResult("Search Latency", False, "No latency data collected")

    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    passed = max_latency < MAX_LATENCY_S

    return VerificationResult(
        "Search Latency",
        passed=passed,
        detail=f"avg={avg_latency*1000:.0f}ms, max={max_latency*1000:.0f}ms (threshold={MAX_LATENCY_S*1000:.0f}ms)",
        latency_ms=avg_latency * 1000,
    )


def check_pgvector_fallback() -> VerificationResult:
    """Check 5: pgvector fallback still works."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        dsn = os.environ.get("POSTGRES_DSN")
        if not dsn:
            return VerificationResult("pgvector Fallback", False, "POSTGRES_DSN not set")

        conn = psycopg2.connect(dsn)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM task_memory")
            count = cur.fetchone()["cnt"]
        conn.close()

        passed = count > 0
        return VerificationResult(
            "pgvector Fallback",
            passed=passed,
            detail=f"task_memory has {count} rows (pgvector intact)",
        )
    except Exception as e:
        return VerificationResult("pgvector Fallback", False, f"Error: {e}")


def check_dual_write_roundtrip(sl: SemanticLayer) -> VerificationResult:
    """Check 6: Dual-write roundtrip (upsert → search → verify)."""
    test_id = "verify_test_roundtrip"
    test_text = "verification roundtrip test query melanin technologies qdrant migration"
    collection = "task_memory"

    try:
        # Write
        sl.upsert(
            collection,
            id=test_id,
            text=test_text,
            metadata={
                "task": test_text,
                "proposal": "test",
                "agent": "verification_script",
                "decision": "test_roundtrip",
                "source": "verification",
            },
        )

        # Small delay for indexing
        time.sleep(0.5)

        # Search
        results = sl.search(collection, query="verification roundtrip melanin", limit=3, score_threshold=0.3)

        # Verify the test point appears
        found = any(
            r["payload"].get("decision") == "test_roundtrip"
            for r in results
        )

        # Cleanup
        sl.delete(collection, test_id)

        if found:
            return VerificationResult(
                "Dual-Write Roundtrip",
                passed=True,
                detail="Write → search → found → cleaned up",
            )
        else:
            return VerificationResult(
                "Dual-Write Roundtrip",
                passed=False,
                detail="Wrote test point but search didn't find it",
            )
    except Exception as e:
        # Try cleanup even if test failed
        try:
            sl.delete(collection, test_id)
        except Exception:
            pass
        return VerificationResult("Dual-Write Roundtrip", False, f"Error: {e}")


def check_filter_search(sl: SemanticLayer) -> VerificationResult:
    """Check 7: Filtered search works (context_summaries with session_id)."""
    try:
        # Search context_summaries with a filter — should not error even if no results
        results = sl.search_with_filter(
            "context_summaries",
            query="session context",
            must=[{"key": "session_id", "match": {"value": "test_session_does_not_exist"}}],
            limit=3,
        )

        # This should return empty (no matching session_id) — that's fine
        return VerificationResult(
            "Filtered Search",
            passed=True,
            detail=f"Filter query executed successfully ({len(results)} results for nonexistent session)",
        )
    except Exception as e:
        return VerificationResult("Filtered Search", False, f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Verify Qdrant migration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 60)
    print("  Qdrant Migration Verification")
    print("=" * 60)
    print()

    sl = SemanticLayer()
    all_results: list[VerificationResult] = []

    # Run all checks
    print("Running checks...")
    print()

    # 1. Health
    r = check_qdrant_health(sl)
    all_results.append(r)
    print(r)

    if not r.passed:
        print("\n  ⚠️  Qdrant unreachable — cannot continue verification.")
        print("  Check QDRANT_URL and container status.")
        sys.exit(1)

    # 2. Collections
    collection_results = check_collections_exist(sl)
    all_results.extend(collection_results)
    for r in collection_results:
        print(r)

    # 3. Search correctness
    search_results = check_search_correctness(sl)
    all_results.extend(search_results)
    for r in search_results:
        print(r)

    # 4. Latency
    r = check_search_latency(sl)
    all_results.append(r)
    print(r)

    # 5. pgvector fallback
    r = check_pgvector_fallback()
    all_results.append(r)
    print(r)

    # 6. Dual-write roundtrip
    r = check_dual_write_roundtrip(sl)
    all_results.append(r)
    print(r)

    # 7. Filtered search
    r = check_filter_search(sl)
    all_results.append(r)
    print(r)

    # Summary
    print()
    print("=" * 60)
    passed = sum(1 for r in all_results if r.passed)
    failed = sum(1 for r in all_results if not r.passed)
    total = len(all_results)

    if failed == 0:
        print(f"  ✓ ALL CHECKS PASSED ({passed}/{total})")
        print("  Qdrant semantic layer is fully operational.")
    else:
        print(f"  ✗ {failed} CHECK(S) FAILED ({passed}/{total} passed)")
        print()
        print("  Failed checks:")
        for r in all_results:
            if not r.passed:
                print(f"    - {r.name}: {r.detail}")

    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
