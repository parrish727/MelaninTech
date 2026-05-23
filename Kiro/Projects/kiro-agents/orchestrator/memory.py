import os
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
_conn = None


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


def store(task: str, proposal: str, agent: str, decision: str):
    conn = _get_conn()
    embedding = _embed(task)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO task_memory (task, proposal, agent, decision, embedding) VALUES (%s, %s, %s, %s, %s)",
            (task, proposal, agent, decision, embedding),
        )
    conn.commit()


def recall(task: str, limit: int = 3) -> list[dict]:
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


def store_conversation(role: str, content: str):
    """Store a CEO/system conversation turn for persistent context."""
    conn = _get_conn()
    embedding = _embed(content)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO conversation_memory (role, content, embedding) VALUES (%s, %s, %s)",
            (role, content, embedding),
        )
    conn.commit()


def recall_conversation(query: str, limit: int = 5) -> list[dict]:
    """Recall relevant past conversation turns by semantic similarity."""
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
