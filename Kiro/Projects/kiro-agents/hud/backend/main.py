"""Melanin Tech HUD — Internal monitoring dashboard backend."""
import os
import docker
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

app = FastAPI(title="Melanin Tech HUD")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_DSN = os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro")
_HUD_PASSWORD = os.environ.get("HUD_PASSWORD", "melanin-hud-2026")
_INFRA_MODE = os.environ.get("INFRA_MODE", "docker")  # docker | kubernetes


def _db():
    conn = psycopg2.connect(_DSN)
    return conn


# ── Auth (password + TOTP 2FA) ────────────────────────────────────────────────
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import hmac, hashlib, struct, time as _time, base64

_JWT_SECRET = os.environ.get("HUD_JWT_SECRET", "hud-internal-secret")
_TOTP_SECRET = os.environ.get("HUD_TOTP_SECRET", "JBSWY3DPEHPK3PXP")  # base32 encoded, generate your own
security = HTTPBearer(auto_error=False)


def _generate_totp(secret_b32: str) -> str:
    """Generate current TOTP code."""
    key = base64.b32decode(secret_b32.upper())
    counter = struct.pack(">Q", int(_time.time()) // 30)
    h = hmac.HMAC(key, counter, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = (struct.unpack(">I", h[offset:offset+4])[0] & 0x7FFFFFFF) % 1000000
    return f"{code:06d}"


def _verify_totp(secret_b32: str, code: str) -> bool:
    """Verify TOTP code (allows 1 window drift)."""
    key = base64.b32decode(secret_b32.upper())
    for offset in [-1, 0, 1]:
        counter = struct.pack(">Q", (int(_time.time()) // 30) + offset)
        h = hmac.HMAC(key, counter, hashlib.sha1).digest()
        o = h[-1] & 0x0F
        expected = (struct.unpack(">I", h[o:o+4])[0] & 0x7FFFFFFF) % 1000000
        if f"{expected:06d}" == code:
            return True
    return False


def verify_token(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        jwt.decode(creds.credentials, _JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.post("/api/login")
def login(body: dict):
    if body.get("password") != _HUD_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    if not body.get("totp"):
        raise HTTPException(status_code=401, detail="2FA code required")
    if not _verify_totp(_TOTP_SECRET, body["totp"]):
        raise HTTPException(status_code=401, detail="Invalid 2FA code")
    token = jwt.encode({"sub": "admin", "exp": datetime.utcnow().timestamp() + 86400}, _JWT_SECRET, algorithm="HS256")
    return {"token": token}


# ── Executive Dashboard ───────────────────────────────────────────────────────
@app.get("/api/dashboard", dependencies=[Depends(verify_token)])
def dashboard():
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Tickets summary
    cur.execute("SELECT status, COUNT(*) as count FROM tickets GROUP BY status")
    tickets = {r["status"]: r["count"] for r in cur.fetchall()}

    # Recent tickets
    cur.execute("SELECT id, status, agent, LEFT(task, 80) as task, created_at FROM tickets ORDER BY id DESC LIMIT 5")
    recent_tickets = cur.fetchall()

    # Task memory count
    cur.execute("SELECT COUNT(*) as count FROM task_memory")
    memory_count = cur.fetchone()["count"]

    # Container count
    try:
        client = docker.from_env()
        containers = client.containers.list()
        running = len(containers)
    except Exception:
        running = 0

    conn.close()
    return {
        "tickets": tickets,
        "recent_tickets": recent_tickets,
        "memory_entries": memory_count,
        "containers_running": running,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Agents ────────────────────────────────────────────────────────────────────
@app.get("/api/agents", dependencies=[Depends(verify_token)])
def agents():
    agent_list = [
        "orchestrator", "frontend-agent", "backend-agent", "scaffold-agent",
        "deploy-agent", "support-agent", "code-agent", "file-agent",
        "uxui-agent", "darius-agent", "qa-agent",
    ]
    results = []
    try:
        client = docker.from_env()
        for name in agent_list:
            container_name = f"docker-{name}-1"
            try:
                c = client.containers.get(container_name)
                results.append({
                    "name": name,
                    "status": c.status,
                    "uptime": c.attrs["State"]["StartedAt"],
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                })
            except docker.errors.NotFound:
                results.append({"name": name, "status": "not found", "uptime": None, "image": None})
    except Exception as e:
        return {"agents": [], "error": str(e)}

    return {"agents": results}


# ── Infrastructure ────────────────────────────────────────────────────────────
@app.get("/api/infrastructure", dependencies=[Depends(verify_token)])
def infrastructure():
    if _INFRA_MODE == "kubernetes":
        return _k8s_infrastructure()
    return _docker_infrastructure()


def _docker_infrastructure():
    services = []
    # Only show containers relevant to Melanin Tech and our projects
    our_prefixes = ["docker-", "orthoflow-"]
    exclude = ["desktop-", "kind-"]
    try:
        client = docker.from_env()
        for c in client.containers.list(all=True):
            name = c.name
            if not any(name.startswith(p) for p in our_prefixes):
                continue
            if any(name.startswith(e) for e in exclude):
                continue
            services.append({
                "name": name,
                "status": c.status,
                "ports": str(c.ports) if c.ports else "",
                "started": c.attrs["State"]["StartedAt"],
            })
    except Exception as e:
        return {"services": [], "error": str(e)}
    return {"services": sorted(services, key=lambda x: x["name"]), "mode": "docker"}


def _k8s_infrastructure():
    """Query Kubernetes API for pod/service status."""
    try:
        from kubernetes import client as k8s_client, config as k8s_config
        try:
            k8s_config.load_incluster_config()
        except Exception:
            k8s_config.load_kube_config()

        v1 = k8s_client.CoreV1Api()
        services = []

        # Get pods across all namespaces we manage
        namespaces = ["melanin-tech", "melanin-website", "orthoflow", "default"]
        for ns in namespaces:
            try:
                pods = v1.list_namespaced_pod(namespace=ns)
                for pod in pods.items:
                    services.append({
                        "name": f"{ns}/{pod.metadata.name}",
                        "status": pod.status.phase,
                        "ports": "",
                        "started": pod.status.start_time.isoformat() if pod.status.start_time else "",
                        "namespace": ns,
                    })
            except Exception:
                continue

        return {"services": services, "mode": "kubernetes"}
    except ImportError:
        return {"services": [], "error": "kubernetes package not installed", "mode": "kubernetes"}
    except Exception as e:
        return {"services": [], "error": str(e), "mode": "kubernetes"}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "melanin-tech-hud"}


# ── Health History ────────────────────────────────────────────────────────────
@app.get("/api/health/history", dependencies=[Depends(verify_token)])
def health_history(hours: int = 24):
    """Get health snapshots for graphing."""
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM health_snapshots WHERE created_at > NOW() - INTERVAL '%s hours' ORDER BY created_at", (hours,))
    snapshots = cur.fetchall()
    conn.close()
    return {"snapshots": snapshots, "hours": hours}


# ── WebSocket Live Updates ────────────────────────────────────────────────────
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json as _json

_ws_clients: list[WebSocket] = []


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.append(websocket)
    try:
        while True:
            # Send live data every 10 seconds
            try:
                data = _get_live_data()
                await websocket.send_text(_json.dumps(data))
            except Exception:
                break
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.remove(websocket)


def _get_live_data() -> dict:
    """Get current system state for WebSocket push."""
    try:
        client = docker.from_env()
        our = [c for c in client.containers.list(all=True) if c.name.startswith("docker-") or c.name.startswith("orthoflow-")]
        running = len([c for c in our if c.status == "running"])
        total = len(our)
    except Exception:
        running, total = 0, 0

    try:
        conn = psycopg2.connect(_DSN)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tickets WHERE status IN ('open','in_progress')")
        open_tickets = cur.fetchone()[0]
        conn.close()
    except Exception:
        open_tickets = 0

    return {
        "type": "live",
        "containers_running": running,
        "containers_total": total,
        "open_tickets": open_tickets,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Costs ─────────────────────────────────────────────────────────────────────
@app.get("/api/costs", dependencies=[Depends(verify_token)])
def costs():
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Total spend
    cur.execute("SELECT COALESCE(SUM(cost_usd), 0) as total FROM llm_usage")
    total = cur.fetchone()["total"]
    # By model
    cur.execute("SELECT model, SUM(cost_usd) as cost, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens, COUNT(*) as calls FROM llm_usage GROUP BY model ORDER BY cost DESC")
    by_model = cur.fetchall()
    # By agent
    cur.execute("SELECT agent, SUM(cost_usd) as cost, COUNT(*) as calls FROM llm_usage GROUP BY agent ORDER BY cost DESC")
    by_agent = cur.fetchall()
    # Last 7 days daily
    cur.execute("SELECT DATE(created_at) as day, SUM(cost_usd) as cost FROM llm_usage WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY DATE(created_at) ORDER BY day")
    daily = cur.fetchall()
    conn.close()
    return {"total_usd": round(total, 4), "by_model": by_model, "by_agent": by_agent, "daily": daily}


# ── Darius ────────────────────────────────────────────────────────────────────
@app.get("/api/darius", dependencies=[Depends(verify_token)])
def darius():
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT session_id, COUNT(*) as turns FROM darius_sessions GROUP BY session_id ORDER BY MAX(created_at) DESC LIMIT 10")
    sessions = cur.fetchall()
    cur.execute("SELECT COUNT(DISTINCT session_id) as total FROM darius_sessions")
    total = cur.fetchone()["total"]
    conn.close()
    return {"total_sessions": total, "recent_sessions": sessions}


# ── Tickets ───────────────────────────────────────────────────────────────────
@app.get("/api/tickets", dependencies=[Depends(verify_token)])
def tickets():
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, status, agent, LEFT(task, 120) as task, created_at FROM tickets ORDER BY id DESC LIMIT 25")
    rows = cur.fetchall()
    cur.execute("SELECT status, COUNT(*) as count FROM tickets GROUP BY status")
    summary = {r["status"]: r["count"] for r in cur.fetchall()}
    conn.close()
    return {"tickets": rows, "summary": summary}


# ── Memory ────────────────────────────────────────────────────────────────────
@app.get("/api/memory", dependencies=[Depends(verify_token)])
def memory():
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, task, agent, decision, created_at FROM task_memory ORDER BY created_at DESC LIMIT 20")
    task_mem = cur.fetchall()
    cur.execute("SELECT id, role, LEFT(content, 100) as content, created_at FROM conversation_memory ORDER BY created_at DESC LIMIT 20")
    conv_mem = cur.fetchall()
    cur.execute("SELECT COUNT(*) as task_count FROM task_memory")
    task_count = cur.fetchone()["task_count"]
    cur.execute("SELECT COUNT(*) as conv_count FROM conversation_memory")
    conv_count = cur.fetchone()["conv_count"]
    conn.close()
    return {"task_memory": task_mem, "conversation_memory": conv_mem, "task_count": task_count, "conv_count": conv_count}


@app.get("/api/memory/search", dependencies=[Depends(verify_token)])
def memory_search(q: str = ""):
    """Semantic search across task memory."""
    if not q:
        return {"results": []}
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Text search fallback (semantic search requires embedding)
    cur.execute("SELECT id, task, agent, decision, created_at FROM task_memory WHERE task ILIKE %s ORDER BY created_at DESC LIMIT 10", (f"%{q}%",))
    results = cur.fetchall()
    conn.close()
    return {"query": q, "results": results}


# ── Projects ──────────────────────────────────────────────────────────────────
@app.get("/api/projects", dependencies=[Depends(verify_token)])
def projects():
    project_list = []
    try:
        client = docker.from_env()
        # Melanin Tech Website
        try:
            c = client.containers.get("docker-production-server-1")
            project_list.append({"name": "melanin-tech.com", "status": c.status, "url": "https://www.melanin-tech.com", "started": c.attrs["State"]["StartedAt"]})
        except Exception:
            project_list.append({"name": "melanin-tech.com", "status": "unknown", "url": "https://www.melanin-tech.com", "started": None})
        # OrthoFlow
        try:
            c = client.containers.get("orthoflow-frontend-1")
            project_list.append({"name": "OrthoFlow AI", "status": c.status, "url": "https://app.orthoflowsolutions.com", "started": c.attrs["State"]["StartedAt"]})
        except Exception:
            project_list.append({"name": "OrthoFlow AI", "status": "unknown", "url": "https://app.orthoflowsolutions.com", "started": None})
    except Exception:
        pass
    return {"projects": project_list}


# ── Security ──────────────────────────────────────────────────────────────────
@app.get("/api/security", dependencies=[Depends(verify_token)])
def security():
    import subprocess
    results = {}
    # Cert expiry
    try:
        r = subprocess.run(["openssl", "x509", "-enddate", "-noout", "-in", "/etc/letsencrypt/live/melanin-tech.com/fullchain.pem"], capture_output=True, text=True, timeout=5)
        results["cert_expiry"] = r.stdout.strip().replace("notAfter=", "") if r.returncode == 0 else "unknown"
    except Exception:
        results["cert_expiry"] = "unable to check"
    # Fail2ban status + ban list
    try:
        client = docker.from_env()
        f2b = client.containers.get("docker-fail2ban-1")
        results["fail2ban"] = f2b.status
        # Get banned IPs
        try:
            exit_code, output = f2b.exec_run("fail2ban-client status nginx-limit-req")
            if exit_code == 0:
                lines = output.decode().split("\n")
                ban_line = [l for l in lines if "Banned IP" in l or "banned" in l.lower()]
                results["banned_ips"] = ban_line[0].strip() if ban_line else "0 banned"
            else:
                results["banned_ips"] = "unable to query"
        except Exception:
            results["banned_ips"] = "unable to query"
    except Exception:
        results["fail2ban"] = "not found"
        results["banned_ips"] = "n/a"
    results["npm_audit"] = "last run: see CI"
    return results


# ── Clients ───────────────────────────────────────────────────────────────────
@app.get("/api/clients", dependencies=[Depends(verify_token)])
def clients():
    """OrthoFlow client accounts — metadata + usage metrics."""
    try:
        import psycopg2 as pg2
        conn = pg2.connect(os.environ.get("ORTHOFLOW_DSN", "postgresql://orthoflow:changeme@host.docker.internal:5433/orthoflow"))
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, name, created_at FROM practices ORDER BY created_at DESC")
        practices = cur.fetchall()
        cur.execute("SELECT practice_id, COUNT(*) as invoice_count, SUM(total_amount) as total_spend FROM invoices GROUP BY practice_id")
        usage = {str(r["practice_id"]): {"invoices": r["invoice_count"], "spend": float(r["total_spend"] or 0)} for r in cur.fetchall()}
        conn.close()
        for p in practices:
            u = usage.get(str(p["id"]), {"invoices": 0, "spend": 0})
            p["invoice_count"] = u["invoices"]
            p["total_spend"] = round(u["spend"], 2)
        return {"clients": practices}
    except Exception as e:
        return {"clients": [], "error": str(e)}


# ── Container Health Alerting ─────────────────────────────────────────────────
import threading
import httpx as _httpx

_SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
_SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")
_alerted: set = set()


def _check_containers():
    """Background thread: check container health every 60s, alert on failures, store snapshots."""
    import time
    while True:
        time.sleep(60)
        try:
            client = docker.from_env()
            all_containers = client.containers.list(all=True)
            our_containers = [c for c in all_containers if c.name.startswith("docker-") or c.name.startswith("orthoflow-")]
            running = [c for c in our_containers if c.status == "running"]

            # Alert on failures
            for c in our_containers:
                if c.status in ("exited", "dead") and c.name not in _alerted:
                    _alerted.add(c.name)
                    _send_alert(f"🚨 *Container Down:* `{c.name}` — status: {c.status}")
                elif c.status == "running" and c.name in _alerted:
                    _alerted.discard(c.name)

            # Store health snapshot every 5 minutes
            if int(time.time()) % 300 < 60:
                try:
                    conn = psycopg2.connect(_DSN)
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM task_memory")
                    mem = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM tickets WHERE status='open'")
                    t_open = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM tickets WHERE status='done'")
                    t_done = cur.fetchone()[0]
                    cur.execute("INSERT INTO health_snapshots (containers_running, containers_total, memory_entries, tickets_open, tickets_done) VALUES (%s,%s,%s,%s,%s)",
                                (len(running), len(our_containers), mem, t_open, t_done))
                    # Purge snapshots older than 90 days
                    cur.execute("DELETE FROM health_snapshots WHERE created_at < NOW() - INTERVAL '365 days'")
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
        except Exception:
            pass


def _send_alert(message: str):
    if not _SLACK_TOKEN or not _SLACK_CHANNEL:
        return
    try:
        _httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {_SLACK_TOKEN}", "Content-Type": "application/json"},
            json={"channel": _SLACK_CHANNEL, "text": message},
            timeout=10,
        )
    except Exception:
        pass


# Start health monitor in background
threading.Thread(target=_check_containers, daemon=True).start()


# ── Contracts Tab ─────────────────────────────────────────────────────────────


@app.get("/api/contracts", dependencies=[Depends(verify_token)])
def contracts():
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM contracts ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    for r in rows:
        for k in ("bill_rate", "firm_margin", "net_rate", "total_invoiced", "total_paid", "outstanding"):
            if r.get(k) is not None:
                r[k] = float(r[k])
    active = [c for c in rows if c["status"] == "active"]
    monthly_revenue = sum(c["net_rate"] * c["hours_per_week"] * 4.33 for c in active)
    outstanding = sum(c["outstanding"] for c in rows)
    return {
        "contracts": rows,
        "stats": {
            "active": len(active),
            "monthly_revenue": round(monthly_revenue),
            "outstanding": round(outstanding),
            "avg_net_rate": round(sum(c["net_rate"] for c in active) / max(len(active), 1)),
        },
    }


@app.post("/api/contracts", dependencies=[Depends(verify_token)])
def create_contract(body: dict):
    conn = _db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO contracts (client, staffing_firm, role, bill_rate, firm_margin, net_rate, status, start_date, end_date, hours_per_week)
        VALUES (%(client)s, %(staffing_firm)s, %(role)s, %(bill_rate)s, %(firm_margin)s, %(net_rate)s, %(status)s, %(start_date)s, %(end_date)s, %(hours_per_week)s)
        RETURNING id""", body)
    new_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return {"id": new_id, "status": "created"}


@app.put("/api/contracts/{contract_id}", dependencies=[Depends(verify_token)])
def update_contract(contract_id: str, body: dict):
    conn = _db()
    cur = conn.cursor()
    sets = ", ".join(f"{k} = %({k})s" for k in body if k != "id")
    body["contract_id"] = contract_id
    cur.execute(f"UPDATE contracts SET {sets}, updated_at = NOW() WHERE id = %(contract_id)s", body)
    conn.commit()
    conn.close()
    return {"id": contract_id, "status": "updated"}


@app.delete("/api/contracts/{contract_id}", dependencies=[Depends(verify_token)])
def delete_contract(contract_id: str):
    conn = _db()
    cur = conn.cursor()
    cur.execute("DELETE FROM contracts WHERE id = %s", (contract_id,))
    conn.commit()
    conn.close()
    return {"id": contract_id, "status": "deleted"}


@app.post("/api/contracts/darius", dependencies=[Depends(verify_token)])
def contracts_darius(body: dict):
    """Proxy to Darius agent for contract intelligence."""
    import httpx as _hx
    prompt = body.get("message", "")
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, client, role, net_rate, status, outstanding, end_date FROM contracts ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    active = [c for c in rows if c["status"] == "active"]
    summary = f"Active: {len(active)}, Total outstanding: ${sum(float(c['outstanding']) for c in rows):.0f}, Avg rate: ${sum(float(c['net_rate']) for c in active)/max(len(active),1):.0f}/hr"
    brief = "; ".join(f"{c['id']} {c['client']} ${float(c['net_rate'])}/hr {c['status']}" for c in rows)
    context = f"{summary}. Contracts: {brief}"
    try:
        r = _hx.post(
            "http://darius-agent:8000/task",
            json={"task": f"[Contract Management] {context}\n\nUser: {prompt}", "project": "melanin-contracts", "session_id": "hud-contracts"},
            timeout=60,
        )
        data = r.json()
        return {"reply": data.get("args", {}).get("proposal", "No response from Darius.")}
    except Exception as e:
        return {"reply": f"Darius unavailable: {e}"}


# ── Governance Tab ────────────────────────────────────────────────────────────

@app.get("/api/governance", dependencies=[Depends(verify_token)])
def governance():
    import glob, re
    gov_dir = "/app/governance" if os.path.isdir("/app/governance") else os.path.join(os.path.dirname(__file__), "../../governance")
    policies = []
    for f in sorted(glob.glob(os.path.join(gov_dir, "*.md"))):
        name = os.path.basename(f).replace(".md", "").replace("-", " ").title()
        with open(f) as fh:
            content = fh.read()
        policies.append({"name": name, "file": os.path.basename(f), "lines": len(content.splitlines())})

    # Compliance summary from checklist
    checklist_path = os.path.join(gov_dir, "compliance-checklist.md")
    done = todo = pending = 0
    if os.path.isfile(checklist_path):
        with open(checklist_path) as fh:
            text = fh.read()
        done = text.count("✅")
        todo = text.count("🔲")
        pending = text.count("⚠️")

    # Open governance-related tickets
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, status, LEFT(task, 100) as task FROM tickets WHERE task ILIKE '%governance%' OR task ILIKE '%compliance%' OR task ILIKE '%security%' OR task ILIKE '%BAA%' OR task ILIKE '%vulnerability%' OR task ILIKE '%penetration%' OR task ILIKE '%disaster%' OR task ILIKE '%non-root%' ORDER BY id")
    gov_tickets = cur.fetchall()
    conn.close()

    return {
        "policies": policies,
        "compliance": {"done": done, "todo": todo, "pending": pending},
        "tickets": gov_tickets,
        "summary": {
            "total_policies": len(policies),
            "controls_passed": done,
            "controls_pending": todo + pending,
            "open_tickets": len([t for t in gov_tickets if t["status"] == "open"]),
        }
    }


@app.post("/api/governance/darius", dependencies=[Depends(verify_token)])
def governance_darius(body: dict):
    """Proxy to Darius for governance/compliance questions."""
    import httpx as _hx
    prompt = body.get("message", "")
    gov_dir = "/app/governance" if os.path.isdir("/app/governance") else os.path.join(os.path.dirname(__file__), "../../governance")
    policies = [f.replace(".md", "") for f in os.listdir(gov_dir) if f.endswith(".md")]
    context = f"Governance policies: {', '.join(policies)}. Ask about any specific policy for details."
    try:
        r = _hx.post("http://darius-agent:8000/task",
            json={"task": f"[Governance & Compliance] {context}\n\nUser: {prompt}", "project": "melanin-governance", "session_id": "hud-governance"},
            timeout=60)
        data = r.json()
        return {"reply": data.get("args", {}).get("proposal", "No response from Darius.")}
    except Exception as e:
        return {"reply": f"Darius unavailable: {e}"}


# ── SRE Monitoring Tabs ───────────────────────────────────────────────────────

@app.get("/api/sre/internal", dependencies=[Depends(verify_token)])
def sre_internal():
    """SRE view: internal infrastructure — agents, databases, queues, orchestrator."""
    client = docker.from_env()
    internal_services = [
        "docker-orchestrator-1", "docker-postgres-1", "docker-ollama-1",
        "docker-hud-1", "docker-hud-frontend-1", "docker-mcp-server-1",
        "docker-darius-agent-1", "docker-frontend-agent-1", "docker-backend-agent-1",
        "docker-deploy-agent-1", "docker-scaffold-agent-1", "docker-support-agent-1",
        "docker-code-agent-1", "docker-file-agent-1", "docker-uxui-agent-1",
        "docker-qa-agent-1", "docker-mcp-github-1", "docker-mcp-postgres-1",
        "docker-mcp-figma-1", "docker-mcp-fetch-1", "docker-playwright-mcp-1",
        "docker-security-watchdog-1", "docker-redis-1", "docker-vaultwarden-1",
    ]
    services = []
    for name in internal_services:
        try:
            c = client.containers.get(name)
            started = c.attrs.get("State", {}).get("StartedAt", "")
            services.append({"name": name.replace("docker-", "").replace("-1", ""), "status": c.status, "started": started})
        except Exception:
            services.append({"name": name.replace("docker-", "").replace("-1", ""), "status": "not found", "started": ""})

    running = len([s for s in services if s["status"] == "running"])
    down = len([s for s in services if s["status"] != "running"])

    # DB health
    db_health = "unknown"
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        db_health = "healthy"
        conn.close()
    except Exception:
        db_health = "unhealthy"

    return {
        "services": services,
        "summary": {"running": running, "down": down, "total": len(services), "db_health": db_health},
    }


@app.get("/api/sre/external", dependencies=[Depends(verify_token)])
def sre_external():
    """SRE view: external-facing — production, staging, OrthoFlow, nginx, certs, DNS."""
    import httpx as _hx
    client = docker.from_env()

    external_services = [
        "docker-production-server-1", "docker-staging-server-1", "docker-testing-server-1",
        "docker-preview-server-1", "docker-nginx-1", "docker-certbot-1",
        "docker-cloudflare-ddns-1", "docker-fail2ban-1", "docker-cert-monitor-1",
        "orthoflow-frontend-1", "orthoflow-backend-1", "orthoflow-postgres-1",
        "orthoflow-redis-1", "orthoflow-minio-1", "orthoflow-worker-1", "orthoflow-ollama-1",
    ]
    services = []
    for name in external_services:
        try:
            c = client.containers.get(name)
            started = c.attrs.get("State", {}).get("StartedAt", "")
            services.append({"name": name.replace("docker-", "").replace("-1", ""), "status": c.status, "started": started})
        except Exception:
            services.append({"name": name.replace("docker-", "").replace("-1", ""), "status": "not found", "started": ""})

    running = len([s for s in services if s["status"] == "running"])
    down = len([s for s in services if s["status"] != "running"])

    # Endpoint health checks
    endpoints = []
    for url, label in [
        ("http://production-server:3000", "melanin-tech.com"),
        ("http://staging-server:3003", "staging"),
        ("http://testing-server:3002", "testing"),
        ("http://nginx:80", "nginx"),
    ]:
        try:
            r = _hx.get(url, timeout=5, follow_redirects=True)
            endpoints.append({"name": label, "status": "up", "code": r.status_code, "latency_ms": int(r.elapsed.total_seconds() * 1000)})
        except Exception:
            endpoints.append({"name": label, "status": "down", "code": 0, "latency_ms": 0})

    # TLS cert expiry
    cert_expiry = "unknown"
    try:
        c = client.containers.get("docker-nginx-1")
        result = c.exec_run("cat /etc/letsencrypt/live/melanin-tech.com/fullchain.pem")
        if result.exit_code == 0:
            import subprocess
            p = subprocess.run(["openssl", "x509", "-enddate", "-noout"], input=result.output, capture_output=True)
            cert_expiry = p.stdout.decode().strip().replace("notAfter=", "")
    except Exception:
        pass

    return {
        "services": services,
        "endpoints": endpoints,
        "cert_expiry": cert_expiry,
        "summary": {"running": running, "down": down, "total": len(services)},
    }


@app.post("/api/sre/darius", dependencies=[Depends(verify_token)])
def sre_darius(body: dict):
    """Proxy to Darius for SRE questions."""
    import httpx as _hx
    prompt = body.get("message", "")
    scope = body.get("scope", "all")
    try:
        r = _hx.post("http://darius-agent:8000/task",
            json={"task": f"[SRE — {scope}] You are monitoring Melanin Technologies infrastructure. User: {prompt}", "project": "melanin-sre", "session_id": "hud-sre"},
            timeout=60)
        data = r.json()
        return {"reply": data.get("args", {}).get("proposal", "No response from Darius.")}
    except Exception as e:
        return {"reply": f"Darius unavailable: {e}"}


# ── Chart Data (Grafana-style time-series) ────────────────────────────────────

@app.get("/api/charts/executive", dependencies=[Depends(verify_token)])
def charts_executive():
    """Time-series data for Executive dashboard charts."""
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT containers_running, containers_total, memory_entries, tickets_open, tickets_done, created_at FROM health_snapshots ORDER BY created_at DESC LIMIT 288")
    snapshots = list(reversed(cur.fetchall()))

    cur.execute("""
        SELECT DATE(created_at) as date, status, COUNT(*) as count
        FROM tickets WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY DATE(created_at), status ORDER BY date
    """)
    ticket_trend = cur.fetchall()

    cur.execute("SELECT agent, COUNT(*) as count FROM tickets GROUP BY agent ORDER BY count DESC")
    agent_dist = cur.fetchall()

    cur.execute("""
        SELECT DATE(created_at) as date, SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens, SUM(cost_usd) as cost
        FROM llm_usage WHERE created_at > NOW() - INTERVAL '7 days'
        GROUP BY DATE(created_at) ORDER BY date
    """)
    llm_usage = cur.fetchall()

    conn.close()

    for row in snapshots:
        row["created_at"] = row["created_at"].isoformat() if row.get("created_at") else None
    for row in ticket_trend:
        row["date"] = str(row["date"])
    for row in llm_usage:
        row["date"] = str(row["date"])
        row["cost"] = float(row["cost"]) if row["cost"] else 0

    return {"snapshots": snapshots, "ticket_trend": ticket_trend, "agent_distribution": agent_dist, "llm_usage": llm_usage}


@app.get("/api/charts/sre", dependencies=[Depends(verify_token)])
def charts_sre():
    """Time-series for SRE tabs: container health, tickets open/done over time."""
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT containers_running, containers_total, tickets_open, tickets_done, created_at FROM health_snapshots ORDER BY created_at DESC LIMIT 288")
    snapshots = list(reversed(cur.fetchall()))
    conn.close()
    for row in snapshots:
        row["created_at"] = row["created_at"].isoformat() if row.get("created_at") else None
    return {"snapshots": snapshots}


@app.get("/api/charts/agents", dependencies=[Depends(verify_token)])
def charts_agents():
    """Chart data for Agents tab: tasks per agent, ticket status by agent."""
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT agent, COUNT(*) as total, SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done, SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) as open FROM tickets GROUP BY agent ORDER BY total DESC")
    by_agent = cur.fetchall()
    cur.execute("""
        SELECT agent, DATE(created_at) as date, COUNT(*) as count
        FROM tickets WHERE created_at > NOW() - INTERVAL '14 days'
        GROUP BY agent, DATE(created_at) ORDER BY date
    """)
    trend = cur.fetchall()
    conn.close()
    for r in trend:
        r["date"] = str(r["date"])
    return {"by_agent": by_agent, "trend": trend}


@app.get("/api/charts/contracts", dependencies=[Depends(verify_token)])
def charts_contracts():
    """Chart data for Contracts tab: revenue trend, outstanding balance."""
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT client, net_rate, hours_per_week, outstanding, status FROM contracts ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()
    for r in rows:
        for k in ("net_rate", "hours_per_week", "outstanding"):
            if r.get(k) is not None:
                r[k] = float(r[k])
    active = [r for r in rows if r["status"] == "active"]
    revenue_by_client = [{"name": r["client"][:12], "value": round(r["net_rate"] * r["hours_per_week"] * 4.33)} for r in active]
    outstanding_by_client = [{"name": r["client"][:12], "value": round(r["outstanding"])} for r in rows if r["outstanding"] > 0]
    return {"revenue_by_client": revenue_by_client, "outstanding_by_client": outstanding_by_client}


@app.get("/api/charts/tickets", dependencies=[Depends(verify_token)])
def charts_tickets():
    """Chart data for Tickets tab: daily open/close trend."""
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as opened
        FROM tickets WHERE created_at > NOW() - INTERVAL '30 days'
        GROUP BY DATE(created_at) ORDER BY date
    """)
    opened = cur.fetchall()
    cur.execute("SELECT agent, COUNT(*) as count FROM tickets WHERE created_at > NOW() - INTERVAL '30 days' GROUP BY agent ORDER BY count DESC LIMIT 8")
    by_agent = cur.fetchall()
    conn.close()
    for r in opened:
        r["date"] = str(r["date"])
    return {"opened_trend": opened, "by_agent": by_agent}
