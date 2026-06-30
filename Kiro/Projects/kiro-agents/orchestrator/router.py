import httpx
from config.settings import AGENT_URLS
from orchestrator.contracts import check, consume_ticket
from orchestrator.template_engine import parse_template_command, load_template, resolve_template, list_templates


def route(task: str, project: str = "default", callback_id: str = None) -> dict:
    # Check if this is a template command first
    trigger, params = parse_template_command(task)
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
                    "task": task,
                    "project": project,
                    "template": trigger,
                    "steps": steps,
                    "proposal": _format_template_proposal(template, steps),
                },
            }

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
            "args": {"task": task, "project": project, "proposal": f"Available workflow templates:\n\n{listing}"},
        }

    agent_type = _classify(task_lower)

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
        json={"task": task, "project": project, "callback_id": callback_id},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


import re

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
    if _word_match(["scaffold", "bootstrap", "init project", "new project", "create project"], task_lower):
        return "scaffold"
    if _word_match(["deploy", "launch", "build image", "docker compose up", "go live"], task_lower):
        return "deploy"
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
