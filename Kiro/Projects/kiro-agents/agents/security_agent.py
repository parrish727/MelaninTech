"""
Security-Compliance Agent — always-on sensor/executor for Melanin Technologies.

Role split (confirmed architecture):
  - Darius = the brain + orchestrator (plan / analyze / evaluate)
  - security-agent = the always-on sensor/executor (this module)

The security-watchdog daemon is the continuous sensor: it scans every 60s and writes
findings to the `security_findings` table. This agent is the executor + query surface:

  STATUS / AUDIT tasks (no LLM):
    Live query of open findings, fail2ban bans, socket access, and governance
    compliance posture — returns a formatted report. No tokens burned.

  ANALYSIS / REMEDIATION tasks (routed to Darius):
    Sends the live security context + the relevant governance policy to Darius for
    plan -> analyze -> evaluate, then returns Darius's proposal. Any remediation with
    blast radius is propose-only (Slack approval). A strict allowlist of non-destructive,
    reversible actions (ban_ip / restart_container / seal_endpoint) may execute
    autonomously — this is the self-healing posture.

STRICT SCOPE: enforce and uphold the guardrails and standards already defined in
governance/*.md. This agent detects, analyzes, proposes, alerts, and executes ONLY
allowlisted containment. It never invents new policy and never takes destructive action.
"""
import os
import re
import subprocess

import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")
DARIUS_URL = os.environ.get("DARIUS_URL", "http://darius-agent:8000")

# Non-destructive, reversible actions the agent may execute WITHOUT human approval.
# Everything else is propose-only through the Slack approval flow.
AUTONOMOUS_ACTIONS = ("ban_ip", "restart_container", "seal_endpoint")

# Governance policies this agent enforces (source of truth — never invents rules).
GOVERNANCE_DIR = os.environ.get("GOVERNANCE_DIR", "/app/governance")

SYSTEM_PROMPT = """You are the Security-Compliance Agent — the always-on sensor/executor for \
Melanin Technologies. You enforce and uphold the existing guardrails in governance/*.md. \
You do NOT invent policy. For analysis tasks, produce: (1) threat classification, \
(2) root cause with evidence, (3) governance policy referenced, (4) proposed remediation \
mapped to the autonomous allowlist (ban_ip/restart_container/seal_endpoint) or flagged as \
propose-only for human approval, (5) blast-radius / false-positive risk. Be concise and \
evidence-driven. Never expose secrets — reference by name. Never propose destructive actions."""


def _load_governance(ref: str | None) -> str:
    """Load a governance policy file to ground Darius's analysis in existing standards."""
    if not ref:
        return ""
    path = os.path.join(GOVERNANCE_DIR, ref)
    if os.path.isfile(path):
        try:
            with open(path) as f:
                return f.read()
        except Exception:
            return ""
    return ""


def _gather_live_security() -> list[str]:
    """Query live security posture — findings, bans, socket access. No LLM."""
    lines = ["🛡️ *Security Posture — All Systems*", ""]

    # Open findings from the audit trail
    try:
        import sys as _sys
        _sys.path.insert(0, "/app")
        from orchestrator.security_findings import findings_summary, open_findings
        openf = open_findings(limit=50)
        by_sev: dict[str, int] = {}
        for f in openf:
            by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
        if openf:
            sev_str = ", ".join(f"{k}:{v}" for k, v in sorted(by_sev.items()))
            lines.append(f"🔴 *Open findings:* {len(openf)} ({sev_str})")
            for f in openf[:5]:
                lines.append(f"   • [{f['severity']}] {f['threat_class']}: {f['subject'][:80]}")
        else:
            lines.append("🟢 *Open findings:* none")
        summ = findings_summary(hours=24)
        if summ["rows"]:
            top = summ["rows"][0]
            lines.append(f"📊 *24h:* {sum(r['n'] for r in summ['rows'])} findings, top: {top['threat_class']} ({top['hits']} hits)")
    except Exception as e:
        lines.append(f"🟡 Findings unavailable: {e}")

    # fail2ban bans (read DB directly — no docker exec hang)
    try:
        import sqlite3
        db = "/app/docker/fail2ban/db/fail2ban.sqlite3"
        if os.path.exists(db):
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
            cur = conn.execute("SELECT jail, COUNT(*) FROM bans GROUP BY jail")
            rows = cur.fetchall()
            conn.close()
            total = sum(r[1] for r in rows)
            detail = ", ".join(f"{j}:{n}" for j, n in rows) if rows else "none"
            lines.append(f"{'🟢' if total == 0 else '🛡️'} *fail2ban bans:* {total} ({detail})")
    except Exception:
        pass

    # Docker socket compliance (unauthorized access = access-control violation)
    try:
        result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                                capture_output=True, text=True, timeout=10)
        names = result.stdout.strip().splitlines()
        lines.append(f"🔍 *Monitored containers:* {len(names)}")
    except Exception:
        pass

    return lines


def _parse_autonomous_action(text: str) -> tuple[str, str] | None:
    """Extract an allowlisted autonomous action from Darius's proposal, if present.
    Looks for an explicit machine-readable directive line:
        ACTION: ban_ip <ip>
        ACTION: restart_container <name>
        ACTION: seal_endpoint <host>
    Returns (action, target) or None. Only allowlisted actions are honored.
    """
    m = re.search(r"ACTION:\s*(\w+)\s+([^\s]+)", text)
    if not m:
        return None
    action, target = m.group(1), m.group(2)
    if action not in AUTONOMOUS_ACTIONS:
        return None
    return action, target


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    """Sensor/executor: status = live query; analysis/remediation = route to Darius."""
    task_lower = task.lower()
    is_status = any(k in task_lower for k in
                    ["status", "posture", "report", "digest", "audit", "overview", "findings"])

    if is_status:
        report_lines = _gather_live_security()
        return {
            "agent": "SecurityAgent",
            "model": "none (live query)",
            "description": "SecurityAgent: live security posture",
            "action": "security",
            "args": {
                "task": task,
                "project": project,
                "project_path": os.path.join(PROJECTS_BASE, project),
                "proposal": "\n".join(report_lines),
            },
        }

    # Analysis / remediation — route to Darius (the brain) grounded in governance.
    import httpx
    live_context = "\n".join(_gather_live_security())

    # Best-effort: pull the most relevant governance policy to ground the analysis.
    gov_ref = None
    for needle, ref in [
        ("secret", "secrets-policy.md"), ("socket", "access-control-policy.md"),
        ("access", "access-control-policy.md"), ("network", "network-policy.md"),
        ("ban", "network-policy.md"), ("ddos", "network-policy.md"),
        ("inject", "incident-response-policy.md"), ("trojan", "incident-response-policy.md"),
        ("depend", "change-management-policy.md"), ("data", "data-protection-policy.md"),
    ]:
        if needle in task_lower:
            gov_ref = ref
            break
    gov_text = _load_governance(gov_ref)

    try:
        darius_prompt = (
            f"[Security Analysis] Live security posture:\n{live_context}\n\n"
            + (f"Governing policy ({gov_ref}):\n{gov_text}\n\n" if gov_text else "")
            + f"Security task to analyze and remediate: {task}\n\n"
            "Enforce the governance policy above. Classify the threat, give root cause with "
            "evidence, propose remediation. If the remediation is a non-destructive allowlisted "
            "action (ban_ip/restart_container/seal_endpoint), emit a final line exactly as "
            "'ACTION: <action> <target>'. Otherwise mark it propose-only for human approval."
        )
        r = httpx.post(f"{DARIUS_URL}/task", json={
            "task": darius_prompt,
            "project": project,
            "session_id": "security-analysis",
        }, timeout=90)
        darius_response = r.json().get("args", {}).get("proposal", proposal_text)
    except Exception:
        darius_response = proposal_text

    # Record analysis + detect an allowlisted autonomous action (executed by orchestrator
    # approval flow or self-healing executor — this handler only classifies/proposes).
    autonomous = _parse_autonomous_action(darius_response)

    return {
        "agent": "SecurityAgent (via Darius)",
        "model": model,
        "description": f"SecurityAgent analysis: {task[:80]}",
        "action": "security",
        "args": {
            "task": task,
            "project": project,
            "project_path": os.path.join(PROJECTS_BASE, project),
            "proposal": darius_response,
            "autonomous_action": {"action": autonomous[0], "target": autonomous[1]} if autonomous else None,
        },
    }


app = create_app("SecurityAgent", SYSTEM_PROMPT, handle)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
