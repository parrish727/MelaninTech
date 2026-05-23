import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

_conn = None

MAX_ATTEMPTS = 9


def _get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(os.environ["POSTGRES_DSN"])
        _conn.autocommit = False
    # if connection is in a bad state, reset it
    if _conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
        try:
            _conn.rollback()
        except Exception:
            _conn = psycopg2.connect(os.environ["POSTGRES_DSN"])
            _conn.autocommit = False
    with _conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id SERIAL PRIMARY KEY,
                client TEXT NOT NULL,
                agent TEXT,
                task TEXT NOT NULL,
                proposal TEXT,
                status TEXT DEFAULT 'open',
                type TEXT DEFAULT 'client',
                priority TEXT DEFAULT 'normal',
                callback_id TEXT UNIQUE,
                attempts INT DEFAULT 0,
                last_heartbeat TIMESTAMPTZ,
                log TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        for col, definition in [
            ("priority", "TEXT DEFAULT 'normal'"),
            ("attempts", "INT DEFAULT 0"),
            ("last_heartbeat", "TIMESTAMPTZ"),
            ("log", "TEXT"),
        ]:
            cur.execute(f"""
                ALTER TABLE tickets ADD COLUMN IF NOT EXISTS {col} {definition}
            """)
    _conn.commit()
    return _conn


def open_ticket(client: str, task: str, agent: str, proposal: str, callback_id: str,
                ticket_type: str = "client", priority: str = "normal") -> int:
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO tickets (client, task, agent, proposal, status, type, priority, callback_id, attempts)
               VALUES (%s, %s, %s, %s, 'open', %s, %s, %s, 0) RETURNING id""",
            (client, task, agent, proposal, ticket_type, priority, callback_id),
        )
        ticket_id = cur.fetchone()[0]
    conn.commit()
    return ticket_id


def update_ticket(callback_id: str, status: str, log: str = None):
    conn = _get_conn()
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        if log:
            cur.execute(
                "UPDATE tickets SET status=%s, updated_at=%s, log=COALESCE(log,'') || %s WHERE callback_id=%s",
                (status, now, f"\n[{now.isoformat()}] {log}", callback_id),
            )
        else:
            cur.execute(
                "UPDATE tickets SET status=%s, updated_at=%s WHERE callback_id=%s",
                (status, now, callback_id),
            )
    conn.commit()


def heartbeat(callback_id: str, log: str = None):
    """Called periodically by agents while working to signal they are alive."""
    conn = _get_conn()
    now = datetime.now(timezone.utc)
    with conn.cursor() as cur:
        if log:
            cur.execute(
                """UPDATE tickets SET last_heartbeat=%s, updated_at=%s,
                   log=COALESCE(log,'') || %s WHERE callback_id=%s""",
                (now, now, f"\n[{now.isoformat()}] {log}", callback_id),
            )
        else:
            cur.execute(
                "UPDATE tickets SET last_heartbeat=%s, updated_at=%s WHERE callback_id=%s",
                (now, now, callback_id),
            )
    conn.commit()


def increment_attempts(callback_id: str) -> int:
    """Increment attempt counter and return new count."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE tickets SET attempts=attempts+1, updated_at=%s WHERE callback_id=%s RETURNING attempts",
            (datetime.now(timezone.utc), callback_id),
        )
        row = cur.fetchone()
    conn.commit()
    return row[0] if row else 0


def get_stuck_tickets(timeout_seconds: int) -> list[dict]:
    """Return in_progress tickets whose heartbeat has expired."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT * FROM tickets
               WHERE status = 'in_progress'
               AND last_heartbeat < NOW() - INTERVAL '%s seconds'""",
            (timeout_seconds,),
        )
        return cur.fetchall()


def list_tickets(client: str = None, status: str = None, ticket_type: str = None,
                 priority: str = None) -> list[dict]:
    conn = _get_conn()
    query = "SELECT id, client, agent, task, status, type, priority, attempts, created_at FROM tickets WHERE 1=1"
    params = []
    if client:
        query += " AND client=%s"; params.append(client)
    if status:
        query += " AND status=%s"; params.append(status)
    if ticket_type:
        query += " AND type=%s"; params.append(ticket_type)
    if priority:
        query += " AND priority=%s"; params.append(priority)
    query += " ORDER BY created_at DESC LIMIT 20"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()
