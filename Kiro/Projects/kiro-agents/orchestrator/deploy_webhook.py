"""
Deploy Webhook — receives notifications from Watchtower and GitHub Actions,
then auto-triggers the QA agent for the affected project.

Endpoints:
  POST /webhook/deploy  — Watchtower or GitHub Actions calls this after a deploy
  GET  /webhook/health  — Health check for the webhook server

Watchtower config (docker-compose.yml):
  WATCHTOWER_NOTIFICATION_URL: http://orchestrator:9090/webhook/deploy

GitHub Actions (add to workflow):
  - name: Trigger QA
    run: |
      curl -X POST https://hud.melanin-tech.com/webhook/deploy \
        -H "Content-Type: application/json" \
        -d '{"project": "orthoflow-ai", "source": "github-actions", "ref": "${{ github.sha }}"}'
"""
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

import httpx

logger = logging.getLogger("orchestrator.webhook")

_SLACK_APP = None
_SLACK_CHANNEL = None

# Map container/image names to project identifiers for QA
IMAGE_TO_PROJECT = {
    "orthoflow-backend": "orthoflow-ai",
    "orthoflow-frontend": "orthoflow-ai",
    "orthoflow": "orthoflow-ai",
    "melanin-website": "melanin-tech-website",
    "production-server": "melanin-tech-website",
    "melanin-tech-website": "melanin-tech-website",
    "htc-backend": "htc-app",
    "htc-frontend": "htc-app",
    "music-catalogue": "music-catalogue",
    "orchestrator": "kiro-agents",
    "darius-agent": "kiro-agents",
}

QA_AGENT_URL = "http://qa-agent:8000/task"


def _identify_project(body: dict) -> str | None:
    """Identify which project was deployed from the webhook payload."""
    # Explicit project field (from GitHub Actions or manual trigger)
    if body.get("project"):
        return body["project"]

    # Watchtower sends image name in the payload
    image = body.get("image", body.get("Image", ""))
    for key, project in IMAGE_TO_PROJECT.items():
        if key in image.lower():
            return project

    # Container name from Watchtower
    container = body.get("container", body.get("Container", ""))
    for key, project in IMAGE_TO_PROJECT.items():
        if key in container.lower():
            return project

    return None


def _trigger_qa(project: str, source: str, ref: str = ""):
    """Dispatch QA for the project and post results to Slack."""
    global _SLACK_APP, _SLACK_CHANNEL

    logger.info(f"QA triggered for {project} (source: {source})")

    # Notify Slack that QA is starting
    try:
        _SLACK_APP.client.chat_postMessage(
            channel=_SLACK_CHANNEL,
            text=f"🧪 *QA Auto-Triggered*\n*Project:* `{project}`\n*Source:* {source}" + (f"\n*Ref:* `{ref[:8]}`" if ref else ""),
        )
    except Exception as e:
        logger.error(f"Slack notification failed: {e}")

    # Call QA agent
    try:
        resp = httpx.post(
            QA_AGENT_URL,
            json={"task": f"Post-deploy QA for {project}", "project": project},
            timeout=180,
        )
        resp.raise_for_status()
        qa_result = resp.json()

        qa_pass = qa_result.get("qa_pass", False)
        report = qa_result.get("args", {}).get("proposal", "No report generated")

        status_icon = "✅" if qa_pass else "❌"
        _SLACK_APP.client.chat_postMessage(
            channel=_SLACK_CHANNEL,
            text=f"{status_icon} *QA {'PASSED' if qa_pass else 'FAILED'}* — `{project}` ({source})\n\n{report}",
        )

        if not qa_pass:
            logger.warning(f"QA FAILED for {project} — deploy may need rollback")

        # If QA passed, run SRE health verification
        if qa_pass:
            _run_sre_health_check(project, source)

    except Exception as e:
        logger.error(f"QA agent call failed: {e}")
        try:
            _SLACK_APP.client.chat_postMessage(
                channel=_SLACK_CHANNEL,
                text=f"⚠️ *QA agent unreachable* for `{project}` — {e}\nManual verification required.",
            )
        except Exception:
            pass


def _run_sre_health_check(project: str, source: str):
    """Post-deploy SRE health verification. Runs after QA passes."""
    import subprocess
    import time as _time

    logger.info(f"SRE health check for {project}")

    checks = []
    project_containers = {
        "orthoflow-ai": ["orthoflow-backend-1", "orthoflow-frontend-1"],
        "melanin-tech-website": ["docker-production-server-1"],
        "kiro-agents": ["docker-orchestrator-1", "docker-darius-agent-1"],
        "htc-app": ["htc-backend-1"],
        "music-catalogue": ["music-catalogue-backend-1"],
    }

    project_health_urls = {
        "orthoflow-ai": "http://host.docker.internal:8000/health",
        "melanin-tech-website": "http://host.docker.internal:3000/api/health",
        "htc-app": "http://host.docker.internal:8001/health",
        "kiro-agents": None,
    }

    containers = project_containers.get(project, [])
    health_url = project_health_urls.get(project)

    # 1. Container health — verify running and not restarting
    for container in containers:
        try:
            result = subprocess.run(
                ["docker", "inspect", container, "--format", "{{.State.Status}} Restarts={{.RestartCount}}"],
                capture_output=True, text=True, timeout=10
            )
            status = result.stdout.strip()
            healthy = "running" in status
            checks.append(("Container " + container, healthy, status))
        except Exception as e:
            checks.append(("Container " + container, False, str(e)))

    # 2. API health endpoint responds
    if health_url:
        try:
            # Wait up to 30 seconds for the service to be ready (post-deploy startup time)
            for attempt in range(6):
                try:
                    r = httpx.get(health_url, timeout=5)
                    if r.status_code == 200:
                        checks.append(("Health endpoint", True, f"{health_url} → 200 ({(attempt+1)*5}s)"))
                        break
                except Exception:
                    pass
                _time.sleep(5)
            else:
                checks.append(("Health endpoint", False, f"{health_url} unreachable after 30s"))
        except Exception as e:
            checks.append(("Health endpoint", False, str(e)))

    # 3. Check for crash loops (restart count > 0 within 2 min)
    _time.sleep(10)  # Wait 10s then check again for restart loops
    for container in containers:
        try:
            result = subprocess.run(
                ["docker", "inspect", container, "--format", "{{.RestartCount}}"],
                capture_output=True, text=True, timeout=10
            )
            restarts = int(result.stdout.strip())
            if restarts > 0:
                checks.append(("Restart loop check", False, f"{container} has {restarts} restarts — possible crash loop"))
            else:
                checks.append(("Stability check", True, f"{container} stable (0 restarts)"))
        except Exception:
            pass

    # Format and post results
    all_pass = all(c[1] for c in checks)
    lines = []
    for name, passed, detail in checks:
        icon = "✅" if passed else "❌"
        lines.append(f"{icon} {name}: {detail}")

    status_icon = "🟢" if all_pass else "🔴"
    message = f"{status_icon} *SRE Post-Deploy Health — `{project}`*\n" + "\n".join(lines)

    if not all_pass:
        message += "\n\n🚨 *@pktech_dev* — Health check failed within 2 min of deploy. Manual review required."

    try:
        _SLACK_APP.client.chat_postMessage(channel=_SLACK_CHANNEL, text=message)
    except Exception as e:
        logger.error(f"SRE Slack notification failed: {e}")


class WebhookHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for deploy webhooks."""

    def do_POST(self):
        if self.path == "/webhook/deploy":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"

            try:
                body = json.loads(body_bytes) if body_bytes else {}
            except json.JSONDecodeError:
                body = {}

            project = _identify_project(body)
            source = body.get("source", "watchtower")
            ref = body.get("ref", body.get("sha", ""))

            if project:
                # Run QA in background so we don't block the webhook response
                threading.Thread(
                    target=_trigger_qa,
                    args=(project, source, ref),
                    daemon=True,
                ).start()
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "accepted", "project": project}).encode())
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ignored", "reason": "unknown project"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/webhook/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "deploy-webhook"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default access logs — use structured logging instead."""
        logger.debug(f"Webhook: {args[0]}" if args else "")


def start_webhook_server(slack_app, slack_channel: str, port: int = 9090):
    """Start the webhook HTTP server in a daemon thread."""
    global _SLACK_APP, _SLACK_CHANNEL
    _SLACK_APP = slack_app
    _SLACK_CHANNEL = slack_channel

    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Deploy webhook server listening on port {port}")
    print(f"🔗 Deploy webhook listening on ::{port}/webhook/deploy")
