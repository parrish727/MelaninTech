"""
Darius Memory — session persistence via Kiro postgres + pgvector.
Reuses the existing task_memory table and adds a darius_sessions table.
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
