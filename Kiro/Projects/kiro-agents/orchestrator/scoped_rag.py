"""
Scoped RAG — per-project/workflow vector namespaces.

Each project and workflow gets its own isolated memory space in pgvector.
Agents retrieve only relevant context from their scope, not the global pool.

Namespaces:
  - project:<name>  (e.g. project:melanin-tech-website, project:orthoflow)
  - workflow:<name> (e.g. workflow:seo-improve, workflow:build-feature)
  - global          (cross-project memory, used as fallback)

Table: scoped_memory (extends existing task_memory pattern)
"""
import os
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("scoped_rag")

_DSN = os.environ.get("POSTGRES_DSN", "")
_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
_conn = None


def _get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(_DSN)
    if _conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
        try:
            _conn.rollback()
        except Exception:
            _conn = psycopg2.connect(_DSN)
    with _conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scoped_memory (
                id SERIAL PRIMARY KEY,
                namespace TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB,
                embedding vector(768),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scoped_ns ON scoped_memory(namespace)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scoped_created ON scoped_memory(created_at)")
        _conn.commit()
    return _conn


def _embed(text: str) -> list[float]:
    """Generate embedding via Ollama nomic-embed-text."""
    import httpx
    response = httpx.post(
        f"{_OLLAMA_URL}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["embedding"]


# ── Store ─────────────────────────────────────────────────────────────────────

def store(namespace: str, content: str, metadata: dict = None):
    """
    Store content in a scoped namespace with embedding.

    Args:
        namespace: e.g. "project:melanin-tech-website" or "workflow:seo-improve"
        content: Text content to store and embed
        metadata: Optional dict (task type, agent, status, etc.)
    """
    conn = _get_conn()
    embedding = _embed(content)
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO scoped_memory (namespace, content, metadata, embedding)
               VALUES (%s, %s, %s, %s)""",
            (namespace, content, json.dumps(metadata) if metadata else None, embedding),
        )
    conn.commit()


def store_workflow_run(workflow_name: str, task: str, result: str, approved: bool, agent: str = None):
    """Convenience: store a workflow run in the workflow's namespace."""
    store(
        namespace=f"workflow:{workflow_name}",
        content=f"Task: {task}\nResult: {result[:2000]}",
        metadata={"approved": approved, "agent": agent, "type": "workflow_run"},
    )


def store_project_context(project: str, content: str, context_type: str = "general"):
    """Convenience: store project-specific context."""
    store(
        namespace=f"project:{project}",
        content=content,
        metadata={"type": context_type},
    )


# ── Recall ────────────────────────────────────────────────────────────────────

def recall(query: str, namespace: str = None, limit: int = 5, approved_only: bool = False) -> list[dict]:
    """
    Recall relevant context from a namespace (or global).

    Args:
        query: Search query
        namespace: Scope to search in (None = search all)
        limit: Max results
        approved_only: Only return entries where metadata.approved is true

    Returns:
        List of dicts with: content, metadata, similarity_score
    """
    conn = _get_conn()
    embedding = _embed(query)

    query_sql = """
        SELECT content, metadata, (embedding <-> %s::vector) as distance
        FROM scoped_memory
        WHERE 1=1
    """
    params = [embedding]

    if namespace:
        query_sql += " AND namespace = %s"
        params.append(namespace)

    if approved_only:
        query_sql += " AND (metadata->>'approved')::boolean = true"

    query_sql += " ORDER BY embedding <-> %s::vector LIMIT %s"
    params.extend([embedding, limit])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query_sql, params)
        results = []
        for row in cur.fetchall():
            entry = {
                "content": row["content"],
                "metadata": row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}"),
                "distance": float(row["distance"]),
            }
            results.append(entry)

    return results


def recall_for_workflow(workflow_name: str, query: str, limit: int = 5) -> list[dict]:
    """Recall context scoped to a specific workflow."""
    return recall(query, namespace=f"workflow:{workflow_name}", limit=limit)


def recall_for_project(project: str, query: str, limit: int = 5) -> list[dict]:
    """Recall context scoped to a specific project."""
    return recall(query, namespace=f"project:{project}", limit=limit)


def recall_global(query: str, limit: int = 5) -> list[dict]:
    """Recall from all namespaces (cross-project)."""
    return recall(query, namespace=None, limit=limit)


# ── Namespace Management ──────────────────────────────────────────────────────

def list_namespaces() -> list[dict]:
    """List all namespaces with their entry counts."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT namespace, COUNT(*) as entries,
                   MAX(created_at) as last_updated
            FROM scoped_memory
            GROUP BY namespace
            ORDER BY namespace
        """)
        return [dict(r) for r in cur.fetchall()]


def get_namespace_stats(namespace: str) -> dict:
    """Get stats for a specific namespace."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT COUNT(*) as total_entries,
                   COUNT(*) FILTER (WHERE (metadata->>'approved')::boolean = true) as approved,
                   MIN(created_at) as first_entry,
                   MAX(created_at) as last_entry
            FROM scoped_memory
            WHERE namespace = %s
        """, (namespace,))
        return dict(cur.fetchone())


def clear_namespace(namespace: str) -> int:
    """Delete all entries in a namespace. Returns count deleted."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM scoped_memory WHERE namespace = %s", (namespace,))
        count = cur.rowcount
    conn.commit()
    return count
