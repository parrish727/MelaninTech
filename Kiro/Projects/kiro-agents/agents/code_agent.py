import uvicorn
from agents.base_agent import create_app

SYSTEM_PROMPT = (
    "You are a senior software engineer. Given a task, propose the exact code to write. "
    "Be concise. Return only the code and a one-line description of what it does."
)


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    return {
        "agent": "CodeAgent",
        "model": model,
        "description": f"CodeAgent proposes for project '{project}': {task}",
        "action": "code",
        "args": {"task": task, "project": project, "proposal": proposal_text},
    }


app = create_app("CodeAgent", SYSTEM_PROMPT, handle)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
