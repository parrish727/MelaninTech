import os
import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

PROJECT_PATHS = {
    "orthoflow-ai": "/app/orthoflow-backend",
}

SYSTEM_PROMPT = """You are a senior backend engineer specializing in FastAPI and Python.

CRITICAL RULES:
- NEVER reference or modify files from other projects
- ONLY output files for the project you are assigned
- Each project is completely isolated

For every file, start the code block with a path comment:
```python
# app/api/routes/invoices.py
<content>
```

Rules:
- Type hints on all function signatures
- Input validation via Pydantic
- Be concise, production-ready code only
"""


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    project_path = PROJECT_PATHS.get(project.lower())
    if not project_path:
        project_path = os.path.join(PROJECTS_BASE, project, "backend")

    return {
        "agent": "BackendAgent",
        "model": model,
        "description": f"BackendAgent [{project}]: {task[:80]}",
        "action": "backend",
        "args": {
            "task": task,
            "project": project,
            "project_path": project_path,
            "proposal": f"PROJECT: {project}\n\n{proposal_text}",
        },
    }


app = create_app("BackendAgent", SYSTEM_PROMPT, handle)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
