"""
Orchestrator Memory — semantic recall for task decisions and conversation history.

Architecture (post-Qdrant migration):
  - PRIMARY: Qdrant via SemanticLayer for all reads
  - FALLBACK: pgvector if Qdrant is unreachable
  - DUAL-WRITE: All writes go to both Qdrant AND pgvector for backward compat

Tables (pgvector — kept for fallback):
  task_memory — past task decisions with embeddings
  conversation_memory — CEO/system conversation turns with embeddings
"""
import os
import logging
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("orchestrator.memory")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
_conn = None

# ── Qdrant (Primary) ─────────────────────────────────────────────────────────

_semantic_layer = None


def _get_qdrant():
    """Lazy-init the Qdrant SemanticLayer client."""
    global _semantic_layer
    if _semantic_layer is None:
        try:
            from integrations.qdrant_client import SemanticLayer
            _semantic_layer = SemanticLayer()
            if not _semantic_layer.health():
                logger.warning("Qdrant not healthy — will use pgvector fallback")
                _semantic_layer = None
        except Exception as e:
            logger.warning(f"Qdrant init failed: {e} — using pgvector fallback")
            _semantic_layer = None
    return _semantic_layer


def _qdrant_available() -> bool:
    """Check if Qdrant is reachable."""
    sl = _get_qdrant()
    if sl is None:
        return False
    try:
        return sl.health()
    except Exception:
        return False


# ── PostgreSQL (Fallback + Dual-Write Target) ─────────────────────────────────

def _get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(os.environ["POSTGRES_DSN"])
    if _conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
        try:
            _conn.rollback()
        except Exception:
            _conn = psycopg2.connect(os.environ["POSTGRES_DSN"])
    with _conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS task_memory (
                id SERIAL PRIMARY KEY,
                task TEXT,
                proposal TEXT,
                agent TEXT,
                decision TEXT,
                embedding vector(768),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id SERIAL PRIMARY KEY,
                role TEXT,
                content TEXT,
                embedding vector(768),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        _conn.commit()
    return _conn


def _embed(text: str) -> list[float]:
    response = httpx.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["embedding"]


# ── Task Memory ───────────────────────────────────────────────────────────────

def store(task: str, proposal: str, agent: str, decision: str):
    """
    Store a task decision. Dual-writes to Qdrant + pgvector.
    """
    # Write to pgvector (always — backward compat)
    conn = _get_conn()
    embedding = _embed(task)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO task_memory (task, proposal, agent, decision, embedding) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (task, proposal, agent, decision, embedding),
        )
        row_id = cur.fetchone()[0]
    conn.commit()

    # Write to Qdrant (best-effort — don't fail the operation if Qdrant is down)
    sl = _get_qdrant()
    if sl:
        try:
            text = f"{task} | {proposal or ''} | {decision or ''}"
            sl.upsert(
                "task_memory",
                id=f"task_memory_{row_id}",
                text=text.strip(),
                metadata={
                    "task": task or "",
                    "proposal": proposal or "",
                    "agent": agent or "",
                    "decision": decision or "",
                    "source": "live_write",
                },
            )
        except Exception as e:
            logger.warning(f"Qdrant write failed for task_memory (pgvector write succeeded): {e}")


def recall(task: str, limit: int = 3) -> list[dict]:
    """
    Recall relevant past task decisions. Qdrant primary, pgvector fallback.
    """
    # Try Qdrant first
    sl = _get_qdrant()
    if sl:
        try:
            results = sl.search("task_memory", query=task, limit=limit)
            if results:
                return [
                    {
                        "task": r["payload"].get("task", ""),
                        "proposal": r["payload"].get("proposal", ""),
                        "agent": r["payload"].get("agent", ""),
                        "decision": r["payload"].get("decision", ""),
                    }
                    for r in results
                ]
        except Exception as e:
            logger.warning(f"Qdrant search failed, falling back to pgvector: {e}")

    # Fallback to pgvector
    conn = _get_conn()
    embedding = _embed(task)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT task, proposal, agent, decision
            FROM task_memory
            ORDER BY embedding <-> %s::vector
            LIMIT %s
            """,
            (embedding, limit),
        )
        return cur.fetchall()


# ── Conversation Memory ───────────────────────────────────────────────────────

def store_conversation(role: str, content: str):
    """Store a CEO/system conversation turn. Dual-writes to Qdrant + pgvector."""
    # Write to pgvector
    conn = _get_conn()
    embedding = _embed(content)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO conversation_memory (role, content, embedding) VALUES (%s, %s, %s) RETURNING id",
            (role, content, embedding),
        )
        row_id = cur.fetchone()[0]
    conn.commit()

    # Write to Qdrant (best-effort)
    sl = _get_qdrant()
    if sl:
        try:
            sl.upsert(
                "conversation_memory",
                id=f"conversation_memory_{row_id}",
                text=content,
                metadata={
                    "role": role or "",
                    "content": content[:5000],
                    "source": "live_write",
                },
            )
        except Exception as e:
            logger.warning(f"Qdrant write failed for conversation_memory: {e}")


def recall_conversation(query: str, limit: int = 5) -> list[dict]:
    """Recall relevant past conversation turns. Qdrant primary, pgvector fallback."""
    # Try Qdrant first
    sl = _get_qdrant()
    if sl:
        try:
            results = sl.search("conversation_memory", query=query, limit=limit)
            if results:
                return [
                    {
                        "role": r["payload"].get("role", ""),
                        "content": r["payload"].get("content", ""),
                        "created_at": r["payload"].get("created_at", ""),
                    }
                    for r in results
                ]
        except Exception as e:
            logger.warning(f"Qdrant search failed, falling back to pgvector: {e}")

    # Fallback to pgvector
    conn = _get_conn()
    embedding = _embed(query)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT role, content, created_at
            FROM conversation_memory
            ORDER BY embedding <-> %s::vector
            LIMIT %s
            """,
            (embedding, limit),
        )
        return cur.fetchall()
