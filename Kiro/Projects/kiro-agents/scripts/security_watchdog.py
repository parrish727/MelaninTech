#!/usr/bin/env python3
"""
Security Watchdog — monitors for anomalous activity.
Alerts Slack with violations and waits for CEO approval before engaging kill switch.
Does NOT auto-wipe. Human-in-the-loop always.

Runs as a container alongside the existing ticket watchdog.

Flow:
  1. Detect violation
  2. Post to Slack with Approve/Dismiss buttons
  3. Wait for response
  4. If approved → engage kill switch
  5. If dismissed → log and continue monitoring
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FILE = BASE_DIR / "logs" / "security_watchdog.log"

# Containers that are explicitly permitted to mount /var/run/docker.sock.
# Each entry is a declared service in docker-compose.yml with a documented reason.
#
# To add a new container: confirm it is declared in docker-compose.yml, document
# the reason inline, then add the container name and restart security-watchdog.
ALLOWED_SOCKET_CONTAINERS = {
    "docker-orchestrator-1",       # Core agent router — manages container lifecycle
    "docker-hud-1",                # HUD backend — reads container stats for dashboard
    "docker-deploy-agent-1",       # Deploy agent — builds and restarts app containers
    "docker-sre-agent-1",          # SRE agent — reads container health and logs
    "docker-security-watchdog-1",  # This process — monitors socket access
    "docker-nginx-reload-1",       # nginx-reload sidecar — watches container start
                                   #   events and signals nginx -s reload via docker exec
    "docker-mcp-gateway-1",        # MCP gateway — Docker tools require socket for container mgmt
    "kind-cloud-provider",         # Kind K8s — cloud-provider node for cluster networking
    "orthoflow-watchtower-1",      # OrthoFlow auto-updater — pulls new images and restarts
}
SECRET_PATTERNS = ["sk-ant-", "xoxb-", "xapp-", "ghp_", "glpat-", "AKIA"]
MAX_FAILED_BANS = 20

# Alert cooldown: suppress repeated alerts for the same violation within this window (seconds).
# Prevents Slack spam when the same known-false-positive fires every check cycle.
ALERT_COOLDOWN_SECONDS = 900  # 15 minutes

SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")

# Tracks last alert time per violation string for deduplication
_alert_history: dict[str, float] = {}


def log(msg: str):
    LOG_FILE.parent.mkdir(exist_ok=True)
    entry = f"[{datetime.now().isoformat()}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")
    print(entry)


def slack_alert(violations: list[str]) -> str | None:
    """Post violation alert to Slack with approval buttons. Returns message ts."""
    if not SLACK_TOKEN or not SLACK_CHANNEL:
        log("⚠️  No Slack credentials — cannot alert")
        return None

    import httpx
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "🚨 Security Violation Detected"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(f"• {v}" for v in violations)}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "*Action Required:* Engage kill switch? This will wipe `.env` and revoke all service secrets on next restart."}},
        {"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "🔴 Engage Kill Switch"}, "style": "danger", "action_id": "security_kill_switch_approve", "value": "approve"},
            {"type": "button", "text": {"type": "plain_text", "text": "✅ Dismiss — False Positive"}, "action_id": "security_kill_switch_dismiss", "value": "dismiss"},
        ]},
    ]

    r = httpx.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"},
        json={"channel": SLACK_CHANNEL, "text": f"🚨 Security Alert: {len(violations)} violation(s) detected", "blocks": blocks},
        timeout=10)
    data = r.json()
    if data.get("ok"):
        log(f"Slack alert posted (ts: {data.get('ts')})")
        return data.get("ts")
    else:
        log(f"Slack alert failed: {data.get('error')}")
        return None


def check_docker_socket_access() -> list[str]:
    violations = []
    try:
        result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10)
        for name in result.stdout.strip().splitlines():
            mounts = subprocess.run(["docker", "inspect", name, "--format", "{{.HostConfig.Binds}}"], capture_output=True, text=True, timeout=5)
            if "docker.sock" in mounts.stdout and name not in ALLOWED_SOCKET_CONTAINERS:
                violations.append(f"Unauthorized Docker socket access: `{name}`")
    except Exception:
        pass
    return violations


def check_secret_leaks_in_logs() -> list[str]:
    violations = []
    try:
        result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10)
        for name in result.stdout.strip().splitlines():
            logs = subprocess.run(["docker", "logs", name, "--tail", "50", "--since", "5m"], capture_output=True, text=True, timeout=10)
            output = logs.stdout + logs.stderr
            for pattern in SECRET_PATTERNS:
                if pattern in output:
                    violations.append(f"Secret pattern `{pattern}` leaked in logs of `{name}`")
    except Exception:
        pass
    return violations


def check_fail2ban_bans() -> list[str]:
    violations = []
    try:
        result = subprocess.run(["docker", "exec", "docker-fail2ban-1", "fail2ban-client", "status"], capture_output=True, text=True, timeout=10)
        if result.stdout:
            import re
            bans = re.findall(r"Currently banned:\s+(\d+)", result.stdout)
            total = sum(int(b) for b in bans)
            if total > MAX_FAILED_BANS:
                violations.append(f"Excessive bans: {total} IPs currently banned (threshold: {MAX_FAILED_BANS})")
    except Exception:
        pass
    return violations


def run_checks() -> list[str]:
    violations = []
    violations.extend(check_docker_socket_access())
    violations.extend(check_secret_leaks_in_logs())
    violations.extend(check_fail2ban_bans())
    return violations


def main():
    daemon = "--daemon" in sys.argv
    interval = 60  # seconds between checks

    log("Security watchdog started" + (" (daemon mode)" if daemon else ""))

    while True:
        violations = run_checks()

        if violations:
            now = time.time()
            # Filter out violations that were already alerted within the cooldown window
            new_violations = [
                v for v in violations
                if now - _alert_history.get(v, 0) > ALERT_COOLDOWN_SECONDS
            ]

            if new_violations:
                log(f"🚨 {len(new_violations)} violation(s) detected")
                for v in new_violations:
                    log(f"   • {v}")

                # Alert Slack — do NOT auto-wipe, wait for human approval
                slack_alert(new_violations)
                # The kill switch is engaged via Slack button callback in the orchestrator
                # This watchdog only detects and alerts — never acts without approval

                # Update cooldown history
                for v in new_violations:
                    _alert_history[v] = now
            elif not daemon:
                log(f"⏸️  {len(violations)} violation(s) suppressed (within cooldown)")
        else:
            if not daemon:
                log("✅ Security check passed — no violations")

        if not daemon:
            break

        time.sleep(interval)


if __name__ == "__main__":
    main()
