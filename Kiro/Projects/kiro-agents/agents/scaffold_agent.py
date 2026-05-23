import os
import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

SYSTEM_PROMPT = (
    "You are a project scaffolding expert. Given a project name and stack (Next.js + TypeScript frontend, "
    "FastAPI backend, PostgreSQL), output a shell script that creates the full directory structure, "
    "initializes the projects, and writes a docker-compose.yml wiring all services together. "
    "For every file, start the code block with a comment on the first line containing the relative file path. "
    "Example:\n```bash\n# deploy.sh\n<content>\n```\nBe concise. Output only the files."
)


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    project_path = os.path.join(PROJECTS_BASE, project)
    return {
        "agent": "ScaffoldAgent",
        "model": model,
        "description": f"ScaffoldAgent will bootstrap project '{project}'",
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
