import httpx
from config.settings import AGENT_URLS
from orchestrator.contracts import check, consume_ticket


def route(task: str, project: str = "default", callback_id: str = None) -> dict:
    task_lower = task.lower()
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


def _classify(task_lower: str) -> str:
    if any(k in task_lower for k in ["darius", "agent loop", "agentic", "multi-step", "autonomously", "figure out"]):
        return "darius"
    if any(k in task_lower for k in ["scaffold", "bootstrap", "init project", "new project", "create project"]):
        return "scaffold"
    if any(k in task_lower for k in ["deploy", "launch", "build image", "docker compose up", "go live"]):
        return "deploy"
    if any(k in task_lower for k in ["seo", "aeo", "schema markup", "json-ld", "sitemap", "robots.txt", "indexnow", "search engine", "ai overview", "faq page"]):
        return "frontend"  # SEO tasks produce frontend code (schema, HTML structure)
    if any(k in task_lower for k in ["frontend", "component", "page", "ui", "ux", "design", "next.js", "react", "tailwind", "css", "layout", "style", "color", "animation", "mobile", "responsive", "viewport", "website", "screen"]):
        return "frontend"
    if any(k in task_lower for k in ["backend", "api", "route", "endpoint", "model", "database", "fastapi"]):
        return "backend"
    if any(k in task_lower for k in ["bug", "fix", "broken", "error", "issue", "support", "not working", "crash"]):
        return "support"
    if any(k in task_lower for k in ["file operation", "read file", "create file", "delete file", "move file", "folder operation"]):
        return "file"
    return "code"
