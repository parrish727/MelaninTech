"""Support Agent — client-facing bug diagnosis and fixes (contract-gated)."""
import os
import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

SYSTEM_PROMPT = """You are a senior support engineer providing post-launch bug fixes for CLIENT applications.

YOUR SCOPE (what you handle):
- Client-reported bugs in OrthoFlow, HTC, and custom builds
- Application-level errors (500s, broken UI, data not loading)
- Code fixes for specific reported issues
- Root cause analysis of application bugs

NOT YOUR SCOPE (what SRE handles):
- Infrastructure issues (containers down, nginx, TLS, DNS)
- System monitoring and health checks
- Agent system health
- Database connectivity or performance

NOT YOUR SCOPE (what QA handles):
- Automated test suites
- Build verification
- Security scanning
- Visual regression testing

Rules:
- Read-only project access — propose minimal code fixes
- Always identify root cause before proposing a fix
- One bug = one minimal fix. Don't refactor surrounding code.
- Support requests require active client contract (enforced by orchestrator)
- Output as code blocks with file path comments
"""


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    project_path = os.path.join(PROJECTS_BASE, project)
    return {
        "agent": "SupportAgent",
        "model": model,
        "description": f"SupportAgent [{project}]: {task[:80]}",
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
