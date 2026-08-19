"""File Agent — file system operations specialist."""
import os
import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

SYSTEM_PROMPT = """You are a file operations specialist.

Capabilities:
- Create, read, write, delete, move, copy files
- Directory creation and traversal
- Bulk file transformations (rename patterns, find/replace)
- Project scaffolding support

Rules:
- Scoped to project output directory only
- Describe exactly what operations will be performed before executing
- Use os.makedirs(exist_ok=True) for any directory creation
- Output file operations as code blocks with path comments
"""


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    project_path = os.path.join(PROJECTS_BASE, project)
    return {
        "agent": "FileAgent",
        "model": model,
        "description": f"FileAgent [{project}]: {task[:80]}",
        "action": "file",
        "args": {
            "task": task,
            "project": project,
            "project_path": project_path,
            "proposal": proposal_text,
        },
    }


app = create_app("FileAgent", SYSTEM_PROMPT, handle)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
