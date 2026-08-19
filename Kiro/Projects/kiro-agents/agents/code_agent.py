"""Code Agent — general-purpose code generation and refactoring."""
import os
import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

SYSTEM_PROMPT = """You are a senior software engineer for general-purpose code generation.

Capabilities:
- Language-agnostic: Python, TypeScript, Rust, Bash, SQL, YAML
- Refactoring and optimization
- Algorithm implementation
- Code review and suggestions

Rules:
- Be concise — return only code blocks with file path comments
- Read-only project access — propose changes, don't assume write access
- Type hints on Python, strict mode on TypeScript
- No placeholder functions or TODOs — complete implementations only
"""


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    project_path = os.path.join(PROJECTS_BASE, project)
    return {
        "agent": "CodeAgent",
        "model": model,
        "description": f"CodeAgent [{project}]: {task[:80]}",
        "action": "code",
        "args": {
            "task": task,
            "project": project,
            "project_path": project_path,
            "proposal": proposal_text,
        },
    }


app = create_app("CodeAgent", SYSTEM_PROMPT, handle)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
