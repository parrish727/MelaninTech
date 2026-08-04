import os
import subprocess
import time
import uvicorn
from fastapi import FastAPI

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")

KNOWN_SERVICES = {
    "melanin-tech-website": ("preview-server", "/app/melanin-tech-website"),
    "melanin-website":      ("preview-server", "/app/melanin-tech-website"),
    "website":              ("preview-server", "/app/melanin-tech-website"),
}

# ── Destructive Operation Approval Gate ───────────────────────────────────────
# docker rm, volume rm, and similar destructive ops require explicit human approval
# via Slack before execution. This prevents accidental container deletion.

_pending_destructive_approvals: dict[str, bool | None] = {}


def _request_destructive_approval(operation: str, target: str, context: str = "") -> bool:
    """
    Post a Slack message requesting approval for a destructive operation.
    Blocks until approved/rejected (max 5 minutes timeout).
    Returns True if approved, False if rejected or timed out.
    """
    import uuid
    approval_id = str(uuid.uuid4())[:8]
    _pending_destructive_approvals[approval_id] = None  # None = pending

    try:
        from config.settings import SLACK_BOT_TOKEN
        import httpx

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"🚨 *Destructive Operation Approval Required*\n\n"
                        f"*Operation:* `{operation}`\n"
                        f"*Target:* `{target}`\n"
                        f"{f'*Context:* {context}' if context else ''}\n\n"
                        f"This operation is irreversible. Approve to proceed."
                    ),
                },
            },
            {
                "type": "actions",
                "block_id": f"destructive_{approval_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve Removal"},
                        "style": "primary",
                        "action_id": "destructive_approve",
                        "value": approval_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Deny"},
                        "style": "danger",
                        "action_id": "destructive_deny",
                        "value": approval_id,
                    },
                ],
            },
        ]

        channel = SLACK_CHANNEL
        if not channel:
            # No Slack channel configured — deny by default for safety
            _pending_destructive_approvals.pop(approval_id, None)
            return False

        httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"},
            json={"channel": channel, "text": f"🚨 Destructive op approval: {operation} on {target}", "blocks": blocks},
            timeout=10,
        )

        # Block and poll for approval (max 5 minutes)
        deadline = time.time() + 300
        while time.time() < deadline:
            decision = _pending_destructive_approvals.get(approval_id)
            if decision is not None:
                _pending_destructive_approvals.pop(approval_id, None)
                return decision is True
            time.sleep(2)

        # Timed out — deny
        _pending_destructive_approvals.pop(approval_id, None)
        return False

    except Exception:
        _pending_destructive_approvals.pop(approval_id, None)
        return False


def handle_destructive_decision(approval_id: str, approved: bool):
    """Called by the Slack interaction handler when owner approves/denies."""
    if approval_id in _pending_destructive_approvals:
        _pending_destructive_approvals[approval_id] = approved

app = FastAPI()

@app.post("/task")
def task(body: dict):
    task_text = body["task"]
    project   = body.get("project", "default")
    callback_id = body.get("callback_id")

    # CI failure diagnosis — use specialized skill + LLM
    if "ci " in task_text.lower() and any(k in task_text.lower() for k in ["failure", "failed", "vulnerability", "scan", "build error"]):
        return _handle_ci_failure_task(task_text, project, callback_id)

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


def _handle_ci_failure_task(task_text: str, project: str, callback_id: str) -> dict:
    """Handle CI failure diagnosis using the CI diagnosis skill.

    Reads the specialized skill file, sends the failure context to the LLM,
    and returns a proposal with code blocks for the fix.
    """
    from agents.base_agent import select_model, _complete, load_skill

    # Load the CI diagnosis skill
    ci_skill = load_skill("ci-diagnosis")
    if not ci_skill:
        ci_skill = (
            "You are a senior DevOps engineer diagnosing CI failures. "
            "Identify the root cause and propose a minimal fix. "
            "Output fenced code blocks with file path comments on line 1."
        )

    model = select_model(task_text)

    # Attempt to fetch the GitHub Actions log for additional context
    log_context = _fetch_gh_actions_log(project)
    if log_context:
        enriched_task = f"{task_text}\n\n--- GitHub Actions Log (last 200 lines) ---\n{log_context}"
    else:
        enriched_task = task_text

    proposal_text = _complete(model, ci_skill, enriched_task)
    project_path = os.path.join(PROJECTS_BASE, project)

    return {
        "agent": "DeployAgent",
        "model": model,
        "description": f"CI failure diagnosis and fix for '{project}'",
        "action": "code",
        "args": {
            "task": task_text,
            "project": project,
            "project_path": project_path,
            "proposal": proposal_text,
        },
    }


def _fetch_gh_actions_log(project: str) -> str | None:
    """Attempt to fetch the latest failed GitHub Actions run log.

    Uses the `gh` CLI if available, falls back to None.
    Repos are mapped from project name to GitHub owner/repo.
    """
    import subprocess as _sp

    # Map project names to GitHub repos
    repo_map = {
        "orthoflow-ai": "MelaninTechnologies/orthoflow-ai",
        "melanin-tech-website": "MelaninTechnologies/melanin-tech-website",
        "kiro-agents": "MelaninTechnologies/kiro-agents",
    }

    repo = repo_map.get(project)
    if not repo:
        return None

    try:
        # Get the latest failed run ID
        result = _sp.run(
            ["gh", "run", "list", "--repo", repo, "--status", "failure", "--limit", "1", "--json", "databaseId"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        import json
        runs = json.loads(result.stdout)
        if not runs:
            return None

        run_id = runs[0]["databaseId"]

        # Fetch the failed log
        log_result = _sp.run(
            ["gh", "run", "view", str(run_id), "--repo", repo, "--log-failed"],
            capture_output=True, text=True, timeout=60,
        )
        if log_result.returncode != 0:
            return None

        # Return last 200 lines to keep context manageable
        lines = log_result.stdout.strip().splitlines()
        return "\n".join(lines[-200:])

    except Exception:
        return None


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

        # Stop and remove old container (requires human approval)
        try:
            old = client.containers.get(f"docker-{service}-1")
            old.stop(timeout=10)
            _hb(f"requesting approval to remove container docker-{service}-1")
            approved = _request_destructive_approval(
                operation="docker rm",
                target=f"docker-{service}-1",
                context=f"Rebuilding {service} — old container must be removed to start new one",
            )
            if not approved:
                # Restart the stopped container instead of removing
                old.start()
                return {
                    "agent": "DeployAgent",
                    "model": "direct",
                    "description": f"Container removal denied for {service}",
                    "action": "deploy_complete",
                    "result": f"⚠️ Container removal denied by owner. Old container restarted. Deploy aborted.",
                }
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
