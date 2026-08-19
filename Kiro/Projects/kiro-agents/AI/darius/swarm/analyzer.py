"""
Trace Analyzer — Extracts actionable patterns from Darius execution history.

Analyzes darius_traces to identify:
- Which task types fail most often
- Which models underperform (latency, errors)
- Which steps get rejected by the evaluator
- Token efficiency trends (are we getting better or worse?)
- Common error patterns that indicate skill gaps

Output: structured insights that feed into the skill refinement engine.
"""
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger("darius.swarm.analyzer")

_DSN = os.environ.get("POSTGRES_DSN", "")


def _get_conn():
    import psycopg2
    return psycopg2.connect(_DSN)


def analyze(days: int = 7) -> dict:
    """
    Run full analysis on the last N days of traces.
    Returns structured insights for the refinement engine.
    """
    insights = {
        "period_days": days,
        "analyzed_at": datetime.utcnow().isoformat(),
        "summary": {},
        "failure_patterns": [],
        "model_performance": [],
        "engine_comparison": [],
        "skill_gaps": [],
        "recommendations": [],
    }

    try:
        conn = _get_conn()
        cur = conn.cursor()

        # ── Overall Summary ───────────────────────────────────────────────────
        cur.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'success') as success,
                COUNT(*) FILTER (WHERE status != 'success') as failed,
                COALESCE(AVG(latency_ms), 0) as avg_latency,
                COALESCE(SUM(tokens_in + tokens_out), 0) as total_tokens
            FROM darius_traces
            WHERE created_at > NOW() - INTERVAL '%s days'
        """, (days,))
        row = cur.fetchone()
        insights["summary"] = {
            "total_executions": row[0],
            "successes": row[1],
            "failures": row[2],
            "success_rate": round((row[1] / max(row[0], 1)) * 100, 1),
            "avg_latency_ms": int(row[3]),
            "total_tokens": int(row[4]),
        }

        # ── Failure Patterns ──────────────────────────────────────────────────
        cur.execute("""
            SELECT
                tool_name,
                phase,
                COUNT(*) as fail_count,
                ARRAY_AGG(DISTINCT LEFT(tool_result, 100)) as sample_errors
            FROM darius_traces
            WHERE status != 'success'
                AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY tool_name, phase
            ORDER BY fail_count DESC
            LIMIT 10
        """, (days,))
        for row in cur.fetchall():
            insights["failure_patterns"].append({
                "tool": row[0],
                "phase": row[1],
                "count": row[2],
                "sample_errors": row[3][:3] if row[3] else [],
            })

        # ── Model Performance ─────────────────────────────────────────────────
        cur.execute("""
            SELECT
                model,
                COUNT(*) as calls,
                COUNT(*) FILTER (WHERE status = 'success') as successes,
                COALESCE(AVG(latency_ms) FILTER (WHERE status = 'success'), 0) as avg_latency,
                COALESCE(AVG(tokens_in + tokens_out), 0) as avg_tokens
            FROM darius_traces
            WHERE model IS NOT NULL
                AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY model
            ORDER BY calls DESC
        """, (days,))
        for row in cur.fetchall():
            insights["model_performance"].append({
                "model": row[0],
                "calls": row[1],
                "success_rate": round((row[2] / max(row[1], 1)) * 100, 1),
                "avg_latency_ms": int(row[3]),
                "avg_tokens": int(row[4]),
            })

        # ── Engine Comparison ─────────────────────────────────────────────────
        cur.execute("""
            SELECT
                tool_name,
                COUNT(*) as executions,
                COUNT(*) FILTER (WHERE status = 'success') as successes,
                COALESCE(AVG(latency_ms), 0) as avg_latency,
                COALESCE(AVG(tokens_in), 0) as avg_input_tokens
            FROM darius_traces
            WHERE tool_name IN ('delta_executor', 'agent_swarm', 'agent:darius', 'planner')
                AND phase = 'complete'
                AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY tool_name
            ORDER BY executions DESC
        """, (days,))
        for row in cur.fetchall():
            insights["engine_comparison"].append({
                "engine": row[0],
                "executions": row[1],
                "success_rate": round((row[2] / max(row[1], 1)) * 100, 1),
                "avg_latency_ms": int(row[3]),
                "avg_input_tokens": int(row[4]),
            })

        # ── Skill Gaps (tasks that repeatedly fail) ───────────────────────────
        cur.execute("""
            SELECT
                LEFT(tool_args::text, 200) as task_preview,
                COUNT(*) as attempts,
                COUNT(*) FILTER (WHERE status = 'success') as successes
            FROM darius_traces
            WHERE phase = 'complete'
                AND created_at > NOW() - INTERVAL '%s days'
            GROUP BY LEFT(tool_args::text, 200)
            HAVING COUNT(*) >= 2 AND COUNT(*) FILTER (WHERE status = 'success') < COUNT(*) * 0.5
            ORDER BY attempts DESC
            LIMIT 5
        """, (days,))
        for row in cur.fetchall():
            insights["skill_gaps"].append({
                "task_pattern": row[0],
                "attempts": row[1],
                "successes": row[2],
                "failure_rate": round(((row[1] - row[2]) / max(row[1], 1)) * 100, 1),
            })

        conn.close()

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        insights["error"] = str(e)

    # ── Generate Recommendations ──────────────────────────────────────────────
    insights["recommendations"] = _generate_recommendations(insights)

    return insights


def _generate_recommendations(insights: dict) -> list[str]:
    """Generate actionable recommendations from analysis."""
    recs = []

    summary = insights.get("summary", {})
    if summary.get("success_rate", 100) < 90:
        recs.append(f"Success rate is {summary['success_rate']}% — investigate failure patterns below")

    if summary.get("avg_latency_ms", 0) > 60000:
        recs.append(f"Avg latency {summary['avg_latency_ms']}ms — consider using /task/delta for sequential tasks")

    # Model recommendations
    for mp in insights.get("model_performance", []):
        if mp["success_rate"] < 80 and mp["calls"] > 3:
            recs.append(f"Model '{mp['model']}' has {mp['success_rate']}% success rate — consider switching to a different tier")

    # Engine recommendations
    engines = insights.get("engine_comparison", [])
    if engines:
        best = min(engines, key=lambda e: e.get("avg_input_tokens", 999999))
        if best["engine"] != "agent_swarm":
            recs.append(f"'{best['engine']}' is most token-efficient — route more tasks there")

    # Skill gap recommendations
    for gap in insights.get("skill_gaps", []):
        recs.append(f"Repeated failures on: {gap['task_pattern'][:80]} ({gap['failure_rate']}% fail rate) — needs skill refinement")

    if not recs:
        recs.append("No critical issues detected. System performing within expected parameters.")

    return recs
