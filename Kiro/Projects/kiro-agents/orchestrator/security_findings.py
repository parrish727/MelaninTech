"""
Security Findings — persistent audit trail for the security-compliance system.

Every detection from the security-agent (sensor/executor) is written here, not just
posted to Slack. This gives Darius (the analysis/evaluation brain) a queryable history
to reason over, and provides a compliance audit trail mapped to governance policies.

Table lifecycle:
  detected -> analyzing (routed to Darius) -> proposed -> approved|dismissed
           -> remediated -> verified   (or) auto_remediated (allowlisted actions)

Threat classes map to the aligned skill files in agents/skills/security-*.skill.md.
"""
import os
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import RealDictCursor

_conn = None
_schema_initialized = False

# Threat classes — each aligns to a security-*.skill.md for Darius analysis.
THREAT_CLASSES = (
    "secret_scanner",        # bots probing for .env/config/credentials
    "malicious_dependency",  # trojan/supply-chain — poisoned packages, typosquats
    "prompt_injection",      # agent-hijack — injected instructions via untrusted input
    "credential_stuffing",   # repeated auth failures / brute force
    "ddos_ratelimit",        # volumetric / rate-limit abuse
    "unauthorized_access",   # socket/privilege/network-policy violation
    "secret_leak",           # secret pattern found in logs/output
    "compliance_drift",      # governance policy violation (non-attack)
)

# Severity → incident tier (mirrors the P1-P4 model used by SRE).
SEVERITY_TIERS = ("P1", "P2", "P3", "P4")

# Autonomous remediation allowlist. Everything else is propose-only (Slack approval).
# Aligns with the self-healing posture: these are non-destructive, reversible actions.
AUTONOMOUS_ACTIONS = ("ban_ip", "restart_container", "seal_endpoint")


def _get_conn():
    global _conn, _schema_initialized
    dsn = os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro")
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(dsn)
        _conn.autocommit = False
        _schema_initialized = False
    if _conn.status == psycopg2.extensions.STATUS_IN_TRANSACTION:
        try:
            _conn.rollback()
        except Exception:
            _conn = psycopg2.connect(dsn)
            _conn.autocommit = False
            _schema_initialized = False
    if not _schema_initialized:
        with _conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS security_findings (
                    id SERIAL PRIMARY KEY,
                    threat_class TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'P3',
                    source TEXT,
                    subject TEXT,
                    evidence TEXT,
                    governance_ref TEXT,
                    status TEXT NOT NULL DEFAULT 'detected',
                    analysis TEXT,
                    proposed_action TEXT,
                    action_taken TEXT,
                    autonomous BOOLEAN DEFAULT FALSE,
                    callback_id TEXT,
                    first_seen TIMESTAMPTZ DEFAULT NOW(),
                    last_seen TIMESTAMPTZ DEFAULT NOW(),
                    hit_count INT DEFAULT 1,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_secfind_status ON security_findings (status)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_secfind_class ON security_findings (threat_class, last_seen DESC)
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_secfind_dedupe
                ON security_findings (threat_class, subject)
                WHERE status IN ('detected', 'analyzing', 'proposed')
            """)
        _conn.commit()
        _schema_initialized = True
    return _conn


def record_finding(threat_class: str, subject: str, evidence: str,
                   severity: str = "P3", source: str = "security-watchdog",
                   governance_ref: str | None = None) -> int:
    """Persist a finding. Deduplicates open findings by (threat_class, subject):
    a repeat increments hit_count and bumps last_seen instead of creating a new row.
    Returns the finding id.
    """
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT id FROM security_findings
            WHERE threat_class = %s AND subject = %s
              AND status IN ('detected', 'analyzing', 'proposed')
            ORDER BY id DESC LIMIT 1
        """, (threat_class, subject))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE security_findings
                SET hit_count = hit_count + 1, last_seen = NOW(), updated_at = NOW(),
                    evidence = %s
                WHERE id = %s
            """, (evidence, row["id"]))
            conn.commit()
            return row["id"]
        cur.execute("""
            INSERT INTO security_findings
                (threat_class, severity, source, subject, evidence, governance_ref)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (threat_class, severity, source, subject, evidence, governance_ref))
        fid = cur.fetchone()["id"]
    conn.commit()
    return fid


def update_finding(finding_id: int, **fields):
    """Update mutable fields on a finding (status, analysis, proposed_action,
    action_taken, autonomous, callback_id, severity)."""
    allowed = {"status", "analysis", "proposed_action", "action_taken",
               "autonomous", "callback_id", "severity"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    conn = _get_conn()
    cols = ", ".join(f"{k} = %s" for k in sets)
    vals = list(sets.values()) + [finding_id]
    with conn.cursor() as cur:
        cur.execute(f"UPDATE security_findings SET {cols}, updated_at = NOW() WHERE id = %s", vals)
    conn.commit()


def open_findings(limit: int = 50) -> list[dict]:
    """Return findings still needing attention (not verified/dismissed)."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT * FROM security_findings
            WHERE status NOT IN ('verified', 'dismissed', 'auto_remediated')
            ORDER BY
                CASE severity WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END,
                last_seen DESC
            LIMIT %s
        """, (limit,))
        return [dict(r) for r in cur.fetchall()]


def findings_summary(hours: int = 24) -> dict:
    """Aggregate counts by threat_class and severity over a window (for reports)."""
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"""
            SELECT threat_class, severity, COUNT(*) AS n, SUM(hit_count) AS hits
            FROM security_findings
            WHERE last_seen > NOW() - INTERVAL '{int(hours)} hours'
            GROUP BY threat_class, severity
            ORDER BY n DESC
        """)
        return {"window_hours": hours, "rows": [dict(r) for r in cur.fetchall()]}
