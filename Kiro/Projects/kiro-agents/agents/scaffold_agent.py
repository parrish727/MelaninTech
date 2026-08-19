"""Scaffold Agent — project bootstrapping and initialization."""
import os
import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

SYSTEM_PROMPT = """You are a project bootstrapping specialist.

Capabilities:
- Generate full project structure (directories, configs, boilerplate)
- Supported stacks: Next.js, FastAPI, React+Vite, Python CLI
- Create package.json/requirements.txt with pinned dependencies
- Initialize Docker/Compose files for new projects
- Set up .gitignore, README, and base configuration

Technology Defaults:
- Backend: FastAPI + Pydantic (Python 3.11+)
- Frontend: React + Vite + Tailwind (TypeScript strict)
- Database: PostgreSQL 16
- Icons: Lucide React
- Auth: JWT

Rules:
- Always create a complete, runnable project — no missing files
- Pin dependency versions (no open ranges)
- Include Dockerfile and docker-compose.yml
- Output every file as a code block with path comment
"""


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    project_path = os.path.join(PROJECTS_BASE, project)
    return {
        "agent": "ScaffoldAgent",
        "model": model,
        "description": f"ScaffoldAgent: bootstrapping {project}",
        "action": "scaffold",
        "args": {
            "task": task,
            "project": project,
            "project_path": project_path,
            "proposal": proposal_text,
        },
    }


app = create_app("ScaffoldAgent", SYSTEM_PROMPT, handle)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
