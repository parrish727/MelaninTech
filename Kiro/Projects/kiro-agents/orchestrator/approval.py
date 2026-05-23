import os
from orchestrator.memory import store, recall, store_conversation
from orchestrator.tickets import open_ticket, update_ticket, heartbeat, MAX_ATTEMPTS

PREVIEW_DIR = "/app/previews"
pending_approvals = {}


def _save_preview(ticket_id: int, proposal_text: str) -> str | None:
    """Extract HTML from proposal and save as a preview file. Returns URL or None."""
    import re
    match = re.search(r'```html\n(.*?)```', proposal_text, re.DOTALL)
    if not match:
        return None
    html = match.group(1).strip()
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    path = os.path.join(PREVIEW_DIR, f"ticket-{ticket_id}.html")
    with open(path, "w") as f:
        f.write(html)
    return f"http://localhost:3001/ticket-{ticket_id}.html"


def _context_block(task: str) -> dict | None:
    similar = recall(task)
    if not similar:
        return None
    lines = "\n".join(
        f"• [{r['decision'].upper()}] ({r['agent']}) {r['task']}" for r in similar
    )
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*Similar past tasks:*\n{lines}"},
    }


def request_approval(app, channel: str, task: str, proposal: dict, callback_id: str):
    pending_approvals[callback_id] = proposal
    # open a ticket in the DB
    ticket_id = open_ticket(
        client=proposal["args"].get("project", "default"),
        task=task,
        agent=proposal["agent"],
        proposal=proposal["args"]["proposal"],
        callback_id=callback_id,
        ticket_type=proposal.get("_ticket_type", "client"),
    )
    proposal["_ticket_id"] = ticket_id
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Agent:* {proposal['agent']}  |  *Model:* `{proposal.get('model', 'unknown')}`\n"
                    f"*Task:* {proposal['args']['task'][:200]}\n"
                    f"*Project Path:* `{proposal['args'].get('project_path', 'N/A')}`\n\n"
                    f"*Proposal:*\n```{proposal['args']['proposal'][:800]}```"
                ),
            },
        },
    ]

    ctx = _context_block(task)
    if ctx:
        blocks.append(ctx)

    # Generate HTML preview if proposal contains one
    preview_url = _save_preview(ticket_id, proposal["args"]["proposal"])
    if preview_url:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"👁️ *Preview:* <{preview_url}|View before approving>"},
        })

    blocks.append({
        "type": "actions",
        "block_id": callback_id,
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ Approve"},
                "style": "primary",
                "action_id": "approve",
                "value": callback_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✏️ Modify"},
                "action_id": "modify",
                "value": callback_id,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "❌ Reject"},
                "style": "danger",
                "action_id": "reject",
                "value": callback_id,
            },
        ],
    })

    try:
        app.client.chat_postMessage(
            channel=channel,
            text=f"*{proposal['description']}*",
            blocks=blocks,
        )
    except Exception as e:
        # Auto-cancel the ticket so it can be re-submitted cleanly
        update_ticket(callback_id, status="cancelled")
        pending_approvals.pop(callback_id, None)
        raise RuntimeError(f"Failed to post approval to Slack (ticket auto-cancelled): {e}") from e


def open_modify_modal(app, trigger_id: str, callback_id: str):
    proposal = pending_approvals.get(callback_id)
    if not proposal:
        return
    app.client.views_open(
        trigger_id=trigger_id,
        view={
            "type": "modal",
            "callback_id": f"modify_submit:{callback_id}",
            "title": {"type": "plain_text", "text": "Modify Proposal"},
            "submit": {"type": "plain_text", "text": "Approve Modified"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "modified_proposal",
                    "label": {"type": "plain_text", "text": "Edit the proposal"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "proposal_text",
                        "multiline": True,
                        "initial_value": proposal["args"]["proposal"],
                    },
                }
            ],
        },
    )


def _write_code_blocks(proposal_text: str, project_path: str) -> list[str]:
    """
    Parse fenced code blocks with a file path comment on the first line.
    Expected format:
        ```python
        # path/to/file.py
        <code>
        ```
    Returns list of files written.
    """
    import re
    written = []
    pattern = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
    for match in pattern.finditer(proposal_text):
        block = match.group(1)
        lines = block.strip().splitlines()
        if not lines:
            continue
        # first line must be a path comment: # some/path or // some/path
        first = lines[0].strip()
        if first.startswith("#") or first.startswith("//"):
            rel_path = first.lstrip("#/").strip()
            content = "\n".join(lines[1:])
        else:
            continue  # no path hint, skip
        full_path = os.path.join(project_path, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        written.append(full_path)
    return written


def execute_proposal(proposal: dict) -> str:
    action = proposal["action"]
    args = proposal["args"]
    project_path = args.get("project_path", "")
    proposal_text = args["proposal"]

    if action == "file":
        os.makedirs(project_path, exist_ok=True)
        log_path = os.path.join(project_path, "proposal.md")
        with open(log_path, "w") as f:
            f.write(f"# Task\n{args['task']}\n\n# Proposal\n{proposal_text}\n")
        return f"📁 Created project folder and wrote proposal to `{log_path}`"

    if action in ("scaffold", "backend", "frontend", "support"):
        written = _write_code_blocks(proposal_text, project_path)
        if written:
            files = "\n".join(f"  • `{f}`" for f in written)
            # Auto-rebuild OrthoFlow frontend if files were written there
            if "orthoflow-frontend" in project_path:
                try:
                    import subprocess
                    subprocess.run(
                        ["docker", "compose", "-f", "/app/docker/docker-compose-orthoflow.yml", "up", "-d", "--force-recreate", "--build", "frontend"],
                        capture_output=True, timeout=120, cwd="/app"
                    )
                except Exception:
                    pass
            # Run QA checks
            try:
                import httpx as _httpx
                qa_resp = _httpx.post("http://qa-agent:8000/task", json={"task": args["task"], "project": args.get("project", "default")}, timeout=120)
                if qa_resp.status_code == 200:
                    qa_data = qa_resp.json()
                    qa_report = qa_data.get("args", {}).get("proposal", "")
                    if not qa_data.get("qa_pass", True):
                        return f"✅ Written {len(written)} file(s) to `{project_path}`:\n{files}\n\n⚠️ *QA Failed:*\n{qa_report}"
                    files += f"\n\n🧪 *QA Passed*\n{qa_report}"
            except Exception:
                pass
            return f"✅ Written {len(written)} file(s) to `{project_path}`:\n{files}"

        # Retry: ask the LLM to reformat as code blocks
        from agents.base_agent import _complete, select_model
        retry_prompt = (
            "The following proposal needs to be converted into ONLY fenced code blocks with file paths.\n"
            "Each code block must start with a comment containing the relative file path.\n"
            "Output NOTHING except code blocks. No explanations.\n\n"
            f"Project path: {project_path}\n"
            f"Original proposal:\n{proposal_text[:3000]}"
        )
        retry_model = select_model(args.get("task", ""))
        reformatted = _complete(retry_model, "You convert proposals into fenced code blocks with file path comments. Output ONLY code blocks.", retry_prompt)
        written = _write_code_blocks(reformatted, project_path)
        if written:
            files = "\n".join(f"  • `{f}`" for f in written)
            return f"✅ Written {len(written)} file(s) to `{project_path}` (reformatted):\n{files}"

        # Final fallback
        os.makedirs(project_path, exist_ok=True)
        fallback = os.path.join(project_path, f"{action}_proposal.md")
        with open(fallback, "w") as f:
            f.write(f"# Task\n{args['task']}\n\n# Proposal\n{proposal_text}\n")
        return f"⚠️ Could not parse code blocks after retry — proposal saved to `{fallback}`"

    if action == "deploy_complete":
        # Deploy-agent already executed — just return the result
        return proposal.get("result", "✅ Deploy complete.")

    if action == "deploy":
        import re, subprocess
        project = args.get("project", "")
        callback_id = proposal.get("_callback_id")

        # For known compose services, use Docker SDK directly — skip LLM script entirely
        compose_services = {
            "melanin-tech-website": "melanin-website",
            "melanin-website": "melanin-website",
            "website": "melanin-website",
        }
        if project.lower() in compose_services:
            service = compose_services[project.lower()]
            # Use Docker SDK directly — avoids all path resolution issues with Docker Desktop VM
            try:
                import docker as docker_sdk
                client = docker_sdk.from_env()
                # Build the image
                if callback_id:
                    heartbeat(callback_id, f"building image for {service}")
                image, logs = client.images.build(
                    path="/app/melanin-tech-website",
                    tag=f"docker-{service}",
                    rm=True,
                    forcerm=True,
                )
                # Stop and remove existing container
                try:
                    old = client.containers.get(f"docker-{service}-1")
                    old.stop(timeout=10)
                    old.remove()
                except Exception:
                    pass
                # Start new container
                if callback_id:
                    heartbeat(callback_id, f"starting {service}")
                client.containers.run(
                    image=f"docker-{service}",
                    name=f"docker-{service}-1",
                    detach=True,
                    restart_policy={"Name": "unless-stopped"},
                    ports={"3000/tcp": 3000},
                    network="docker_agent-net",
                    labels={"managed-by": "kiro-deploy-agent"},
                )
                if callback_id:
                    heartbeat(callback_id, "container started")
                return f"🚀 Rebuilt and restarted `{service}` — http://localhost:3000"
            except Exception as e:
                return f"⚠️ Deploy failed: {e}"

        # Generic deploy — use LLM-generated script
        script_path = os.path.join(project_path, "deploy.sh")
        os.makedirs(project_path, exist_ok=True)
        blocks = re.findall(r"```(?:bash|sh)?\n(.*?)```", proposal_text, re.DOTALL)
        script = "\n".join(blocks) if blocks else proposal_text
        is_daemon = any(k in script for k in ["npm run dev", "npm start", "uvicorn", "gunicorn", "tail -f"])
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\nset -e\n\n" + script)
        os.chmod(script_path, 0o755)
        if is_daemon:
            log_path = os.path.join(project_path, "deploy.log")
            with open(log_path, "w") as log_f:
                proc = subprocess.Popen(["bash", script_path], stdout=log_f, stderr=log_f)
            if callback_id:
                heartbeat(callback_id, f"daemon started PID={proc.pid} log={log_path}")
            return f"🚀 Daemon started for `{args.get('project', project_path)}` — PID `{proc.pid}`\nLogs: `{log_path}`"
        # short-lived — run and wait
        if callback_id:
            heartbeat(callback_id, "deploy script running")
        result = subprocess.run(["bash", script_path], capture_output=True, text=True, timeout=600)
        if callback_id:
            heartbeat(callback_id, f"deploy finished rc={result.returncode}")
        if result.returncode == 0:
            return f"🚀 Deployed `{args.get('project', project_path)}`\n```{result.stdout[-1000:]}```"
        return f"⚠️ Deploy script error:\n```{result.stderr[-1000:]}```"

    if action == "code":
        return f"💻 Code proposal ready for implementation:\n```{proposal_text[:1000]}```"

    return f"✅ Action `{action}` acknowledged."


def handle_approval(ack, body, action, say, app=None):
    ack()
    callback_id = action["value"]
    decision = action["action_id"]

    if decision == "modify":
        open_modify_modal(body.get("app"), body.get("trigger_id"), callback_id)
        return

    proposal = pending_approvals.pop(callback_id, None)
    if not proposal:
        say("⚠️ Could not find the pending proposal. It may have already been handled.")
        return

    if decision == "approve":
        proposal["_callback_id"] = callback_id
        ticket_id = proposal.get("_ticket_id", "?")
        update_ticket(callback_id, "in_progress", "approved — execution started")
        result = execute_proposal(proposal)
        store(proposal["args"]["task"], proposal["args"]["proposal"], proposal["agent"], "approved")
        store_conversation("assistant", f"[{proposal['agent']}] {proposal['args']['proposal']}")
        update_ticket(callback_id, "done", "execution complete")
        say(f"✅ *Ticket #{ticket_id} — Done*\n{result}")

        # Auto-deploy to testing → staging ONLY for melanin-tech-website
        if proposal.get("action") in ("frontend", "scaffold", "backend") and proposal["args"].get("project", "").lower() in ("melanin-tech-website", "default"):
            import threading
            from orchestrator.deploy_pipeline import deploy_pipeline
            threading.Thread(
                target=deploy_pipeline,
                args=(app, ticket_id),
                daemon=True,
            ).start()
    else:
        ticket_id = proposal.get("_ticket_id", "?")
        store(proposal["args"]["task"], proposal["args"]["proposal"], proposal["agent"], "rejected")
        store_conversation("assistant", f"[{proposal['agent']}][rejected] {proposal['args']['proposal']}")
        update_ticket(callback_id, "rejected")
        say(f"❌ *Ticket #{ticket_id} — Rejected*: `{proposal['action']}` — discarded.")


def handle_modify_submit(ack, body, view, say, app=None):
    ack()
    callback_id = view["callback_id"].split(":", 1)[1]
    proposal = pending_approvals.pop(callback_id, None)
    if not proposal:
        say("⚠️ Proposal expired or already handled.")
        return

    modified_text = view["state"]["values"]["modified_proposal"]["proposal_text"]["value"]
    proposal["args"]["proposal"] = modified_text

    result = execute_proposal(proposal)
    store(proposal["args"]["task"], modified_text, proposal["agent"], "approved_modified")
    store_conversation("assistant", f"[{proposal['agent']}][modified] {modified_text}")
    say(f"✏️ *Modified, approved & completed*\n{result}")

    if proposal.get("action") in ("frontend", "scaffold", "backend") and proposal["args"].get("project", "").lower() in ("melanin-tech-website", "default"):
        import threading
        from orchestrator.deploy_pipeline import deploy_pipeline
        threading.Thread(
            target=deploy_pipeline,
            args=(app, proposal.get("_ticket_id", "?")),
            daemon=True,
        ).start()
