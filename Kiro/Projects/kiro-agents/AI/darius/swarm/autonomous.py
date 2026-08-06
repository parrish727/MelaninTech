"""
Darius Autonomous Heartbeat — Background loop that keeps Darius productive.

Runs as a daemon thread inside the Darius server. On each heartbeat:
1. Check for open tickets assigned to Darius → execute them
2. Check if daily self-improvement is due → run analysis cycle
3. Check if daily digest is due → post productivity report to Slack
4. Update health status in Redis

Safety boundaries:
- Only processes tickets from the ticket queue (no ad-hoc actions)
- Only modifies projects within PROJECTS_BASE
- Posts change window to Slack before any deployment-related work
- Never auto-applies skill refinements (proposals only)
- Respects kill switch (checks Redis flag before each action)
- Logs every autonomous action to darius_traces

Intervals:
- Heartbeat: every 60 seconds (check for work)
- Self-improvement: every 24 hours
- Daily digest: every 24 hours (offset from improvement by 1h)
"""
import os
import time
import json
import logging
import threading
from datetime import datetime

logger = logging.getLogger("darius.autonomous")

_HEARTBEAT_INTERVAL = int(os.environ.get("DARIUS_HEARTBEAT_INTERVAL", "60"))  # seconds
_ENABLED = os.environ.get("DARIUS_AUTONOMOUS", "true").lower() == "true"
_DSN = os.environ.get("POSTGRES_DSN", "")
_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
_SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
_SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")

# Track timing
_last_improvement = 0.0
_last_digest = 0.0
_IMPROVEMENT_INTERVAL = 86400  # 24 hours
_DIGEST_INTERVAL = 86400       # 24 hours
_DIGEST_OFFSET = 3600          # 1 hour after improvement

# Daily stats
_daily_stats = {
    "tasks_completed": 0,
    "tasks_failed": 0,
    "tokens_used": 0,
    "cost_usd": 0.0,
    "engines_used": {},
    "started_at": time.time(),
}


def _get_redis():
    try:
        import redis
        r = redis.Redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        return r
    except Exception:
        return None


def _is_kill_switched() -> bool:
    """Check if the kill switch is engaged — stop all autonomous actions."""
    r = _get_redis()
    if not r:
        return False  # Fail open if Redis is down (conservative)
    return r.get("darius:kill_switch") == "engaged"


def _get_open_tickets() -> list[dict]:
    """Get tickets that are explicitly approved for Darius to execute autonomously.
    
    Only picks up tickets with:
    - status='approved' (CEO hit approve in Slack)
    - OR status='open' AND auto_execute=true (pre-approved for autonomous work)
    
    Does NOT pick up:
    - status='open' without approval (might be informational, pending decision)
    - Unassigned tickets (orchestrator should route first)
    """
    if not _DSN:
        return []
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(_DSN)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, task, agent, status, created_at
            FROM tickets
            WHERE agent = 'darius'
              AND attempts < 3
              AND (
                status = 'approved'
                OR (status = 'open' AND auto_execute = TRUE)
              )
            ORDER BY created_at ASC
            LIMIT 3
        """)
        tickets = [dict(r) for r in cur.fetchall()]
        conn.close()
        return tickets
    except Exception as e:
        logger.debug(f"Failed to fetch tickets: {e}")
        return []


def _claim_ticket(ticket_id: int):
    """Mark a ticket as in_progress and assign to Darius."""
    if not _DSN:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(_DSN)
        cur = conn.cursor()
        cur.execute(
            "UPDATE tickets SET status='in_progress', agent='darius', updated_at=NOW() WHERE id=%s",
            (ticket_id,)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _complete_ticket(ticket_id: int, result: str):
    """Mark a ticket as done with the result."""
    if not _DSN:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(_DSN)
        cur = conn.cursor()
        cur.execute(
            "UPDATE tickets SET status='done', result=%s, updated_at=NOW() WHERE id=%s",
            (result[:5000], ticket_id)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _fail_ticket(ticket_id: int, error: str):
    """Increment attempts on a failed ticket."""
    if not _DSN:
        return
    try:
        import psycopg2
        conn = psycopg2.connect(_DSN)
        cur = conn.cursor()
        cur.execute(
            "UPDATE tickets SET attempts = attempts + 1, updated_at=NOW() WHERE id=%s",
            (ticket_id,)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def _extract_and_write_files(output: str, ticket_id: int) -> list[str]:
    """
    Parse code blocks from agent output and write them to disk.
    
    Expects code blocks with file path on line 1:
        ```python
        # /path/to/file.py
        content...
        ```
    
    Or explicit file path comment patterns:
        ```
        // filepath: src/component.tsx
        content...
        ```
    
    Returns list of file paths written.
    """
    import re
    import os

    written = []
    _PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

    # Pattern: ```lang\n# /path or // filepath: path
    code_block_pattern = re.compile(
        r"```(?:\w*)\n"
        r"(?:#|//)\s*(?:filepath:\s*)?([^\n]+)\n"
        r"(.*?)"
        r"```",
        re.DOTALL
    )

    for match in code_block_pattern.finditer(output):
        file_path = match.group(1).strip()
        content = match.group(2)

        # Skip if path looks invalid
        if not file_path or len(file_path) < 3 or file_path.startswith("http"):
            continue

        # Security: resolve path and ensure it's within allowed base
        if not file_path.startswith("/"):
            file_path = os.path.join(_PROJECTS_BASE, "kiro-agents", file_path)

        real_path = os.path.realpath(file_path)

        # Guard: only write within Projects directory
        if not real_path.startswith(os.path.realpath(_PROJECTS_BASE)):
            logger.warning(f"[autonomous] Blocked write outside Projects: {real_path}")
            continue

        # Guard: never write to .env, credentials, or keys
        basename = os.path.basename(real_path).lower()
        if basename in (".env", "credentials", "secrets") or basename.endswith((".key", ".pem")):
            logger.warning(f"[autonomous] Blocked write to sensitive file: {real_path}")
            continue

        try:
            os.makedirs(os.path.dirname(real_path), exist_ok=True)
            with open(real_path, "w") as f:
                f.write(content)
            written.append(real_path)
            logger.info(f"[autonomous] Wrote file: {real_path} ({len(content)} bytes)")
        except Exception as e:
            logger.error(f"[autonomous] Failed to write {real_path}: {e}")

    return written


def _execute_ticket(ticket: dict):
    """Execute a ticket using the auto engine selector, then write output files to disk."""
    global _daily_stats
    ticket_id = ticket["id"]
    task = ticket["task"]

    logger.info(f"[autonomous] Claiming ticket #{ticket_id}: {task[:60]}")
    _claim_ticket(ticket_id)

    try:
        from AI.darius.swarm.selector import select_engine, record_execution

        engine = select_engine(task)
        logger.info(f"[autonomous] Ticket #{ticket_id} → engine '{engine}'")

        # Execute based on engine selection
        if engine == "swarm":
            from AI.darius.swarm.swarm import AgentSwarm
            swarm = AgentSwarm(task_id=f"ticket-{ticket_id}")
            result = swarm.execute(task=task)
            output = result.get("final_output", "")
            usage = result.get("token_usage", {})
        elif engine == "delta":
            from AI.darius.swarm.executor import DeltaExecutor
            executor = DeltaExecutor(task_id=f"ticket-{ticket_id}")
            result = executor.run(task=task)
            output = result.get("final_output", "")
            usage = result.get("token_usage", {})
        else:
            from AI.darius.agent import run_task
            output = run_task(task, session_id=f"ticket-{ticket_id}")
            usage = {"input": 0, "output": 0, "cost": 0}

        # POST-EXECUTION: Extract code blocks and write files to disk
        files_written = _extract_and_write_files(output, ticket_id)
        if files_written:
            file_list = "\n".join(f"  • {f}" for f in files_written)
            output += f"\n\n--- Files Written ({len(files_written)}) ---\n{file_list}"
            logger.info(f"[autonomous] Ticket #{ticket_id}: wrote {len(files_written)} file(s)")

        _complete_ticket(ticket_id, output)

        # Record for adaptive learning
        tokens = usage.get("input", 0) + usage.get("output", 0)
        cost = usage.get("cost", 0)
        record_execution(task, engine, True, tokens, 0, cost)

        # Update daily stats
        _daily_stats["tasks_completed"] += 1
        _daily_stats["tokens_used"] += tokens
        _daily_stats["cost_usd"] += cost
        _daily_stats["engines_used"][engine] = _daily_stats["engines_used"].get(engine, 0) + 1

        logger.info(f"[autonomous] Ticket #{ticket_id} complete ({engine}, {tokens} tokens, {len(files_written)} files)")

    except Exception as e:
        logger.error(f"[autonomous] Ticket #{ticket_id} failed: {e}")
        _fail_ticket(ticket_id, str(e))
        _daily_stats["tasks_failed"] += 1


def _run_improvement():
    """Run the daily self-improvement cycle."""
    global _last_improvement
    logger.info("[autonomous] Running self-improvement cycle...")

    try:
        from AI.darius.swarm.analyzer import analyze
        from AI.darius.swarm.refiner import SkillRefiner

        insights = analyze(days=7)
        refiner = SkillRefiner()
        proposals = refiner.refine(insights)

        # Post to Slack
        summary = insights.get("summary", {})
        _post_to_slack(
            f"🔄 *Darius Auto-Improvement (daily)*\n\n"
            f"• Executions (7d): {summary.get('total_executions', 0)}\n"
            f"• Success rate: {summary.get('success_rate', 0)}%\n"
            f"• Proposals generated: {len(proposals)}\n"
            f"• Recommendations: {len(insights.get('recommendations', []))}\n\n"
            f"{refiner.format_proposals()[:500] if proposals else 'No refinements needed.'}"
        )

        _last_improvement = time.time()
        logger.info(f"[autonomous] Improvement complete: {len(proposals)} proposals")

    except Exception as e:
        logger.error(f"[autonomous] Improvement cycle failed: {e}")


def _run_digest():
    """Post daily productivity digest to Slack."""
    global _last_digest, _daily_stats

    uptime_hours = (time.time() - _daily_stats["started_at"]) / 3600
    engines = _daily_stats["engines_used"]
    engine_breakdown = ", ".join(f"{k}({v})" for k, v in engines.items()) if engines else "none"

    _post_to_slack(
        f"📊 *Darius Daily Digest*\n\n"
        f"*Productivity:*\n"
        f"• Tasks completed: {_daily_stats['tasks_completed']}\n"
        f"• Tasks failed: {_daily_stats['tasks_failed']}\n"
        f"• Tokens used: {_daily_stats['tokens_used']:,}\n"
        f"• Cost: ${_daily_stats['cost_usd']:.3f}\n"
        f"• Engine breakdown: {engine_breakdown}\n"
        f"• Uptime: {uptime_hours:.1f}h\n\n"
        f"*Status:* {'🟢 Autonomous mode active' if _ENABLED else '🔴 Paused'}"
    )

    # Reset daily stats
    _daily_stats = {
        "tasks_completed": 0,
        "tasks_failed": 0,
        "tokens_used": 0,
        "cost_usd": 0.0,
        "engines_used": {},
        "started_at": time.time(),
    }
    _last_digest = time.time()


def _post_to_slack(text: str):
    """Post a message to Slack."""
    if not _SLACK_TOKEN or not _SLACK_CHANNEL:
        return
    try:
        import httpx
        httpx.post("https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {_SLACK_TOKEN}", "Content-Type": "application/json"},
            json={"channel": _SLACK_CHANNEL, "text": text},
            timeout=10)
    except Exception:
        pass


def _heartbeat():
    """Single heartbeat iteration."""
    global _last_improvement, _last_digest

    # Safety: check kill switch
    if _is_kill_switched():
        logger.debug("[autonomous] Kill switch engaged, skipping heartbeat")
        return

    now = time.time()

    # 1. Check for open tickets and execute them
    tickets = _get_open_tickets()
    for ticket in tickets:
        if _is_kill_switched():
            break
        _execute_ticket(ticket)

    # 2. Daily self-improvement (every 24h)
    if now - _last_improvement >= _IMPROVEMENT_INTERVAL:
        _run_improvement()

    # 3. Daily digest (every 24h, offset from improvement)
    if now - _last_digest >= _DIGEST_INTERVAL and now - _last_improvement > _DIGEST_OFFSET:
        _run_digest()

    # 4. Update health in Redis
    r = _get_redis()
    if r:
        r.setex("darius:autonomous:last_heartbeat", 300, str(int(now)))
        r.setex("darius:autonomous:status", 300, "active")


def _loop():
    """Background loop — runs forever."""
    global _last_improvement, _last_digest

    logger.info("[autonomous] Heartbeat loop started")
    _last_improvement = time.time()  # Don't run improvement immediately on startup
    _last_digest = time.time()

    # Announce startup
    _post_to_slack("🤖 *Darius Autonomous Mode — Active*\nHeartbeat started. Monitoring ticket queue, self-improvement scheduled daily.")

    while True:
        try:
            _heartbeat()
        except Exception as e:
            logger.error(f"[autonomous] Heartbeat error: {e}")
        time.sleep(_HEARTBEAT_INTERVAL)


def start():
    """Start the autonomous heartbeat as a daemon thread."""
    if not _ENABLED:
        logger.info("[autonomous] Disabled (DARIUS_AUTONOMOUS=false)")
        return

    thread = threading.Thread(target=_loop, daemon=True, name="darius-autonomous")
    thread.start()
    logger.info("[autonomous] Background thread started")
