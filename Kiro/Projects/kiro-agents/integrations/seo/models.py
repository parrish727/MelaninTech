"""
SEO Pipeline — Data Model (Postgres)

Tables:
  seo_sites          — registered sites for tracking
  seo_gsc_data       — raw GSC query/page data (weekly snapshots)
  seo_keywords       — discovered + tracked keyword list
  seo_serp_positions — SERP rank tracking per keyword (weekly)
  seo_analysis       — analysis findings (opportunities/issues)
  seo_actions        — generated improvement tickets

All tables auto-created on first import.
"""
import os
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
        # Sites to track
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seo_sites (
                id SERIAL PRIMARY KEY,
                domain TEXT UNIQUE NOT NULL,
                gsc_property TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # GSC raw data — weekly snapshots
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seo_gsc_data (
                id SERIAL PRIMARY KEY,
                site_id INTEGER REFERENCES seo_sites(id),
                query TEXT NOT NULL,
                page TEXT,
                clicks INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                ctr REAL DEFAULT 0.0,
                position REAL DEFAULT 0.0,
                date_range_start DATE NOT NULL,
                date_range_end DATE NOT NULL,
                collected_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gsc_site_date ON seo_gsc_data(site_id, date_range_start)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_gsc_query ON seo_gsc_data(query)")

        # Keyword list — discovered from GSC + SERP research
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seo_keywords (
                id SERIAL PRIMARY KEY,
                site_id INTEGER REFERENCES seo_sites(id),
                keyword TEXT NOT NULL,
                category TEXT,
                priority TEXT DEFAULT 'medium',
                source TEXT DEFAULT 'gsc',
                monthly_volume INTEGER,
                difficulty REAL,
                current_position REAL,
                target_page TEXT,
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(site_id, keyword)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_keywords_site ON seo_keywords(site_id, active)")

        # SERP position tracking — weekly snapshots
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seo_serp_positions (
                id SERIAL PRIMARY KEY,
                keyword_id INTEGER REFERENCES seo_keywords(id),
                position INTEGER,
                url TEXT,
                snippet TEXT,
                checked_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_serp_keyword ON seo_serp_positions(keyword_id, checked_at)")

        # Analysis findings — opportunities and issues
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seo_analysis (
                id SERIAL PRIMARY KEY,
                site_id INTEGER REFERENCES seo_sites(id),
                finding_type TEXT NOT NULL,
                severity TEXT DEFAULT 'medium',
                title TEXT NOT NULL,
                description TEXT,
                data JSONB,
                status TEXT DEFAULT 'new',
                ticket_id TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_analysis_site ON seo_analysis(site_id, status)")

        _conn.commit()
    return _conn


# ── Site Management ───────────────────────────────────────────────────────────

def register_site(domain: str, gsc_property: str = None) -> dict:
    """Register a site for SEO tracking."""
    conn = _get_conn()
    prop = gsc_property or f"sc-domain:{domain}"
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO seo_sites (domain, gsc_property)
               VALUES (%s, %s)
               ON CONFLICT (domain) DO UPDATE SET gsc_property = EXCLUDED.gsc_property, active = TRUE
               RETURNING *""",
            (domain, prop),
        )
        site = dict(cur.fetchone())
    conn.commit()
    return site


def get_site(domain: str) -> dict | None:
    """Get site by domain."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM seo_sites WHERE domain = %s", (domain,))
        row = cur.fetchone()
        return dict(row) if row else None


# ── GSC Data ──────────────────────────────────────────────────────────────────

def store_gsc_data(site_id: int, rows: list[dict], date_start: str, date_end: str):
    """Bulk insert GSC query data for a date range."""
    conn = _get_conn()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """INSERT INTO seo_gsc_data
                   (site_id, query, page, clicks, impressions, ctr, position, date_range_start, date_range_end)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    site_id, row["query"], row.get("page"),
                    row.get("clicks", 0), row.get("impressions", 0),
                    row.get("ctr", 0.0), row.get("position", 0.0),
                    date_start, date_end,
                ),
            )
    conn.commit()


def get_gsc_data(site_id: int, limit: int = 100, days_back: int = 28) -> list[dict]:
    """Get recent GSC data for a site."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT query, page, clicks, impressions, ctr, position, date_range_start
               FROM seo_gsc_data
               WHERE site_id = %s AND collected_at > NOW() - INTERVAL '%s days'
               ORDER BY impressions DESC
               LIMIT %s""",
            (site_id, days_back, limit),
        )
        return [dict(r) for r in cur.fetchall()]


# ── Keywords ──────────────────────────────────────────────────────────────────

def upsert_keyword(site_id: int, keyword: str, **kwargs) -> dict:
    """Insert or update a tracked keyword."""
    conn = _get_conn()
    fields = {k: v for k, v in kwargs.items() if v is not None}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO seo_keywords (site_id, keyword, category, priority, source, monthly_volume, difficulty, current_position, target_page)
               VALUES (%(site_id)s, %(keyword)s, %(category)s, %(priority)s, %(source)s, %(monthly_volume)s, %(difficulty)s, %(current_position)s, %(target_page)s)
               ON CONFLICT (site_id, keyword)
               DO UPDATE SET
                   current_position = COALESCE(EXCLUDED.current_position, seo_keywords.current_position),
                   monthly_volume = COALESCE(EXCLUDED.monthly_volume, seo_keywords.monthly_volume),
                   difficulty = COALESCE(EXCLUDED.difficulty, seo_keywords.difficulty),
                   target_page = COALESCE(EXCLUDED.target_page, seo_keywords.target_page)
               RETURNING *""",
            {
                "site_id": site_id,
                "keyword": keyword,
                "category": fields.get("category"),
                "priority": fields.get("priority", "medium"),
                "source": fields.get("source", "gsc"),
                "monthly_volume": fields.get("monthly_volume"),
                "difficulty": fields.get("difficulty"),
                "current_position": fields.get("current_position"),
                "target_page": fields.get("target_page"),
            },
        )
        result = dict(cur.fetchone())
    conn.commit()
    return result


def get_keywords(site_id: int, active_only: bool = True) -> list[dict]:
    """Get all tracked keywords for a site."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        query = "SELECT * FROM seo_keywords WHERE site_id = %s"
        if active_only:
            query += " AND active = TRUE"
        query += " ORDER BY priority DESC, current_position ASC"
        cur.execute(query, (site_id,))
        return [dict(r) for r in cur.fetchall()]


# ── SERP Positions ────────────────────────────────────────────────────────────

def store_serp_position(keyword_id: int, position: int, url: str = None, snippet: str = None):
    """Store a SERP position check result."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO seo_serp_positions (keyword_id, position, url, snippet)
               VALUES (%s, %s, %s, %s)""",
            (keyword_id, position, url, snippet),
        )
        # Update current_position on keyword
        cur.execute(
            "UPDATE seo_keywords SET current_position = %s WHERE id = %s",
            (position, keyword_id),
        )
    conn.commit()


def get_position_history(keyword_id: int, limit: int = 12) -> list[dict]:
    """Get position history for a keyword (last N checks)."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT position, url, checked_at
               FROM seo_serp_positions
               WHERE keyword_id = %s
               ORDER BY checked_at DESC
               LIMIT %s""",
            (keyword_id, limit),
        )
        return [dict(r) for r in cur.fetchall()]


# ── Analysis Findings ─────────────────────────────────────────────────────────

def store_finding(site_id: int, finding_type: str, title: str, description: str = None, severity: str = "medium", data: dict = None) -> dict:
    """Store an analysis finding."""
    import json
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO seo_analysis (site_id, finding_type, severity, title, description, data)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (site_id, finding_type, severity, title, description, json.dumps(data) if data else None),
        )
        result = dict(cur.fetchone())
    conn.commit()
    return result


def get_findings(site_id: int, status: str = "new") -> list[dict]:
    """Get analysis findings by status."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT * FROM seo_analysis
               WHERE site_id = %s AND status = %s
               ORDER BY severity DESC, created_at DESC""",
            (site_id, status),
        )
        return [dict(r) for r in cur.fetchall()]


def update_finding_status(finding_id: int, status: str, ticket_id: str = None):
    """Update finding status (new → ticketed → done)."""
    conn = _get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE seo_analysis SET status = %s, ticket_id = %s WHERE id = %s",
            (status, ticket_id, finding_id),
        )
    conn.commit()
