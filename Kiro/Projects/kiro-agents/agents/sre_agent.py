"""
SRE Agent — Site Reliability Engineering for Melanin Technologies infrastructure.

Responsibilities:
- Internal: HUD, agent system health, orchestrator, databases, MCP services
- External: melanin-tech.com, OrthoFlow, HTC, nginx, TLS, DNS
- Bridge: monitoring the connection between internal services and external-facing endpoints

YOUR SCOPE (what you handle):
- Container health, restarts, OOM detection
- Endpoint reachability (HTTP probes, TLS validity, DNS)
- LLM observability (traces, failures, SLO compliance, error budgets)
- Infrastructure capacity (CPU, RAM, disk, bandwidth)
- nginx, Cloudflare DDNS, certbot, fail2ban
- 12hr SRE digest to Slack
- Incident triage (P1-P4 classification)
- Credit/budget monitoring

NOT YOUR SCOPE (what QA handles):
- Build verification (npm build, pytest)
- API contract testing (does endpoint return 200?)
- Security scanning (auth bypass, injection)
- Visual regression (Playwright screenshots)

NOT YOUR SCOPE (what Support handles):
- Client-reported application bugs
- Code fixes for user-facing issues
- Feature-level debugging
"""
import os
import uvicorn
from agents.base_agent import create_app

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")

SYSTEM_PROMPT = """You are an SRE agent. For diagnosis tasks, provide root cause analysis and remediation steps. Keep output concise and actionable. No code blocks unless specifically asked for a fix."""


def handle(task: str, project: str, proposal_text: str, model: str) -> dict:
    """SRE agent: status reports use live data only (no LLM waste), diagnosis tasks use Darius."""
    import docker
    import psycopg2

    task_lower = task.lower()
    is_status_request = any(k in task_lower for k in ["health check", "status", "report", "digest", "overview"])

    if is_status_request:
        # Pure data query — no LLM call needed, no tokens burned
        report_lines = _gather_live_status()
        return {
            "agent": "SREAgent",
            "model": "none (live query)",
            "description": f"SREAgent: live status report",
            "action": "sre",
            "args": {
                "task": task,
                "project": project,
                "project_path": os.path.join(PROJECTS_BASE, project),
                "proposal": "\n".join(report_lines),
            },
        }
    else:
        # Diagnosis/investigation — route through Darius for learning
        import httpx
        try:
            live_context = "\n".join(_gather_live_status())
            r = httpx.post("http://darius-agent:8000/task", json={
                "task": f"[SRE Diagnosis] Live infrastructure state:\n{live_context}\n\nIssue to investigate: {task}",
                "project": project,
                "session_id": "sre-diagnosis",
            }, timeout=90)
            darius_response = r.json().get("args", {}).get("proposal", proposal_text)
        except Exception:
            darius_response = proposal_text

        return {
            "agent": "SREAgent (via Darius)",
            "model": model,
            "description": f"SREAgent diagnosis: {task[:80]}",
            "action": "sre",
            "args": {
                "task": task,
                "project": project,
                "project_path": os.path.join(PROJECTS_BASE, project),
                "proposal": darius_response,
            },
        }


def _gather_live_status() -> list[str]:
    """Query ALL infrastructure (not project-scoped) and return formatted status lines."""
    import docker
    import psycopg2
    lines = ["📊 *SRE Status — All Systems*", ""]

    try:
        client = docker.from_env()
        all_containers = client.containers.list(all=True)
        our = [c for c in all_containers if c.name.startswith("docker-") or c.name.startswith("orthoflow-") or c.name.startswith("htc-")]
        running = [c for c in our if c.status == "running"]
        down = [c.name.replace("docker-", "").replace("-1", "") for c in our if c.status != "running"]

        lines.append(f"{'🟢' if not down else '🔴'} *Infra:* {len(running)}/{len(our)} containers")
        if down:
            lines.append(f"   ⚠️ Down: {', '.join(down[:5])}")
    except Exception as e:
        lines.append(f"🔴 Docker unreachable: {e}")
        return lines

    # Agent health
    agent_names = ["orchestrator", "frontend-agent", "backend-agent", "deploy-agent",
                   "scaffold-agent", "support-agent", "code-agent", "file-agent",
                   "uxui-agent", "qa-agent", "sre-agent", "darius-agent"]
    try:
        agents_down = [a.replace("-agent", "") for a in agent_names if not any(c.name == f"docker-{a}-1" and c.status == "running" for c in all_containers)]
        agents_up_count = len(agent_names) - len(agents_down)
        lines.append(f"{'🟢' if not agents_down else '🔴'} *Agents:* {agents_up_count}/{len(agent_names)} online")
        if agents_down:
            lines.append(f"   ⚠️ Offline: {', '.join(agents_down)}")
    except Exception:
        pass

    # External services
    ext_services = {
        "melanin-tech.com": "production-server",
        "OrthoFlow": "orthoflow-frontend-1",
        "OrthoFlow API": "orthoflow-backend-1",
        "HTC": "docker-htc-frontend-1",
        "HUD": "docker-hud-frontend-1",
        "nginx": "docker-nginx-1",
    }
    ext_up = []
    ext_down = []
    for label, container_name in ext_services.items():
        # Try both docker- prefix and without
        match = next((c for c in all_containers if container_name in c.name and c.status == "running"), None)
        if match:
            ext_up.append(label)
        else:
            ext_down.append(label)

    lines.append(f"{'🟢' if not ext_down else '🔴'} *Services:* {', '.join(ext_up)}")
    if ext_down:
        lines.append(f"   ⚠️ Down: {', '.join(ext_down)}")

    # DB + LLM metrics
    try:
        conn = psycopg2.connect(os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro"))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tickets WHERE status='open'")
        open_tix = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM llm_traces WHERE created_at > NOW() - INTERVAL '24 hours'")
        llm_calls = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM llm_failures WHERE created_at > NOW() - INTERVAL '24 hours'")
        llm_fails = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(AVG(latency_ms), 0) FROM llm_traces WHERE created_at > NOW() - INTERVAL '24 hours' AND status='success'")
        avg_latency = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM llm_traces WHERE created_at > NOW() - INTERVAL '24 hours' AND cached=TRUE")
        cache_hits = cur.fetchone()[0]
        conn.close()

        llm_status = "🟢" if llm_fails == 0 else ("🟡" if llm_fails < 3 else "🔴")
        lines.append(f"{llm_status} *LLM (24h):* {llm_calls} calls, {llm_fails} failures, {cache_hits} cached, avg {avg_latency}ms")
        lines.append(f"🎫 *Tickets:* {open_tix} open")
    except Exception as e:
        lines.append(f"🟡 DB metrics unavailable: {e}")

    return lines


app = create_app("SREAgent", SYSTEM_PROMPT, handle)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
