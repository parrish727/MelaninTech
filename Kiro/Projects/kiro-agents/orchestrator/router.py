import httpx
from config.settings import AGENT_URLS
from orchestrator.contracts import check, consume_ticket
from orchestrator.template_engine import parse_template_command, load_template, resolve_template, list_templates

# Initialize distributed tracing
try:
    from integrations.tracing import init_tracing, traced, span, get_trace_id, add_span_attributes
    init_tracing("orchestrator", version="2.0.0")
except Exception:
    def traced(name=None, attributes=None):
        def decorator(func):
            return func
        return decorator

    def get_trace_id():
        return "no-trace"

    def add_span_attributes(**kw):
        pass


def _resolve_ticket_references(task: str) -> str:
    """If the task references another ticket (e.g. 'Ticket #58'), fetch that ticket's
    full task text and prepend it as context so the executing agent has everything it needs."""
    import re
    import os
    import psycopg2
    from psycopg2.extras import RealDictCursor

    refs = re.findall(r"(?:ticket\s*#?|#)(\d+)", task.lower())
    if not refs:
        return task

    ticket_ids = sorted(set(int(t) for t in refs))
    context_parts = []
    try:
        dsn = os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro")
        conn = psycopg2.connect(dsn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        for tid in ticket_ids:
            cur.execute("SELECT id, task, proposal FROM tickets WHERE id = %s", (tid,))
            row = cur.fetchone()
            if row:
                context_parts.append(
                    f"--- Referenced Ticket #{row['id']} ---\n"
                    f"{row['task']}\n"
                    + (f"\nProposal:\n{row['proposal']}" if row.get("proposal") else "")
                )
        conn.close()
    except Exception:
        return task  # fail gracefully — use original task if DB unavailable

    if not context_parts:
        return task

    return "\n\n".join(context_parts) + f"\n\n--- Current Instruction ---\n{task}"


@traced("orchestrator.route", attributes={"component": "router"})
def route(task: str, project: str = "default", callback_id: str = None) -> dict:
    # Resolve ticket references so agents get full context
    enriched_task = _resolve_ticket_references(task)

    # Check if this is a template command first
    trigger, params = parse_template_command(enriched_task)
    if trigger:
        template = load_template(trigger)
        if template:
            steps = resolve_template(template, params)
            return {
                "agent": "TemplateEngine",
                "model": "none",
                "action": "template",
                "description": f"Template: {template.name} ({len(steps)} steps)",
                "args": {
                    "task": enriched_task,
                    "project": project,
                    "template": trigger,
                    "steps": steps,
                    "proposal": _format_template_proposal(template, steps),
                },
            }

    # IMPORTANT: Classify based on the ORIGINAL user instruction, not the expanded
    # ticket context. The expanded text may contain keywords (like "POST", "deploy",
    # "send") that are part of the ticket's technical description, not the user's intent.
    # The enriched_task is passed to the executing agent for full context.
    task_lower = task.lower()

    # "list templates" command
    if task_lower.strip() in ("list templates", "templates", "show templates"):
        templates = list_templates()
        listing = "\n".join(f"• `{t['trigger']}` — {t['description']}" for t in templates)
        return {
            "agent": "TemplateEngine",
            "model": "none",
            "action": "info",
            "description": "Available templates",
            "args": {"task": enriched_task, "project": project, "proposal": f"Available workflow templates:\n\n{listing}"},
        }

    agent_type = _classify(task_lower)

    # Orchestrator-handled tasks — no external agent needed
    if agent_type == "orchestrator":
        # Determine if it's email or Slack
        if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", task_lower):
            return _handle_email(enriched_task, project, callback_id)
        return _handle_slack_post(enriched_task, project, callback_id)

    if agent_type == "file_write":
        return _handle_file_write(enriched_task, project, callback_id)

    # Support requests require an active contract
    if agent_type == "support":
        status = check(project)
        if not status["allowed"]:
            raise ValueError(f"Support unavailable for '{project}': {status['reason']}")
        consume_ticket(project)

    url = AGENT_URLS[agent_type]
    # Darius may retry on rate limits — give it more time
    timeout = 600 if agent_type == "darius" else 300
    response = httpx.post(
        f"{url}/task",
        json={"task": enriched_task, "project": project, "callback_id": callback_id},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


import re
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def _word_match(keywords: list[str], text: str) -> bool:
    """Match keywords with word boundaries to avoid substring false positives."""
    for k in keywords:
        if ' ' in k:
            # Multi-word phrases: simple contains is fine
            if k in text:
                return True
        else:
            # Single words: require word boundary
            if re.search(r'\b' + re.escape(k) + r'\b', text):
                return True
    return False


def _classify(task_lower: str) -> str:
    if _word_match(["darius", "agent loop", "agentic", "multi-step", "autonomously", "figure out", "analyze", "plan", "strategy"], task_lower):
        return "darius"

    # Orchestrator-handled tasks (Slack posting, ticket output sharing)
    if _word_match(["post in slack", "post to slack", "send to slack", "post in <#", "post to <#", "post content", "output in <#", "share in <#", "post the output", "post this in", "send this to <#", "post this doc", "post the content", "send this to", "share this in"], task_lower):
        return "orchestrator"
    # Also catch any task with a Slack channel reference + posting intent
    if re.search(r"<#C[A-Z0-9]+", task_lower) and _word_match(["post", "send", "share", "output", "content"], task_lower):
        return "orchestrator"

    # Email tasks — orchestrator handles (has SMTP access)
    if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", task_lower) and _word_match(["email", "send", "mail", "forward"], task_lower):
        return "orchestrator"

    # File creation tasks with specific save paths → orchestrator handles directly
    if _word_match(["save to", "save into", "save in", "save as", "save this"], task_lower) and _word_match(["folder", "directory", "path", "orthodontic", "linesofbusiness", "melanindocs", "orthoflow", "markdown"], task_lower):
        return "file_write"
    if _word_match(["create a markdown", "create a doc", "create file", "write file"], task_lower) and _word_match(["save", "folder", "directory", "orthodontic", "linesofbusiness", "melanindocs", "orthoflow"], task_lower):
        return "file_write"

    if _word_match(["scaffold", "bootstrap", "init project", "new project", "create project"], task_lower):
        return "scaffold"
    if _word_match(["deploy", "launch", "build image", "docker compose up", "go live"], task_lower):
        return "deploy"
    if _word_match(["dba", "database health", "slow query", "connection pool", "vacuum", "table bloat", "dead tuple", "postgres health", "db performance", "migration review", "index recommend"], task_lower):
        return "dba"
    if _word_match(["sre", "uptime", "latency", "health check", "monitoring", "incident", "container down", "nginx", "tls", "cert expir", "dns", "fail2ban", "connectivity", "outage", "downtime", "capacity", "slo", "observability"], task_lower):
        return "sre"
    if _word_match(["seo", "aeo", "schema markup", "json-ld", "sitemap", "robots.txt", "indexnow", "search engine", "ai overview", "faq page"], task_lower):
        return "frontend"
    if _word_match(["frontend", "component", "page", "ui", "ux", "design", "next.js", "react", "tailwind", "css", "layout", "style", "color", "animation", "mobile", "responsive", "viewport", "website", "screen"], task_lower):
        return "frontend"
    if _word_match(["backend", "api", "route", "endpoint", "model", "database", "fastapi"], task_lower):
        return "backend"
    if _word_match(["bug", "fix", "broken", "error", "issue", "support", "not working", "crash"], task_lower):
        return "support"
    if _word_match(["file operation", "read file", "create file", "delete file", "move file", "folder operation"], task_lower):
        return "file"
    return "code"


def _format_template_proposal(template, steps: list[dict]) -> str:
    """Format template steps as a readable proposal for Slack approval."""
    lines = [f"**Pipeline: {template.name}**", f"_{template.description}_", ""]
    for i, step in enumerate(steps, 1):
        icon = "🔒" if step["approve"] else "⚡"
        if step["type"] == "approve":
            icon = "✋"
            lines.append(f"{i}. {icon} **APPROVAL GATE** — {step['message']}")
        elif step["type"] == "darius":
            lines.append(f"{i}. {icon} Darius: {step['task']}")
        else:
            lines.append(f"{i}. {icon} [{step['agent']}] {step['task']}")
    lines.append("")
    lines.append("🔒 = requires approval | ⚡ = auto-executes | ✋ = human gate")
    return "\n".join(lines)


def _handle_slack_post(task: str, project: str, callback_id: str) -> dict:
    """Handle tasks that require posting content to a Slack channel.
    Extracts ticket references and channel IDs from the task text."""

    # Extract channel ID from Slack-formatted channel reference <#C0AQKP0SDFY|channel-name>
    channel_match = re.search(r"<#(C[A-Z0-9]+)(?:\|[^>]*)?>", task)
    target_channel = channel_match.group(1) if channel_match else None

    # Extract ticket references (ticket 35, #35, ticket #35, "35 and 36")
    ticket_refs = re.findall(r"(?:ticket\s*#?|#)(\d+)", task.lower())
    # Also catch bare numbers adjacent to "and" or commas after a ticket ref
    if ticket_refs:
        # Look for "and NN" or ", NN" patterns after the first match
        additional = re.findall(r"(?:and|,)\s*#?(\d+)", task.lower())
        ticket_refs.extend(additional)
    ticket_ids = sorted(set(int(t) for t in ticket_refs))

    # Fetch ticket content from DB
    content_parts = []
    if ticket_ids:
        try:
            dsn = os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro")
            conn = psycopg2.connect(dsn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            for tid in ticket_ids:
                cur.execute("SELECT id, task, proposal, agent, status FROM tickets WHERE id = %s", (tid,))
                row = cur.fetchone()
                if row and row["proposal"]:
                    content_parts.append(f"📋 *Ticket #{row['id']}*\n*Task:* {row['task'][:150]}\n*Agent:* {row['agent']}\n\n{row['proposal']}")
            conn.close()
        except Exception as e:
            content_parts.append(f"⚠️ Error fetching ticket data: {e}")

    # If no ticket refs, check for file references
    if not content_parts:
        # Look for markdown file references in the task
        file_match = re.search(r"`([^`]+\.md)`|```([^`]+\.md)```", task)
        if file_match:
            filename = file_match.group(1) or file_match.group(2)
            # Search for the file
            search_paths = [
                f"/app/Projects/{project}",
                "/app/Projects",
                f"/app/melanin-tech-website",
            ]
            for base in search_paths:
                for root, dirs, files in os.walk(base):
                    if filename in files:
                        filepath = os.path.join(root, filename)
                        try:
                            with open(filepath) as f:
                                content_parts.append(f.read())
                        except Exception:
                            pass
                        break

    if not content_parts:
        content_parts.append("⚠️ No content found — could not locate referenced tickets or files.")

    combined_content = "\n\n---\n\n".join(content_parts)

    proposal_text = (
        f"**Action:** Post to Slack channel {'<#' + target_channel + '>' if target_channel else '(default channel)'}\n"
        f"**Content source:** Ticket(s) {', '.join(f'#{t}' for t in ticket_ids) if ticket_ids else 'file reference'}\n"
        f"**Content length:** {len(combined_content):,} chars\n\n"
        f"---\n\n{combined_content[:1500]}{'...' if len(combined_content) > 1500 else ''}"
    )

    return {
        "agent": "Orchestrator",
        "model": "none",
        "action": "slack_post",
        "description": f"Post content to Slack ({'#' + target_channel if target_channel else 'default channel'})",
        "args": {
            "task": task,
            "project": project,
            "proposal": proposal_text,
            "target_channel": target_channel,
            "content": combined_content,
        },
    }


def _handle_file_write(task: str, project: str, callback_id: str) -> dict:
    """Handle tasks that require writing findings/content to a file on disk."""

    # Extract ticket references
    ticket_refs = re.findall(r"(?:ticket\s*#?|#)(\d+)", task.lower())
    if ticket_refs:
        additional = re.findall(r"(?:and|,)\s*#?(\d+)", task.lower())
        ticket_refs.extend(additional)
    ticket_ids = sorted(set(int(t) for t in ticket_refs))

    # Determine target path from task
    # Look for folder/path references — resolve to actual mounted paths in orchestrator
    path_hints = []
    if "orthodontic_dental" in task.lower() or "orthoflow" in task.lower():
        path_hints.append("/app/orthoflow-backend/../")  # resolves to the OrthoFlow project root
    if "melanindocs" in task.lower():
        path_hints.append("/app/Projects/kiro-agents/../../MelaninDocs")

    # Map to real host-accessible paths via orchestrator volume mounts
    WRITABLE_PATHS = {
        "orthodontic_dental": "/app/LinesOfBusiness/Orthodontic_Dental",
        "orthoflow": "/app/LinesOfBusiness/Orthodontic_Dental/orthoflow-ai",
        "melanindocs": "/app/MelaninDocs",
        "melanin-tech-website": "/app/melanin-tech-website",
    }

    target_dir = None
    for key, path in WRITABLE_PATHS.items():
        if key in task.lower():
            target_dir = path
            break

    if not target_dir:
        target_dir = f"/app/Projects/{project}"

    # Extract filename if mentioned
    file_match = re.search(r"`([^`]+\.(md|txt|py))`|```([^`]+\.(md|txt|py))```", task)
    filename = (file_match.group(1) or file_match.group(3)) if file_match else None

    # Fetch content from tickets
    content_parts = []
    if ticket_ids:
        try:
            dsn = os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro")
            conn = psycopg2.connect(dsn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            for tid in ticket_ids:
                cur.execute("SELECT id, task, proposal FROM tickets WHERE id = %s", (tid,))
                row = cur.fetchone()
                if row and row["proposal"]:
                    content_parts.append(row["proposal"])
            conn.close()
        except Exception as e:
            content_parts.append(f"Error fetching ticket data: {e}")

    combined_content = "\n\n---\n\n".join(content_parts) if content_parts else "(no content found)"

    target_path = target_dir
    if filename:
        target_file = os.path.join(target_path, filename)
    else:
        target_file = os.path.join(target_path, "findings.md")

    proposal_text = (
        f"**Action:** Write file to disk\n"
        f"**Target:** `{target_file}`\n"
        f"**Content source:** Ticket(s) {', '.join(f'#{t}' for t in ticket_ids) if ticket_ids else 'task description'}\n"
        f"**Content length:** {len(combined_content):,} chars\n\n"
        f"---\n\n{combined_content[:1500]}{'...' if len(combined_content) > 1500 else ''}"
    )

    return {
        "agent": "Orchestrator",
        "model": "none",
        "action": "file_write_direct",
        "description": f"Write findings to `{target_file}`",
        "args": {
            "task": task,
            "project": project,
            "proposal": proposal_text,
            "target_file": target_file,
            "content": combined_content,
        },
    }


def _handle_email(task: str, project: str, callback_id: str) -> dict:
    """Handle tasks that require sending an email with optional attachment."""

    # Extract email address
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", task)
    recipient = email_match.group(0) if email_match else None

    # Extract file references
    file_match = re.search(r"([A-Za-z0-9_-]+\.(pdf|md|docx|txt|xlsx|csv))", task)
    attachment_name = file_match.group(0) if file_match else None

    # Search for the file in known writable paths
    attachment_path = None
    if attachment_name:
        search_dirs = [
            "/app/LinesOfBusiness",
            "/app/MelaninDocs",
            "/app/Projects",
            "/app/melanin-tech-website",
        ]
        for base in search_dirs:
            for root, dirs, files in os.walk(base):
                if attachment_name in files:
                    attachment_path = os.path.join(root, attachment_name)
                    break
            if attachment_path:
                break

    # Also check for ticket references to include as body content
    ticket_refs = re.findall(r"(?:ticket\s*#?|#)(\d+)", task.lower())
    if ticket_refs:
        additional = re.findall(r"(?:and|,)\s*#?(\d+)", task.lower())
        ticket_refs.extend(additional)
    ticket_ids = sorted(set(int(t) for t in ticket_refs)) if ticket_refs else []

    body_content = ""
    if ticket_ids:
        try:
            dsn = os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro")
            conn = psycopg2.connect(dsn)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            for tid in ticket_ids:
                cur.execute("SELECT id, proposal FROM tickets WHERE id = %s", (tid,))
                row = cur.fetchone()
                if row and row["proposal"]:
                    body_content += row["proposal"] + "\n\n"
            conn.close()
        except Exception:
            pass

    proposal_text = (
        f"**Action:** Send email\n"
        f"**To:** {recipient}\n"
        f"**Attachment:** {attachment_name or 'none'} {'✅ found at ' + attachment_path if attachment_path else '⚠️ file not found on disk' if attachment_name else ''}\n"
        f"**Body content:** {'From ticket(s) ' + ', '.join(f'#{t}' for t in ticket_ids) if ticket_ids else 'Standard delivery message'}\n"
    )

    return {
        "agent": "Orchestrator",
        "model": "none",
        "action": "email",
        "description": f"Email to {recipient}" + (f" with {attachment_name}" if attachment_name else ""),
        "args": {
            "task": task,
            "project": project,
            "proposal": proposal_text,
            "recipient": recipient,
            "attachment_path": attachment_path,
            "attachment_name": attachment_name,
            "body": body_content,
        },
    }
