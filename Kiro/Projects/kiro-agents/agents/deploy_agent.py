import os
import subprocess
import uvicorn
from fastapi import FastAPI

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

KNOWN_SERVICES = {
    "melanin-tech-website": ("preview-server", "/app/melanin-tech-website"),
    "melanin-website":      ("preview-server", "/app/melanin-tech-website"),
    "website":              ("preview-server", "/app/melanin-tech-website"),
}

app = FastAPI()

@app.post("/task")
def task(body: dict):
    task_text = body["task"]
    project   = body.get("project", "default")
    callback_id = body.get("callback_id")

    # Known service — execute directly, no LLM needed
    if project.lower() in KNOWN_SERVICES:
        service, build_path = KNOWN_SERVICES[project.lower()]
        return _deploy_service(task_text, project, service, build_path, callback_id)

    # Unknown project — fall back to LLM proposal (human approves before execution)
    from agents.base_agent import select_model, _complete
    model = select_model(task_text)
    system_prompt = (
        "You are a senior DevOps engineer. Generate a bash script to deploy the project. "
        "No git. No npm run dev. Output only a fenced bash code block."
    )
    proposal_text = _complete(model, system_prompt, task_text)
    project_path = os.path.join(PROJECTS_BASE, project)
    return {
        "agent": "DeployAgent",
        "model": model,
        "description": f"DeployAgent will deploy '{project}'",
        "action": "deploy",
        "args": {
            "task": task_text,
            "project": project,
            "project_path": project_path,
            "proposal": proposal_text,
        },
    }


def _deploy_service(task: str, project: str, service: str, build_path: str, callback_id: str):
    """Build and restart a known Docker service using the SDK — no compose file path needed."""
    try:
        import docker as docker_sdk
        from orchestrator.tickets import heartbeat as hb

        def _hb(msg):
            if callback_id:
                try:
                    from orchestrator.tickets import heartbeat as hb
                    hb(callback_id, msg)
                except Exception:
                    pass

        client = docker_sdk.from_env()

        _hb(f"building image for {service} from {build_path}")
        image, _ = client.images.build(
            path=build_path,
            tag=f"docker-{service}",
            rm=True,
            forcerm=True,
        )

        # Stop and remove old container
        try:
            old = client.containers.get(f"docker-{service}-1")
            old.stop(timeout=10)
            old.remove()
        except Exception:
            pass

        _hb(f"starting {service}")
        client.containers.run(
            image=f"docker-{service}",
            name=f"docker-{service}-1",
            detach=True,
            restart_policy={"Name": "unless-stopped"},
            ports={"3000/tcp": 3000},
            network="docker_agent-net",
            labels={"managed-by": "kiro-deploy-agent"},
        )
        _hb("done")

        return {
            "agent": "DeployAgent",
            "model": "direct",
            "description": f"Rebuilt and restarted {service}",
            "action": "deploy_complete",
            "result": f"🚀 `{service}` rebuilt and running at http://localhost:3000",
        }

    except Exception as e:
        return {
            "agent": "DeployAgent",
            "model": "direct",
            "description": f"Deploy failed for {service}",
            "action": "deploy_complete",
            "result": f"⚠️ Deploy failed: {e}",
        }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
