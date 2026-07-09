"""
Watchdog — background thread that monitors in_progress tickets for stuck agents.

Per-agent timeouts (seconds):
  file: 30, code: 120, support: 120, backend: 180, frontend: 180,
  scaffold: 300, deploy: 600

Lifecycle:
  stuck → retry (up to MAX_ATTEMPTS=9)
       → failed_backlog  (non-urgent, exhausted retries)
       → failed_urgent   (urgent, stays visible, never backlogged)
"""
import threading
import time
import logging
from datetime import datetime, timezone

from orchestrator.tickets import get_stuck_tickets, update_ticket, increment_attempts, MAX_ATTEMPTS

log = logging.getLogger(__name__)

AGENT_TIMEOUTS = {
    "file": 30,
    "code": 120,
    "support": 120,
    "backend": 180,
    "frontend": 180,
    "scaffold": 300,
    "deploy": 600,
}
DEFAULT_TIMEOUT = 180
POLL_INTERVAL = 30
STATUS_INTERVAL = 18000
REPORT_WINDOW_HOURS = 12

# agent name → docker compose container name
AGENT_CONTAINER_MAP = {
    "file":     "docker-file-agent-1",
    "code":     "docker-code-agent-1",
    "support":  "docker-support-agent-1",
    "backend":  "docker-backend-agent-1",
    "frontend": "docker-frontend-agent-1",
    "scaffold": "docker-scaffold-agent-1",
    "deploy":   "docker-deploy-agent-1",
    "website":  "docker-melanin-website-1",
}

_slack_app = None
_slack_channel = None
_docker = None


def init(app, channel: str):
    global _slack_app, _slack_channel, _docker
    _slack_app = app
    _slack_channel = channel
    try:
        import docker
        _docker = docker.from_env()
        log.info("Watchdog: Docker client connected.")
    except Exception as e:
        log.warning(f"Watchdog: Docker unavailable — container restart disabled. {e}")


def _restart_container(agent: str) -> str | None:
    """Restart the agent's container. Returns container name on success, None on failure."""
    if not _docker:
        return None
    container_name = AGENT_CONTAINER_MAP.get(agent)
    if not container_name:
        return None
    try:
        container = _docker.containers.get(container_name)
        container.restart(timeout=10)
        log.info(f"Watchdog: restarted container {container_name}")
        return container_name
    except Exception as e:
        log.warning(f"Watchdog: failed to restart {container_name}: {e}")
        return None


def _notify(msg: str):
    if _slack_app and _slack_channel:
        try:
            _slack_app.client.chat_postMessage(channel=_slack_channel, text=msg)
        except Exception as e:
            log.warning(f"Watchdog Slack notify failed: {e}")


def _handle_stuck(ticket: dict):
    callback_id = ticket["callback_id"]
    agent = ticket.get("agent", "unknown")
    task_preview = ticket["task"][:60]
    priority = ticket.get("priority", "normal")
    attempts = increment_attempts(callback_id)

    if attempts < MAX_ATTEMPTS:
        update_ticket(callback_id, "open",
                      f"watchdog: attempt {attempts}/{MAX_ATTEMPTS} — restarting container and requeueing")

        restarted = _restart_container(agent)
        container_note = f"container `{restarted}` restarted" if restarted else "container restart unavailable"

        _notify(
            f"⚠️ *Watchdog* — `{agent}` stuck on ticket `{callback_id}`\n"
            f"Task: _{task_preview}_\n"
            f"Attempt {attempts}/{MAX_ATTEMPTS} — {container_note}, requeueing task."
        )
        _retry(ticket)
    else:
        # exhausted retries
        if priority == "urgent":
            update_ticket(callback_id, "failed_urgent",
                          "watchdog: max attempts reached — marked failed_urgent")
            _notify(
                f"🚨 *URGENT TICKET FAILED* — `{callback_id}`\n"
                f"Agent: `{agent}` | Task: _{task_preview}_\n"
                f"Exhausted {MAX_ATTEMPTS} attempts. Requires manual intervention."
            )
        else:
            update_ticket(callback_id, "failed_backlog",
                          "watchdog: max attempts reached — moved to backlog")
            _notify(
                f"🗂️ *Ticket moved to backlog* — `{callback_id}`\n"
                f"Agent: `{agent}` | Task: _{task_preview}_\n"
                f"Exhausted {MAX_ATTEMPTS} attempts."
            )


def _retry(ticket: dict):
    """Spin up a fresh agent call for the ticket without blocking the watchdog."""
    import threading
    from orchestrator.router import route
    from orchestrator.approval import request_approval

    def _run():
        try:
            task = ticket["task"]
            project = ticket.get("client", "default")
            proposal = route(task, project)
            proposal["_ticket_type"] = ticket.get("type", "client")
            if _slack_app and _slack_channel:
                request_approval(_slack_app, _slack_channel, task, proposal, ticket["callback_id"])
        except Exception as e:
            update_ticket(ticket["callback_id"], "open",
                          f"watchdog retry failed to route: {e}")
            log.error(f"Watchdog retry error for {ticket['callback_id']}: {e}")

    threading.Thread(target=_run, daemon=True).start()


def _sweep():
    """Check all agent timeout buckets and handle stuck tickets."""
    for agent, timeout in AGENT_TIMEOUTS.items():
        try:
            stuck = get_stuck_tickets(timeout)
            for ticket in stuck:
                if ticket.get("agent") == agent:
                    log.info(f"Watchdog: stuck ticket {ticket['callback_id']} agent={agent}")
                    _handle_stuck(ticket)
        except Exception as e:
            log.error(f"Watchdog sweep error for {agent}: {e}")

    # catch-all for agents not in the map
    try:
        stuck = get_stuck_tickets(DEFAULT_TIMEOUT)
        for ticket in stuck:
            if ticket.get("agent") not in AGENT_TIMEOUTS:
                _handle_stuck(ticket)
    except Exception as e:
        log.error(f"Watchdog catch-all sweep error: {e}")


def _status_digest():
    """Post a 12-hour activity report to Slack every 5 hours."""
    from orchestrator.tickets import list_tickets, _get_conn
    from psycopg2.extras import RealDictCursor

    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT status, agent, task, attempts, priority, updated_at
               FROM tickets
               WHERE updated_at >= NOW() - INTERVAL '%s hours'
               ORDER BY updated_at DESC""",
            (REPORT_WINDOW_HOURS,),
        )
        rows = cur.fetchall()

    if not rows:
        _notify(f"*🤖 Watchdog — {REPORT_WINDOW_HOURS}hr Report*\n\nNo ticket activity in the last {REPORT_WINDOW_HOURS} hours.")
        return

    buckets = {"done": [], "in_progress": [], "open": [], "failed_urgent": [], "failed_backlog": [], "rejected": []}
    for r in rows:
        buckets.setdefault(r["status"], []).append(r)

    lines = [f"*🤖 Watchdog — {REPORT_WINDOW_HOURS}hr Report*\n"]

    emoji_map = {
        "done": "✅", "in_progress": "⚙️", "open": "🕐",
        "failed_urgent": "🚨", "failed_backlog": "🗂️", "rejected": "❌",
    }
    for status, items in buckets.items():
        if not items:
            continue
        lines.append(f"{emoji_map.get(status, '•')} *{status.replace('_', ' ').title()}* ({len(items)})")
        for t in items[:5]:  # cap at 5 per bucket to keep it readable
            lines.append(f"  • `{t['agent']}` — {t['task'][:70]}")
        if len(items) > 5:
            lines.append(f"  _...and {len(items) - 5} more_")

    lines.append(f"\n_Total activity: {len(rows)} tickets in last {REPORT_WINDOW_HOURS}hrs_")
    _notify("\n".join(lines))


def start():
    """Start the watchdog background thread."""
    def _loop():
        log.info("Watchdog started.")
        last_digest = 0
        while True:
            time.sleep(POLL_INTERVAL)
            _sweep()
            # Check for monitoring gaps (HUD snapshots, SLA tracking)
            check_monitoring_gaps(_slack_app, _slack_channel)
            if time.time() - last_digest >= STATUS_INTERVAL:
                try:
                    _status_digest()
                except Exception as e:
                    log.error(f"Watchdog digest error: {e}")
                last_digest = time.time()

    t = threading.Thread(target=_loop, daemon=True, name="watchdog")
    t.start()
    return t


# ── Monitoring Gap Detection ──────────────────────────────────────────────────
# Runs every 15 minutes alongside the stuck ticket check.
# If health snapshots stop for >15 min, alerts Slack and auto-restarts HUD.

import os
import psycopg2

_last_gap_check = 0
_GAP_CHECK_INTERVAL = 900  # 15 minutes
_GAP_ALERT_THRESHOLD = 900  # alert if no snapshot in 15 min


def check_monitoring_gaps(app, channel):
    """Verify HUD is recording health snapshots. Auto-fix if not."""
    global _last_gap_check
    import time as _time
    now = _time.time()

    if now - _last_gap_check < _GAP_CHECK_INTERVAL:
        return
    _last_gap_check = now

    try:
        dsn = os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro")
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("SELECT created_at FROM health_snapshots ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()

        if not row:
            _alert_and_fix(app, channel, "No health snapshots found in database")
            return

        from datetime import datetime, timezone
        last_snapshot = row[0]
        if last_snapshot.tzinfo is None:
            last_snapshot = last_snapshot.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - last_snapshot).total_seconds()

        if age_seconds > _GAP_ALERT_THRESHOLD:
            _alert_and_fix(app, channel, f"Last health snapshot was {int(age_seconds / 60)} minutes ago")

    except Exception as e:
        log.error(f"Monitoring gap check failed: {e}")


def _alert_and_fix(app, channel, reason):
    """Alert Slack and restart the HUD container to restore monitoring."""
    import subprocess

    log.warning(f"Monitoring gap detected: {reason}")

    # Alert
    try:
        app.client.chat_postMessage(
            channel=channel,
            text=(
                f"🔴 *Monitoring Gap Detected*\n"
                f"*Issue:* {reason}\n"
                f"*Action:* Auto-restarting HUD health monitor\n"
                f"*SLA Impact:* Gap in uptime tracking data"
            ),
        )
    except Exception:
        pass

    # Auto-fix: restart HUD container
    try:
        result = subprocess.run(
            ["docker", "restart", "docker-hud-1"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            try:
                app.client.chat_postMessage(
                    channel=channel,
                    text="✅ HUD container restarted. Monitoring should resume within 5 minutes.",
                )
            except Exception:
                pass
        else:
            log.error(f"HUD restart failed: {result.stderr}")
    except Exception as e:
        log.error(f"Auto-fix failed: {e}")
