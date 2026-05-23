import os
import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

SYSTEM_PROMPT = (
    "You are a senior engineer providing post-launch support. Given a bug report or support request "
    "and the relevant project context, diagnose the issue and propose the minimal code fix. "
    "For every file changed, start the code block with a comment on the first line containing the relative file path. "
    "Example:\n```python\n# api/routes/invoices.py\n<content>\n```\nBe concise and precise."
)


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    project_path = os.path.join(PROJECTS_BASE, project)
    return {
        "agent": "SupportAgent",
        "model": model,
        "description": f"SupportAgent addressing issue for '{project}': {task}",
        "action": "support",
        "args": {
            "task": task,
            "project": project,
            "project_path": project_path,
            "proposal": proposal_text,
        },
    }


app = create_app("SupportAgent", SYSTEM_PROMPT, handle)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
