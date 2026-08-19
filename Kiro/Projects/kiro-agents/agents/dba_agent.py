"""
DBA Agent — PostgreSQL Health Diagnostics
The PostgreSQL equivalent of sp_Blitz: automated health checks,
slow query analysis, index recommendations, bloat detection,
and connection pool monitoring.

Integrated with the orchestrator as a routable agent.
Responds to /task with diagnostic reports.
"""
import os
import json
import uvicorn
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI

app = FastAPI()

POSTGRES_DSN = os.environ.get(
    "POSTGRES_DSN",
    "postgresql://orthoflow:changeme@postgres:5432/orthoflow"
)


def _conn():
    """Get a fresh connection for diagnostics."""
    return psycopg2.connect(POSTGRES_DSN, cursor_factory=RealDictCursor)


def check_connection_health() -> dict:
    """Connection stats — like sp_Blitz's 'Who's Connected'."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                count(*) as total_connections,
                count(*) FILTER (WHERE state = 'active') as active,
                count(*) FILTER (WHERE state = 'idle') as idle,
                count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
                count(*) FILTER (WHERE wait_event_type IS NOT NULL AND state = 'active') as waiting,
                (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_connections
            FROM pg_stat_activity
            WHERE backend_type = 'client backend'
        """)
        stats = dict(cur.fetchone())
        stats["utilization_pct"] = round(stats["total_connections"] / stats["max_connections"] * 100, 1)

        # Longest running queries
        cur.execute("""
            SELECT pid, now() - query_start as duration, state, left(query, 100) as query_preview
            FROM pg_stat_activity
            WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%'
            ORDER BY query_start ASC
            LIMIT 5
        """)
        stats["long_running_queries"] = [dict(r) for r in cur.fetchall()]
        return stats


def check_table_bloat() -> list:
    """Detect table bloat — equivalent of sp_Blitz's bloat checks."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                schemaname || '.' || relname as table_name,
                n_dead_tup as dead_tuples,
                n_live_tup as live_tuples,
                CASE WHEN n_live_tup > 0
                    THEN round(100.0 * n_dead_tup / n_live_tup, 1)
                    ELSE 0 END as dead_pct,
                last_vacuum,
                last_autovacuum,
                last_analyze
            FROM pg_stat_user_tables
            WHERE n_dead_tup > 1000
            ORDER BY n_dead_tup DESC
            LIMIT 10
        """)
        return [dict(r) for r in cur.fetchall()]


def check_index_health() -> dict:
    """Index usage analysis — find unused and missing indexes."""
    with _conn() as conn:
        cur = conn.cursor()

        # Unused indexes (created but never scanned)
        cur.execute("""
            SELECT
                schemaname || '.' || relname as table_name,
                indexrelname as index_name,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                idx_scan as scans
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0
                AND indexrelname NOT LIKE '%pkey%'
                AND indexrelname NOT LIKE '%unique%'
            ORDER BY pg_relation_size(indexrelid) DESC
            LIMIT 10
        """)
        unused = [dict(r) for r in cur.fetchall()]

        # Tables with sequential scans (potential missing indexes)
        cur.execute("""
            SELECT
                schemaname || '.' || relname as table_name,
                seq_scan,
                seq_tup_read,
                idx_scan,
                CASE WHEN seq_scan + idx_scan > 0
                    THEN round(100.0 * seq_scan / (seq_scan + idx_scan), 1)
                    ELSE 0 END as seq_scan_pct,
                n_live_tup as row_count
            FROM pg_stat_user_tables
            WHERE seq_scan > 100
                AND n_live_tup > 1000
                AND (seq_scan > idx_scan OR idx_scan IS NULL)
            ORDER BY seq_tup_read DESC
            LIMIT 10
        """)
        missing = [dict(r) for r in cur.fetchall()]

        return {"unused_indexes": unused, "tables_needing_indexes": missing}


def check_slow_queries() -> list:
    """Top slow queries from pg_stat_statements (requires extension)."""
    with _conn() as conn:
        cur = conn.cursor()
        # Check if pg_stat_statements is available
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'")
        if not cur.fetchone():
            return [{"note": "pg_stat_statements not installed. Run: CREATE EXTENSION pg_stat_statements;"}]

        cur.execute("""
            SELECT
                left(query, 150) as query_preview,
                calls,
                round(total_exec_time::numeric / 1000, 2) as total_time_sec,
                round(mean_exec_time::numeric, 2) as avg_time_ms,
                round(max_exec_time::numeric, 2) as max_time_ms,
                rows
            FROM pg_stat_statements
            WHERE query NOT LIKE '%pg_stat%'
                AND calls > 10
            ORDER BY mean_exec_time DESC
            LIMIT 10
        """)
        return [dict(r) for r in cur.fetchall()]


def check_database_size() -> dict:
    """Database size and largest tables."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT pg_size_pretty(pg_database_size(current_database())) as db_size")
        db_size = cur.fetchone()["db_size"]

        cur.execute("""
            SELECT
                schemaname || '.' || relname as table_name,
                pg_size_pretty(pg_total_relation_size(relid)) as total_size,
                pg_size_pretty(pg_relation_size(relid)) as table_size,
                pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid)) as index_size,
                n_live_tup as row_count
            FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(relid) DESC
            LIMIT 10
        """)
        tables = [dict(r) for r in cur.fetchall()]

        return {"database_size": db_size, "largest_tables": tables}


def check_replication_and_wal() -> dict:
    """WAL generation rate and replication status."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')) as total_wal_generated")
        wal = dict(cur.fetchone())

        cur.execute("""
            SELECT
                checkpoint_write_time,
                checkpoint_sync_time,
                checkpoints_timed,
                checkpoints_req,
                buffers_checkpoint
            FROM pg_stat_bgwriter
        """)
        bgwriter = dict(cur.fetchone())
        wal.update(bgwriter)
        return wal


def check_cache_hit_ratio() -> dict:
    """Buffer cache hit ratio — should be >99% for a healthy DB."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                sum(blks_hit) as hits,
                sum(blks_read) as reads,
                CASE WHEN sum(blks_hit) + sum(blks_read) > 0
                    THEN round(100.0 * sum(blks_hit) / (sum(blks_hit) + sum(blks_read)), 2)
                    ELSE 100 END as hit_ratio_pct
            FROM pg_stat_database
            WHERE datname = current_database()
        """)
        return dict(cur.fetchone())


def full_health_check() -> dict:
    """Run all diagnostics — the full sp_Blitz equivalent."""
    report = {
        "status": "healthy",
        "issues": [],
    }

    try:
        # Connections
        conns = check_connection_health()
        report["connections"] = conns
        if conns["utilization_pct"] > 80:
            report["issues"].append(f"⚠️ Connection utilization at {conns['utilization_pct']}% — consider increasing max_connections or optimizing pool")
            report["status"] = "warning"
        if conns["idle_in_transaction"] > 5:
            report["issues"].append(f"⚠️ {conns['idle_in_transaction']} idle-in-transaction connections — possible connection leak")

        # Cache
        cache = check_cache_hit_ratio()
        report["cache"] = cache
        if cache["hit_ratio_pct"] < 99:
            report["issues"].append(f"⚠️ Cache hit ratio {cache['hit_ratio_pct']}% — consider increasing shared_buffers")
            report["status"] = "warning"

        # Bloat
        bloat = check_table_bloat()
        report["bloat"] = bloat
        for t in bloat:
            if t["dead_pct"] > 20:
                report["issues"].append(f"🔴 High bloat on {t['table_name']}: {t['dead_pct']}% dead tuples — needs VACUUM")
                report["status"] = "critical" if report["status"] != "critical" else report["status"]

        # Indexes
        indexes = check_index_health()
        report["indexes"] = indexes
        if len(indexes["unused_indexes"]) > 5:
            report["issues"].append(f"⚠️ {len(indexes['unused_indexes'])} unused indexes wasting space")
        if len(indexes["tables_needing_indexes"]) > 3:
            report["issues"].append(f"⚠️ {len(indexes['tables_needing_indexes'])} tables doing mostly sequential scans — add indexes")

        # Slow queries
        slow = check_slow_queries()
        report["slow_queries"] = slow

        # Size
        size = check_database_size()
        report["size"] = size

        if not report["issues"]:
            report["issues"].append("✅ All checks passed — database is healthy")

    except Exception as e:
        report["status"] = "error"
        report["issues"].append(f"🔴 Health check failed: {e}")

    return report


# ── Agent API ─────────────────────────────────────────────────────────────────

@app.post("/task")
def handle_task(body: dict):
    """Handle tasks routed by the orchestrator."""
    task = body.get("task", "").lower()
    project = body.get("project", "default")

    # Run full health check
    report = full_health_check()

    # Format as a readable proposal
    lines = [
        "## What Is Being Asked",
        "Database health diagnostic — full PostgreSQL inspection.",
        "",
        "## What Is Needed to Execute",
        "- Connection pool status and utilization",
        "- Cache hit ratio analysis",
        "- Table bloat and vacuum status",
        "- Index usage and recommendations",
        "- Slow query identification",
        "- Database size breakdown",
        "",
        "## Expected Result",
        f"Health status: **{report['status'].upper()}**",
        "",
        "---",
        "",
        f"**Status:** {report['status'].upper()}",
        f"**Issues ({len(report['issues'])}):**",
    ]
    for issue in report["issues"]:
        lines.append(f"  {issue}")

    if report.get("connections"):
        c = report["connections"]
        lines.append(f"\n**Connections:** {c['total_connections']}/{c['max_connections']} ({c['utilization_pct']}%) — Active: {c['active']}, Idle: {c['idle']}, Idle-in-Txn: {c['idle_in_transaction']}")

    if report.get("cache"):
        lines.append(f"**Cache Hit Ratio:** {report['cache']['hit_ratio_pct']}%")

    if report.get("size"):
        lines.append(f"**Database Size:** {report['size']['database_size']}")

    if report.get("slow_queries") and len(report["slow_queries"]) > 0 and "note" not in report["slow_queries"][0]:
        lines.append(f"\n**Top Slow Queries ({len(report['slow_queries'])}):**")
        for q in report["slow_queries"][:5]:
            lines.append(f"  • {q['avg_time_ms']}ms avg ({q['calls']} calls): `{q['query_preview'][:80]}`")

    proposal_text = "\n".join(lines)

    return {
        "agent": "DBAAgent",
        "model": "direct",
        "action": "dba",
        "description": f"Database Health Check — {report['status'].upper()}",
        "args": {
            "task": body.get("task", ""),
            "project": project,
            "project_path": "",
            "proposal": proposal_text,
        },
    }


@app.get("/health")
def health():
    """Quick health endpoint for watchdog."""
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
