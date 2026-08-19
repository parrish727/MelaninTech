import uuid
import threading
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config.settings import SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_CHANNEL_ID
from orchestrator.router import route
from orchestrator.approval import request_approval, handle_approval, handle_modify_submit
from orchestrator.memory import store_conversation
from orchestrator import watchdog

app = App(token=SLACK_BOT_TOKEN)


def _estimate_eta(task: str) -> str:
    """Rough ETA based on task complexity."""
    words = len(task.split())
    if any(k in task.lower() for k in ["rebuild", "entire", "all", "full", "redesign"]):
        return "3–5 min"
    if words > 40:
        return "2–3 min"
    if words > 15:
        return "1–2 min"
    return "30–60 sec"


def process_task(task: str, project: str, say, ticket_type: str = "client"):
    callback_id = str(uuid.uuid4())

    # Immediate acknowledgment (with DNS retry)
    eta = _estimate_eta(task)
    _slack_post_with_retry(
        app,
        SLACK_CHANNEL_ID,
        f"⏳ *Task received* — routing to agent for `{project}`\n*ETA:* {eta}\n> {task[:120]}{'...' if len(task) > 120 else ''}",
    )

    try:
        store_conversation("user", f"[{project}] {task}")
    except Exception:
        pass  # non-blocking — don't fail the task if memory write fails

    try:
        proposal = route(task, project, callback_id=callback_id)
    except Exception as e:
        _slack_post_with_retry(app, SLACK_CHANNEL_ID, f"⚠️ Agent error: {e}")
        return

    # deploy_complete means the agent already executed — no approval needed
    if proposal.get("action") == "deploy_complete":
        _slack_post_with_retry(app, SLACK_CHANNEL_ID, proposal.get("result", "✅ Deploy complete."))
        return

    proposal["_ticket_type"] = ticket_type
    request_approval(app, SLACK_CHANNEL_ID, task, proposal, callback_id)


def _slack_post_with_retry(app, channel: str, text: str, max_retries: int = 3):
    """Post a simple text message to Slack with DNS/network retry."""
    import time
    for attempt in range(max_retries):
        try:
            app.client.chat_postMessage(channel=channel, text=text)
            return
        except Exception as e:
            if attempt < max_retries - 1 and ("Name or service not known" in str(e) or "Connection" in str(e)):
                time.sleep(2 ** attempt)
                continue
            raise


@app.command("/task")
def handle_task(ack, body, say):
    ack()
    _process_task_command(body, say, ticket_type="client")


@app.command("/task-internal")
def handle_internal_task(ack, body, say):
    ack()
    _process_task_command(body, say, ticket_type="internal")


def _process_task_command(body, say, ticket_type: str):
    text = body.get("text", "").strip()
    if not text:
        say("Usage: `/task <project>: <description>`")
        return
    if ":" in text:
        project, task = [s.strip() for s in text.split(":", 1)]
    else:
        project, task = "default", text

    # Deduplicate task text — Slack sometimes double-sends or pastes duplicate content
    task = _deduplicate_task_text(task)

    threading.Thread(target=process_task, args=(task, project, say, ticket_type), daemon=True).start()


def _deduplicate_task_text(text: str) -> str:
    """Detect and remove duplicated content in task text.
    Handles cases where the same bullet list is pasted twice."""
    lines = text.strip().split("\n")
    if len(lines) < 4:
        return text

    # Check if the second half is a repeat of the first half
    mid = len(lines) // 2
    first_half = "\n".join(lines[:mid]).strip()
    second_half = "\n".join(lines[mid:]).strip()

    if first_half == second_half:
        return first_half

    # Also check if there's a repeated block (e.g. same N lines appear twice)
    # by looking for the longest repeated prefix
    for split_point in range(mid - 1, max(2, mid - 5), -1):
        candidate = "\n".join(lines[:split_point]).strip()
        remainder = "\n".join(lines[split_point:]).strip()
        if candidate == remainder:
            return candidate

    return text


@app.command("/tickets")
def handle_tickets(ack, body, say):
    ack()
    from orchestrator.tickets import list_tickets
    text = body.get("text", "").strip()
    parts = text.split() if text else []
    client = parts[0] if len(parts) > 0 else None
    status = parts[1] if len(parts) > 1 else None
    ticket_type = parts[2] if len(parts) > 2 else None
    tickets = list_tickets(client=client, status=status, ticket_type=ticket_type)
    if not tickets:
        say("No tickets found.")
        return
    lines = [f"*#{t['id']}* [{t['status'].upper()}] [{t['type'].upper()}] `{t['client']}` — {t['task'][:80]}" for t in tickets]
    say("*📋 Tickets:*\n" + "\n".join(lines))


@app.command("/agent-status")
def handle_status(ack, body, say):
    ack()
    from orchestrator.tickets import list_tickets
    tickets = list_tickets()
    if not tickets:
        say("No tickets found.")
        return
    latest = tickets[0]
    status_emoji = {"open": "🟡", "in_progress": "🔵", "done": "✅", "rejected": "❌", "cancelled": "⛔"}.get(latest["status"], "⚪")
    say(
        f"{status_emoji} *Latest Ticket #{latest['id']}*\n"
        f"*Status:* {latest['status'].upper()}\n"
        f"*Project:* `{latest['client']}`\n"
        f"*Agent:* {latest.get('agent', 'unknown')}\n"
        f"*Task:* {latest['task'][:200]}"
    )


@app.action("approve")
def on_approve(ack, body, action, say):
    handle_approval(ack, body, action, say, app)


@app.action("reject")
def on_reject(ack, body, action, say):
    handle_approval(ack, body, action, say, app)


@app.action("destructive_approve")
def on_destructive_approve(ack, body, action, say):
    ack()
    from agents.deploy_agent import handle_destructive_decision
    approval_id = action["value"]
    handle_destructive_decision(approval_id, True)
    say(f"✅ Destructive operation approved (ID: {approval_id})")


@app.action("destructive_deny")
def on_destructive_deny(ack, body, action, say):
    ack()
    from agents.deploy_agent import handle_destructive_decision
    approval_id = action["value"]
    handle_destructive_decision(approval_id, False)
    say(f"❌ Destructive operation denied (ID: {approval_id})")


@app.action("modify")
def on_modify(ack, body, action):
    ack()
    from orchestrator.approval import open_modify_modal
    open_modify_modal(app, body["trigger_id"], action["value"])


@app.action("deploy_production")
def on_deploy_production(ack, body, action):
    ack()
    from orchestrator.deploy_pipeline import deploy_to_production
    import threading
    threading.Thread(target=deploy_to_production, args=(app,), daemon=True).start()


@app.action("skip_production")
def on_skip_production(ack, body, action):
    ack()
    app.client.chat_postMessage(channel=SLACK_CHANNEL_ID, text="⏭️ Production deploy skipped.")


@app.action("security_kill_switch_approve")
def on_kill_switch_approve(ack, body, action):
    ack()
    import subprocess
    result = subprocess.run(
        ["python3", "scripts/vault_sync.py", "--lock", "Approved via Slack security alert"],
        capture_output=True, text=True, cwd="/app"
    )
    app.client.chat_postMessage(
        channel=SLACK_CHANNEL_ID,
        text="🔴 *Kill Switch Engaged* — `.env` wiped. Services will lose credentials on next restart.\nTo restore: `python3 scripts/vault_sync.py --unlock`"
    )


@app.action("security_kill_switch_dismiss")
def on_kill_switch_dismiss(ack, body, action):
    ack()
    app.client.chat_postMessage(
        channel=SLACK_CHANNEL_ID,
        text="✅ Security alert dismissed — classified as false positive. Monitoring continues."
    )


@app.view_submission("modify_submit")
def on_modify_submit(ack, body, view, say):
    handle_modify_submit(ack, body, view, say, app)


# ── Mobile-friendly: trigger tasks via @mention ───────────────────────────────
# Usage: @Kiro task project: description
#        @Kiro tickets
#        @Kiro status
@app.event("app_mention")
def handle_mention(event, say):
    text = event.get("text", "")
    # Strip the bot mention (<@BOTID>)
    import re
    text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()

    if not text:
        say("👋 Mention me with a command:\n• `@Kiro task project: description`\n• `@Kiro tickets`\n• `@Kiro status`")
        return

    cmd = text.split()[0].lower()

    if cmd == "task":
        task_text = text[len("task"):].strip()
        if ":" in task_text:
            project, task = [s.strip() for s in task_text.split(":", 1)]
        else:
            project, task = "default", task_text
        threading.Thread(target=process_task, args=(task, project, say, "client"), daemon=True).start()

    elif cmd == "tickets":
        from orchestrator.tickets import list_tickets
        tickets = list_tickets()
        if not tickets:
            say("No tickets found.")
            return
        lines = [f"*#{t['id']}* [{t['status'].upper()}] `{t['client']}` — {t['task'][:80]}" for t in tickets]
        say("*📋 Tickets:*\n" + "\n".join(lines))

    elif cmd == "status":
        from orchestrator.tickets import list_tickets
        tickets = list_tickets()
        if not tickets:
            say("No tickets found.")
            return
        latest = tickets[0]
        status_emoji = {"open": "🟡", "in_progress": "🔵", "done": "✅", "rejected": "❌", "cancelled": "⛔"}.get(latest["status"], "⚪")
        say(f"{status_emoji} *Ticket #{latest['id']}* — {latest['status'].upper()} — `{latest['client']}` — {latest['task'][:200]}")

    else:
        say(f"🤔 Unknown command `{cmd}`. Try:\n• `@Kiro task project: description`\n• `@Kiro tickets`\n• `@Kiro status`")


@app.event("message")
def handle_message(event, say):
    """Catch messages that mention the bot (works in channels and DMs)."""
    import re
    text = event.get("text", "")
    # Skip bot's own messages
    if event.get("bot_id") or event.get("subtype"):
        return
    # Strip bot mention if present
    text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()
    if not text:
        return

    cmd = text.split()[0].lower()

    if cmd == "task":
        task_text = text[len("task"):].strip()
        if ":" in task_text:
            project, task = [s.strip() for s in task_text.split(":", 1)]
        else:
            project, task = "default", task_text
        if task:
            threading.Thread(target=process_task, args=(task, project, say, "client"), daemon=True).start()
        else:
            say("Usage: `task project: description`")

    elif cmd == "tickets":
        from orchestrator.tickets import list_tickets
        tickets = list_tickets()
        if not tickets:
            say("No tickets found.")
            return
        lines = [f"*#{t['id']}* [{t['status'].upper()}] `{t['client']}` — {t['task'][:80]}" for t in tickets]
        say("*📋 Tickets:*\n" + "\n".join(lines))

    elif cmd == "status":
        from orchestrator.tickets import list_tickets
        tickets = list_tickets()
        if not tickets:
            say("No tickets found.")
            return
        latest = tickets[0]
        status_emoji = {"open": "🟡", "in_progress": "🔵", "done": "✅", "rejected": "❌", "cancelled": "⛔"}.get(latest["status"], "⚪")
        say(f"{status_emoji} *Ticket #{latest['id']}* — {latest['status'].upper()} — `{latest['client']}` — {latest['task'][:200]}")

    elif cmd in ("help", "hi", "hello"):
        say("👋 Commands:\n• `task project: description` — submit a task\n• `tickets` — list all tickets\n• `status` — latest ticket")


if __name__ == "__main__":
    # Start the deploy webhook listener (HTTP) alongside Slack (Socket Mode)
    from orchestrator.deploy_webhook import start_webhook_server
    start_webhook_server(app, SLACK_CHANNEL_ID)

    watchdog.init(app, SLACK_CHANNEL_ID)
    watchdog.start()
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    print("⚡ Kiro Orchestrator is running...")
    handler.start()
