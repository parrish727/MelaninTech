"""
Darius FastAPI server — receives tasks from the orchestrator router.
Endpoints:
  POST /task          — single task execution
  POST /chain         — multi-step workflow execution
  GET  /health        — health check
  GET  /status        — dashboard: sessions, recent activity
"""
import uvicorn
from fastapi import FastAPI
from AI.darius.agent import run_task, chain_tasks, run_template
from AI.darius.memory import list_sessions, load_session

app = FastAPI(title="Darius Agent")


@app.post("/task")
def task(body: dict):
    task_text = body["task"]
    project = body.get("project", "default")
    session_id = body.get("session_id", project)
    model_source = body.get("model_source")  # "local" for Ollama, None for default (Claude)
    model_override = body.get("model_override")  # "light" = Haiku, "heavy" = Sonnet/Opus

    result = run_task(task_text, session_id=session_id, model_source=model_source, model_override=model_override)

    # Determine which model was actually used for the response metadata
    if model_source == "local":
        model_used = "local/ollama"
    elif model_override == "light":
        model_used = "claude-haiku"
    else:
        model_used = "claude-sonnet-4-6"

    return {
        "agent": "DariusAgent",
        "model": model_used,
        "description": f"Darius completed: {task_text[:80]}",
        "action": "code",
        "args": {
            "task": task_text,
            "project": project,
            "proposal": result,
        },
    }


@app.post("/chain")
def chain(body: dict):
    """Execute a multi-step workflow.
    Body: {"tasks": [{"agent": "frontend", "task": "...", "project": "..."}], "session_id": "..."}
    """
    tasks = body.get("tasks", [])
    session_id = body.get("session_id", "chain")

    if not tasks:
        return {"error": "No tasks provided"}

    results = chain_tasks(tasks, session_id=session_id)

    return {
        "agent": "DariusAgent",
        "action": "chain",
        "steps": len(tasks),
        "results": results,
    }


@app.get("/health")
def health():
    return {"status": "ok", "agent": "DariusAgent", "version": "1.1"}


@app.post("/template")
def template(body: dict):
    """Execute a YAML workflow template.
    Body: {"trigger": "deploy-website", "params": {"project": "melanin-tech-website"}}
    """
    trigger = body.get("trigger", "")
    params = body.get("params", {})

    if not trigger:
        return {"error": "No trigger provided"}

    results = run_template(trigger, params, session_id=body.get("session_id"))

    return {
        "agent": "DariusAgent",
        "action": "template",
        "template": trigger,
        "steps": len(results),
        "results": results,
    }


@app.get("/status")
def status():
    """Dashboard: list sessions and recent activity."""
    sessions = list_sessions()
    recent = []
    for sid in sessions[-5:]:  # last 5 sessions
        turns = load_session(sid)
        recent.append({
            "session_id": sid,
            "turns": len(turns),
            "last_task": next((t["content"][:100] for t in reversed(turns) if t["role"] == "user"), ""),
        })

    return {
        "agent": "DariusAgent",
        "total_sessions": len(sessions),
        "recent_sessions": recent,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
