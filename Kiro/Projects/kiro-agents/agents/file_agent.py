import os
import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get(
    "PROJECTS_BASE",
    "/Users/pktech_dev/Documents/MelaninTechnologies/Kiro/Projects",
)
# Writes go to the output subdir — the only rw-mounted path
OUTPUT_BASE = os.path.join(PROJECTS_BASE, "FileAgent", "output")

SYSTEM_PROMPT = (
    "You are a file operations specialist. Given a task, describe exactly what file or folder "
    "operations you will perform (create, read, write, delete, move). Be concise and specific."
)


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    project_path = os.path.join(OUTPUT_BASE, project)
    return {
        "agent": "FileAgent",
        "model": model,
        "description": f"FileAgent proposes for '{project_path}': {task}",
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
