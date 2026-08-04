"""
Darius Memory — session persistence via Kiro postgres + pgvector.
Reuses the existing task_memory table and adds darius_sessions + darius_traces tables.

Tables:
  darius_sessions — raw conversation turns per session
  darius_traces   — full reasoning chain for training data extraction
  darius_context_summaries — compressed context for long-running sessions
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

_DSN = os.environ.get("POSTGRES_DSN", "")
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
        # Sessions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS darius_sessions (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_darius_session ON darius_sessions(session_id)")

        # Traces table — captures the full reasoning chain for training data
        cur.execute("""
            CREATE TABLE IF NOT EXISTS darius_traces (
                id SERIAL PRIMARY KEY,
                task_id TEXT NOT NULL,
                session_id TEXT,
                phase TEXT NOT NULL,
                step_index INTEGER DEFAULT 0,
                tool_name TEXT,
                tool_args JSONB,
                tool_result TEXT,
                evaluation_score REAL,
                evaluation_feedback TEXT,
                revision_attempt INTEGER DEFAULT 0,
                model TEXT,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                status TEXT DEFAULT 'success',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_traces_task ON darius_traces(task_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_traces_session ON darius_traces(session_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_traces_phase ON darius_traces(phase)")

        # Context summaries — compressed memory for long sessions
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS darius_context_summaries (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                turn_start INTEGER NOT NULL,
                turn_end INTEGER NOT NULL,
                embedding vector(768),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_context_session ON darius_context_summaries(session_id)")

        _conn.commit()
    return _conn


def save_turn(session_id: str, role: str, content: str):
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO darius_sessions (session_id, role, content) VALUES (%s, %s, %s)",
            (session_id, role, content),
        )
    conn.commit()


def load_session(session_id: str) -> list[dict]:
    """Return all turns for a session ordered by time."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT role, content FROM darius_sessions WHERE session_id=%s ORDER BY created_at",
            (session_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def list_sessions() -> list[str]:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT session_id FROM darius_sessions ORDER BY session_id")
        return [r[0] for r in cur.fetchall()]


# ── Trace Logging ─────────────────────────────────────────────────────────────

def log_trace(
    task_id: str,
    phase: str,
    *,
    session_id: str = None,
    step_index: int = 0,
    tool_name: str = None,
    tool_args: dict = None,
    tool_result: str = None,
    evaluation_score: float = None,
    evaluation_feedback: str = None,
    revision_attempt: int = 0,
    model: str = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: int = 0,
    status: str = "success",
):
    """Log a trace entry for the full reasoning chain.

    Phases: plan, execute, evaluate, revise, reject, complete
    """
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO darius_traces
               (task_id, session_id, phase, step_index, tool_name, tool_args,
                tool_result, evaluation_score, evaluation_feedback, revision_attempt,
                model, tokens_in, tokens_out, latency_ms, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                task_id, session_id, phase, step_index, tool_name,
                json.dumps(tool_args) if tool_args else None,
                tool_result[:10000] if tool_result else None,
                evaluation_score, evaluation_feedback, revision_attempt,
                model, tokens_in, tokens_out, latency_ms, status,
            ),
        )
    conn.commit()


def get_traces(task_id: str) -> list[dict]:
    """Retrieve all trace entries for a task (for replay/training export)."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM darius_traces WHERE task_id=%s ORDER BY created_at",
            (task_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# ── Context Summaries ─────────────────────────────────────────────────────────

def _embed(text: str) -> list[float]:
    """Generate embedding via Ollama nomic-embed-text."""
    import httpx
    ollama_url = os.environ.get("OLLAMA_URL", "http://ollama:11434")
    response = httpx.post(
        f"{ollama_url}/api/embeddings",
        json={"model": "nomic-embed-text", "prompt": text},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def save_context_summary(session_id: str, summary: str, turn_start: int, turn_end: int):
    """Store a compressed context summary. Dual-writes to pgvector + Qdrant."""
    conn = _get_conn()
    embedding = _embed(summary)
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO darius_context_summaries
               (session_id, summary, turn_start, turn_end, embedding)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (session_id, summary, turn_start, turn_end, embedding),
        )
        row_id = cur.fetchone()[0]
    conn.commit()

    # Dual-write to Qdrant (best-effort — don't fail if Qdrant is down)
    try:
        from integrations.qdrant_client import SemanticLayer
        sl = SemanticLayer()
        if sl.health():
            sl.upsert(
                "context_summaries",
                id=f"context_summary_{row_id}",
                text=summary,
                metadata={
                    "session_id": session_id,
                    "summary": summary[:5000],
                    "turn_start": turn_start,
                    "turn_end": turn_end,
                    "source": "live_write",
                },
            )
    except Exception as e:
        import logging
        logging.getLogger("darius.memory").warning(
            f"Qdrant write failed for context_summary (pgvector write succeeded): {e}"
        )


def recall_context_summaries(session_id: str, query: str, limit: int = 3) -> list[dict]:
    """
    Retrieve the most relevant context summaries for a session.
    Qdrant primary, pgvector fallback.
    """
    # Try Qdrant first
    try:
        from integrations.qdrant_client import SemanticLayer
        sl = SemanticLayer()
        if sl.health():
            results = sl.search_with_filter(
                "context_summaries",
                query=query,
                must=[{"key": "session_id", "match": {"value": session_id}}],
                limit=limit,
            )
            if results:
                return [
                    {
                        "summary": r["payload"].get("summary", r["payload"].get("_text", "")),
                        "turn_start": r["payload"].get("turn_start", 0),
                        "turn_end": r["payload"].get("turn_end", 0),
                    }
                    for r in results
                ]
    except Exception as e:
        import logging
        logging.getLogger("darius.memory").warning(
            f"Qdrant search failed for context_summaries, using pgvector: {e}"
        )

    # Fallback to pgvector
    conn = _get_conn()
    embedding = _embed(query)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT summary, turn_start, turn_end
               FROM darius_context_summaries
               WHERE session_id = %s
               ORDER BY embedding <-> %s::vector
               LIMIT %s""",
            (session_id, embedding, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def get_session_turn_count(session_id: str) -> int:
    """Get the total number of turns in a session."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM darius_sessions WHERE session_id=%s",
            (session_id,),
        )
        return cur.fetchone()[0]


def get_last_summary_turn(session_id: str) -> int:
    """Get the turn_end of the most recent summary for a session."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(MAX(turn_end), 0) FROM darius_context_summaries WHERE session_id=%s",
            (session_id,),
        )
        return cur.fetchone()[0]
