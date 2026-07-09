"""Melanin Tech HUD — Internal monitoring dashboard backend."""
import os
import threading
import docker
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime


@asynccontextmanager
async def lifespan(app):
    # Startup: launch health monitor thread
    # _check_containers is defined later in this file but available at runtime
    threading.Thread(target=_check_containers, daemon=True).start()
    print("[HUD] Health monitor thread started", flush=True)
    yield
    # Shutdown: nothing to clean up (daemon thread dies with process)


app = FastAPI(title="Melanin Tech HUD", lifespan=lifespan)
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
    """Background thread: check container health every 60s, alert on failures, store snapshots, send 12hr SRE digest, daily email triage."""
    import time
    _last_digest = time.time()
    _last_email_triage = time.time()
    _last_snapshot = 0  # Force first snapshot immediately
    DIGEST_INTERVAL = 43200  # 12 hours
    EMAIL_TRIAGE_INTERVAL = 86400  # 24 hours (daily)

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
            if time.time() - _last_snapshot >= 300:
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
                    cur.execute("DELETE FROM health_snapshots WHERE created_at < NOW() - INTERVAL '365 days'")

                    # Auto-calculate error budget consumption
                    cur.execute("""
                        SELECT name, target, window_hours FROM llm_slos
                    """)
                    slos = cur.fetchall()
                    for slo_name, target, window_hours in slos:
                        target = float(target)  # DB returns Decimal, need float for math
                        period_start = f"NOW() - INTERVAL '{window_hours} hours'"
                        if slo_name == 'agent_availability':
                            # Exclude HUD timeout errors — those are network timeouts, not LLM failures
                            cur.execute(f"""
                                SELECT COUNT(*) as total,
                                       COUNT(*) FILTER (WHERE status='success') as success
                                FROM llm_traces
                                WHERE created_at > {period_start}
                                  AND COALESCE(task_preview, '') NOT LIKE '%%HUD timeout%%'
                            """)
                            total, success = cur.fetchone()
                            if total == 0:
                                continue  # No data — skip, don't report as failure
                            current = (success / total) * 100
                            budget_total = 100 - target  # e.g., 0.5% error budget
                            consumed = max(0, (100 - current))
                        elif slo_name == 'error_rate':
                            # Exclude HUD timeout errors from error counting
                            cur.execute(f"""
                                SELECT COUNT(*) as total,
                                       COUNT(*) FILTER (WHERE status != 'success'
                                           AND COALESCE(task_preview, '') NOT LIKE '%%HUD timeout%%') as errors
                                FROM llm_traces
                                WHERE created_at > {period_start}
                            """)
                            total, errors = cur.fetchone()
                            if total == 0:
                                continue  # No data — skip, don't report as failure
                            current = (errors / total) * 100
                            budget_total = target  # 2% allowed
                            consumed = current
                        elif slo_name == 'latency_p95':
                            cur.execute(f"""
                                SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95
                                FROM llm_traces
                                WHERE created_at > {period_start}
                                  AND status = 'success'
                                  AND cached = FALSE
                            """)
                            row = cur.fetchone()
                            p95 = row[0] if row and row[0] else 0
                            # target is in ms (e.g., 30000 = 30s)
                            budget_total = target
                            consumed = p95
                            current = p95
                        elif slo_name == 'cache_hit_rate':
                            cur.execute(f"""
                                SELECT COUNT(*) as total,
                                       COUNT(*) FILTER (WHERE cached = TRUE) as hits
                                FROM llm_traces
                                WHERE created_at > {period_start}
                            """)
                            total, hits = cur.fetchone()
                            if total == 0:
                                continue
                            current = (hits / total) * 100
                            # For cache hit rate, budget is inverse — we want >= target
                            # consumed represents how much below target we are
                            budget_total = target  # e.g., 20%
                            consumed = max(0, target - current)
                        elif slo_name == 'token_budget_daily':
                            cur.execute("SELECT COALESCE(SUM(input_tokens), 0) FROM llm_traces WHERE created_at > NOW() - INTERVAL '24 hours'")
                            tokens = cur.fetchone()[0]
                            budget_total = target
                            consumed = tokens
                            current = tokens
                        else:
                            continue

                        remaining = max(0, budget_total - consumed)
                        status_val = 'healthy' if consumed < budget_total * 0.8 else ('warning' if consumed < budget_total else 'exhausted')

                        cur.execute("""
                            INSERT INTO llm_error_budgets (slo_name, period_start, period_end, budget_total, budget_consumed, budget_remaining, status)
                            VALUES (%s, NOW() - INTERVAL '%s hours', NOW(), %s, %s, %s, %s)
                        """, (slo_name, window_hours, budget_total, consumed, remaining, status_val))

                        # Alert on budget exhaustion
                        if status_val == 'exhausted' and slo_name not in _alerted:
                            _alerted.add(f"budget_{slo_name}")
                            _send_alert(f"🔴 *Error Budget Exhausted:* `{slo_name}` — consumed {consumed:.1f} / {budget_total:.1f}")

                    conn.commit()
                    conn.commit()
                    conn.close()
                    _last_snapshot = time.time()
                    print(f"[HUD-WATCHDOG] Snapshot written successfully", flush=True)
                except Exception as snap_err:
                    print(f"[HUD-WATCHDOG] Snapshot write FAILED: {snap_err}", flush=True)
                    _last_snapshot = time.time()  # don't retry immediately on error

            # 12-hour SRE Digest
            if time.time() - _last_digest >= DIGEST_INTERVAL:
                _last_digest = time.time()
                _send_sre_digest(our_containers, running)

            # Daily email triage (every 24h, posts to Slack)
            if time.time() - _last_email_triage >= EMAIL_TRIAGE_INTERVAL:
                _last_email_triage = time.time()
                _run_daily_email_triage()

            # Credit budget check (every 5 min, alert at 80%)
            if time.time() - _last_snapshot >= 300:
                _check_credit_budget()
                _check_endpoint_health()

        except Exception as _watchdog_err:
            import traceback; print(f"[HUD-WATCHDOG] Loop error: {_watchdog_err}"); traceback.print_exc()


# ── Credit Budget Monitoring ──────────────────────────────────────────────────

_MONTHLY_BUDGET_USD = float(os.environ.get("LLM_MONTHLY_BUDGET_USD", "25.00"))
_BUDGET_ALERT_THRESHOLD = 0.80  # 80%
_budget_alerted_this_month = False


def _check_credit_budget():
    """Check if LLM spend is approaching monthly budget. Alert Slack at 80%."""
    global _budget_alerted_this_month
    try:
        conn = psycopg2.connect(_DSN)
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_traces WHERE created_at > date_trunc('month', NOW())")
        spent = float(cur.fetchone()[0])

        # Reset alert flag on new month
        cur.execute("SELECT EXTRACT(DAY FROM NOW())")
        day = int(cur.fetchone()[0])
        if day == 1:
            _budget_alerted_this_month = False

        conn.close()

        utilization = spent / _MONTHLY_BUDGET_USD if _MONTHLY_BUDGET_USD > 0 else 0

        if utilization >= _BUDGET_ALERT_THRESHOLD and not _budget_alerted_this_month:
            _budget_alerted_this_month = True
            _send_alert(
                f"⚠️ *LLM Credit Alert — {utilization*100:.0f}% of monthly budget used*\n"
                f"  • Spent: ${spent:.2f} / ${_MONTHLY_BUDGET_USD:.2f}\n"
                f"  • Remaining: ${_MONTHLY_BUDGET_USD - spent:.2f}\n"
                f"  • Action: Reduce usage or increase budget in `LLM_MONTHLY_BUDGET_USD` env var"
            )
    except Exception:
        pass


def _send_sre_digest(all_containers, running):
    """Generate and send 12-hour SRE analysis report to Slack."""
    try:
        conn = psycopg2.connect(_DSN)
        cur = conn.cursor()

        # Container stats
        total = len(all_containers)
        running_count = len(running)
        down = [c.name.replace("docker-", "").replace("-1", "") for c in all_containers if c.status != "running" and (c.name.startswith("docker-") or c.name.startswith("orthoflow-"))]

        # Agent health
        agent_names = ["orchestrator", "frontend-agent", "backend-agent", "deploy-agent",
                       "scaffold-agent", "support-agent", "code-agent", "file-agent",
                       "uxui-agent", "qa-agent", "sre-agent", "darius-agent"]
        agents_up = []
        agents_down = []
        for name in agent_names:
            container_name = f"docker-{name}-1"
            match = next((c for c in all_containers if c.name == container_name), None)
            if match and match.status == "running":
                agents_up.append(name.replace("-agent", "").replace("-", ""))
            else:
                agents_down.append(name.replace("-agent", "").replace("-", ""))

        # Ticket activity (12h)
        cur.execute("SELECT status, COUNT(*) FROM tickets WHERE updated_at > NOW() - INTERVAL '12 hours' GROUP BY status")
        ticket_activity = {row[0]: row[1] for row in cur.fetchall()}

        # LLM metrics (12h)
        cur.execute("SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE status = 'success') as success, COALESCE(SUM(input_tokens + output_tokens), 0) as tokens, COALESCE(SUM(cost_usd), 0) as cost, COALESCE(AVG(latency_ms), 0) as avg_latency, COUNT(*) FILTER (WHERE cached = TRUE) as cache_hits FROM llm_traces WHERE created_at > NOW() - INTERVAL '12 hours'")
        llm = cur.fetchone()
        llm_total, llm_success, llm_tokens, llm_cost, llm_avg_latency, llm_cache_hits = llm or (0, 0, 0, 0, 0, 0)

        # Failures (12h)
        cur.execute("SELECT failure_type, COUNT(*) FROM llm_failures WHERE created_at > NOW() - INTERVAL '12 hours' GROUP BY failure_type")
        failures = {row[0]: row[1] for row in cur.fetchall()}

        # SLO compliance
        if llm_total > 0:
            availability = (llm_success / llm_total) * 100
            error_rate = 100 - availability
            cache_rate = (llm_cache_hits / llm_total) * 100
        else:
            availability = None
            error_rate = None
            cache_rate = None

        conn.close()

        # Build report
        lines = [
            "📊 *SRE 12-Hour Digest*",
            "",
            "*Infrastructure*",
            f"  • Containers: {running_count}/{total} running",
        ]
        if down:
            lines.append(f"  • ⚠️ Down: {', '.join(down[:5])}")
        else:
            lines.append("  • ✅ All services healthy")

        lines.extend([
            "",
            "*Agent Health*",
            f"  • ✅ Online ({len(agents_up)}/{len(agent_names)}): {', '.join(agents_up)}",
        ])
        if agents_down:
            lines.append(f"  • ❌ Offline: {', '.join(agents_down)}")

        lines.extend([
            "",
            "*LLM Performance*",
            f"  • Calls: {llm_total} ({llm_success} success, {llm_total - llm_success} failed)",
            f"  • Tokens: {int(llm_tokens):,} ({int(llm_cache_hits)} cache hits, {cache_rate:.0f}% hit rate)",
            f"  • Avg latency: {int(llm_avg_latency)}ms | Cost: ${float(llm_cost):.4f}",
        ])

        if failures:
            lines.append(f"  • Failures: {', '.join(f'{t}({c})' for t, c in failures.items())}")

        lines.extend([
            "",
            "*SLO Status*",
        ])
        if availability is not None:
            lines.extend([
                f"  • Availability: {'✅' if availability >= 99.5 else '❌'} {availability:.1f}% (target: 99.5%)",
                f"  • Error rate: {'✅' if error_rate <= 2 else '❌'} {error_rate:.1f}% (target: <2%)",
                f"  • Cache hit: {'✅' if cache_rate >= 20 else '⚠️'} {cache_rate:.0f}% (target: >20%)",
            ])
        else:
            lines.append("  • ℹ️ No LLM calls in this period — SLOs not applicable")

        if ticket_activity:
            lines.extend(["", "*Ticket Activity (12h)*"])
            for status, count in ticket_activity.items():
                emoji = {"done": "✅", "open": "🟡", "cancelled": "⛔"}.get(status, "⚪")
                lines.append(f"  • {emoji} {status}: {count}")

        _send_alert("\n".join(lines))

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


# ── Knowledge Graph API ───────────────────────────────────────────────────────
import re
import pathlib

_GRAPHIFY_PATH = pathlib.Path("/app/graphify-out/graph.json")
_MELANIN_DOCS_PATH = pathlib.Path("/app/melanin-docs")
_GRAPH_CACHE: dict = {}
_GRAPH_CACHE_TIME: float = 0

# Documents to exclude (read-only policy)
_EXCLUDED_DIRS = {"Finance", "sessions"}


def _parse_markdown_sections(filepath: pathlib.Path) -> list[dict]:
    """Parse a markdown file into sections at h2 (##) level."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return []

    sections = []
    current_section = None
    current_lines: list[str] = []
    doc_name = filepath.stem

    for line in content.split("\n"):
        if line.startswith("## "):
            # Save previous section
            if current_section:
                sections.append({
                    "id": f"doc_{doc_name}_{current_section}".lower().replace(" ", "_").replace("/", "_")[:80],
                    "label": current_section,
                    "file_type": "doc",
                    "source_file": str(filepath.relative_to(_MELANIN_DOCS_PATH)) if _MELANIN_DOCS_PATH.exists() else filepath.name,
                    "content": "\n".join(current_lines).strip()[:500],
                    "_origin": "melanin-docs",
                    "community_name": f"Doc: {doc_name}",
                })
            current_section = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Last section
    if current_section:
        sections.append({
            "id": f"doc_{doc_name}_{current_section}".lower().replace(" ", "_").replace("/", "_")[:80],
            "label": current_section,
            "file_type": "doc",
            "source_file": str(filepath.relative_to(_MELANIN_DOCS_PATH)) if _MELANIN_DOCS_PATH.exists() else filepath.name,
            "content": "\n".join(current_lines).strip()[:500],
            "_origin": "melanin-docs",
            "community_name": f"Doc: {doc_name}",
        })

    return sections


def _parse_glossary_concepts(filepath: pathlib.Path) -> list[dict]:
    """Extract concept nodes from the Glossary (each bolded term in a table row)."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return []

    concepts = []
    current_category = "General"

    for line in content.split("\n"):
        if line.startswith("## "):
            current_category = line[3:].strip()
        # Match table rows: | **Term** | Definition |
        match = re.match(r"\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|", line)
        if match:
            term = match.group(1).strip()
            definition = match.group(2).strip()
            concepts.append({
                "id": f"concept_{term}".lower().replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")[:80],
                "label": term,
                "file_type": "concept",
                "source_file": "Glossary.md",
                "content": definition,
                "_origin": "glossary",
                "community_name": f"Concept: {current_category}",
            })

    return concepts


def _get_doc_nodes() -> tuple[list[dict], list[dict]]:
    """Parse all MelaninDocs into nodes and infer edges."""
    nodes = []
    edges = []

    if not _MELANIN_DOCS_PATH.exists():
        return nodes, edges

    # Walk MelaninDocs for markdown files
    doc_files: list[pathlib.Path] = []
    for f in _MELANIN_DOCS_PATH.rglob("*.md"):
        # Skip excluded directories and duplicate files (macOS " 2.md" copies)
        if any(part in _EXCLUDED_DIRS for part in f.parts):
            continue
        if " 2.md" in f.name:
            continue
        doc_files.append(f)

    # Create a top-level node for each document
    doc_top_nodes = []
    for f in doc_files:
        doc_id = f"doc_{f.stem}".lower().replace(" ", "_")[:60]
        doc_top_nodes.append({
            "id": doc_id,
            "label": f.stem.replace("_", " "),
            "file_type": "doc",
            "source_file": str(f.relative_to(_MELANIN_DOCS_PATH)),
            "content": "",
            "_origin": "melanin-docs",
            "community_name": "MelaninDocs",
        })
        nodes.append(doc_top_nodes[-1])

        # Parse sections
        sections = _parse_markdown_sections(f)
        for section in sections:
            nodes.append(section)
            edges.append({
                "source": doc_id,
                "target": section["id"],
                "label": "has_section",
                "type": "contains",
            })

    # Parse Glossary for concept nodes
    glossary_path = _MELANIN_DOCS_PATH / "Glossary.md"
    if glossary_path.exists():
        concepts = _parse_glossary_concepts(glossary_path)
        for concept in concepts:
            nodes.append(concept)
            # Link concept to glossary doc
            edges.append({
                "source": "doc_glossary",
                "target": concept["id"],
                "label": "defines",
                "type": "defines",
            })

    # Infer cross-references: if a concept term appears in a doc section, create an edge
    concept_labels = {n["id"]: n["label"] for n in nodes if n["file_type"] == "concept"}
    section_nodes = [n for n in nodes if n["file_type"] == "doc" and n.get("content")]

    for section in section_nodes:
        content_lower = section.get("content", "").lower()
        for concept_id, concept_label in concept_labels.items():
            # Only link if the concept name is mentioned (case-insensitive, word boundary)
            if len(concept_label) > 3 and concept_label.lower() in content_lower:
                edges.append({
                    "source": section["id"],
                    "target": concept_id,
                    "label": "references",
                    "type": "references",
                })

    return nodes, edges


def _get_agent_nodes() -> tuple[list[dict], list[dict]]:
    """Create nodes for each agent with live status from Docker."""
    agent_list = [
        ("orchestrator", "Orchestrator", "Central router — routes tasks, manages approvals, stores memory"),
        ("frontend-agent", "Frontend Agent", "React/Next.js UI development"),
        ("backend-agent", "Backend Agent", "FastAPI/Python backend development"),
        ("deploy-agent", "Deploy Agent", "Docker/K8s deployment operations"),
        ("scaffold-agent", "Scaffold Agent", "New project bootstrapping"),
        ("support-agent", "Support Agent", "Client support ticket handling"),
        ("code-agent", "Code Agent", "General code operations"),
        ("file-agent", "File Agent", "File system operations"),
        ("uxui-agent", "UX/UI Agent", "Design audit and visual regression"),
        ("qa-agent", "QA Agent", "Testing and quality assurance"),
        ("sre-agent", "SRE Agent", "Site reliability — DB diagnostics, SLO tracking"),
        ("dba-agent", "DBA Agent", "Database health monitoring"),
        ("darius-agent", "Darius", "Autonomous coding agent — multi-step planning and execution"),
        ("security-watchdog", "Security Watchdog", "Container vulnerability scanning, anomaly detection"),
    ]

    nodes = []
    edges = []

    # Get live container status
    status_map = {}
    try:
        client = docker.from_env()
        for c in client.containers.list(all=True):
            status_map[c.name] = c.status
    except Exception:
        pass

    for agent_name, label, description in agent_list:
        container_name = f"docker-{agent_name}-1"
        status = status_map.get(container_name, "unknown")

        node_id = f"agent_{agent_name}".replace("-", "_")
        nodes.append({
            "id": node_id,
            "label": label,
            "file_type": "agent",
            "source_file": f"agents/{agent_name.replace('-', '_')}.py",
            "content": description,
            "_origin": "infrastructure",
            "community_name": "Agents",
            "status": status,
        })

    # Agent relationships
    # All agents connect to orchestrator
    for agent_name, _, _ in agent_list:
        if agent_name != "orchestrator":
            edges.append({
                "source": "agent_orchestrator",
                "target": f"agent_{agent_name}".replace("-", "_"),
                "label": "routes_to",
                "type": "routes",
            })

    # Darius has special relationship — it chains other agents
    for agent_name, _, _ in agent_list:
        if agent_name not in ("orchestrator", "darius-agent", "security-watchdog"):
            edges.append({
                "source": "agent_darius_agent",
                "target": f"agent_{agent_name}".replace("-", "_"),
                "label": "can_dispatch",
                "type": "dispatches",
            })

    return nodes, edges


def _get_service_nodes() -> tuple[list[dict], list[dict]]:
    """Create nodes for infrastructure services with live status."""
    services = [
        ("postgres", "PostgreSQL + pgvector", "Database — semantic memory, tickets, health snapshots"),
        ("redis", "Redis", "Cache and message queue"),
        ("ollama", "Ollama", "Local embeddings (nomic-embed-text, 768-dim)"),
        ("nginx", "nginx", "Reverse proxy — TLS, rate limiting, security headers"),
        ("hud", "HUD Backend", "Internal monitoring API"),
        ("hud-frontend", "HUD Frontend", "Dashboard UI at hud.melanin-tech.com"),
        ("production-server", "melanin-tech.com", "Production website"),
        ("certbot", "certbot", "TLS certificate auto-renewal"),
        ("fail2ban", "fail2ban", "Intrusion detection and IP banning"),
        ("cloudflare-ddns", "Cloudflare DDNS", "Dynamic DNS record updates"),
        ("vaultwarden", "Vaultwarden", "Self-hosted password/secrets manager"),
        ("odysseus", "Odysseus", "AI research workspace"),
        ("mcp-github", "MCP GitHub", "GitHub tool interface for agents"),
        ("mcp-postgres", "MCP Postgres", "Database tool interface for agents"),
        ("mcp-fetch", "MCP Fetch", "HTTP fetch tool for agents"),
    ]

    nodes = []
    edges = []

    # Get live container status
    status_map = {}
    try:
        client = docker.from_env()
        for c in client.containers.list(all=True):
            status_map[c.name] = c.status
    except Exception:
        pass

    for svc_name, label, description in services:
        container_name = f"docker-{svc_name}-1"
        status = status_map.get(container_name, "unknown")

        node_id = f"svc_{svc_name}".replace("-", "_")
        nodes.append({
            "id": node_id,
            "label": label,
            "file_type": "service",
            "source_file": f"docker-compose.yml#{svc_name}",
            "content": description,
            "_origin": "infrastructure",
            "community_name": "Infrastructure",
            "status": status,
        })

    # Service dependencies
    deps = [
        ("svc_hud", "svc_postgres", "depends_on"),
        ("svc_hud_frontend", "svc_hud", "depends_on"),
        ("svc_ollama", "svc_postgres", "stores_in"),
        ("svc_nginx", "svc_production_server", "proxies_to"),
        ("svc_nginx", "svc_hud_frontend", "proxies_to"),
        ("svc_certbot", "svc_nginx", "provides_certs"),
        ("svc_odysseus", "svc_ollama", "uses"),
        ("svc_mcp_github", "svc_postgres", "reads"),
        ("svc_mcp_postgres", "svc_postgres", "connects_to"),
    ]
    for src, tgt, label in deps:
        edges.append({"source": src, "target": tgt, "label": label, "type": "depends"})

    # Agents depend on infrastructure
    agent_infra_deps = [
        ("agent_orchestrator", "svc_postgres", "stores_memory"),
        ("agent_orchestrator", "svc_ollama", "generates_embeddings"),
        ("agent_darius_agent", "svc_mcp_github", "uses_tool"),
        ("agent_darius_agent", "svc_mcp_postgres", "uses_tool"),
        ("agent_darius_agent", "svc_mcp_fetch", "uses_tool"),
    ]
    for src, tgt, label in agent_infra_deps:
        edges.append({"source": src, "target": tgt, "label": label, "type": "uses"})

    return nodes, edges


def _build_unified_graph() -> dict:
    """Build the full knowledge graph merging code graph, docs, agents, and services."""
    import time
    global _GRAPH_CACHE, _GRAPH_CACHE_TIME

    # Cache for 60 seconds
    if _GRAPH_CACHE and (time.time() - _GRAPH_CACHE_TIME) < 60:
        return _GRAPH_CACHE

    all_nodes = []
    all_edges = []

    # 1. Load Graphify code graph (if available)
    if _GRAPHIFY_PATH.exists():
        try:
            import json as _j
            with open(_GRAPHIFY_PATH) as f:
                graphify_data = _j.load(f)
            # Add code nodes (limit to reduce size — skip trivial nodes)
            for node in graphify_data.get("nodes", []):
                node["file_type"] = node.get("file_type", "code")
                all_nodes.append(node)
            # Add code edges
            for edge in graphify_data.get("links", graphify_data.get("edges", [])):
                all_edges.append(edge)
        except Exception:
            pass

    # 2. Add document nodes from MelaninDocs
    doc_nodes, doc_edges = _get_doc_nodes()
    all_nodes.extend(doc_nodes)
    all_edges.extend(doc_edges)

    # 3. Add agent nodes with live status
    agent_nodes, agent_edges = _get_agent_nodes()
    all_nodes.extend(agent_nodes)
    all_edges.extend(agent_edges)

    # 4. Add infrastructure service nodes
    svc_nodes, svc_edges = _get_service_nodes()
    all_nodes.extend(svc_nodes)
    all_edges.extend(svc_edges)

    # 5. Cross-link: connect doc concepts to agents/services where names match
    concept_nodes = [n for n in all_nodes if n.get("file_type") == "concept"]
    agent_svc_nodes = [n for n in all_nodes if n.get("file_type") in ("agent", "service")]

    for concept in concept_nodes:
        concept_label_lower = concept["label"].lower()
        for target in agent_svc_nodes:
            target_label_lower = target["label"].lower()
            if (concept_label_lower in target_label_lower or
                target_label_lower in concept_label_lower):
                all_edges.append({
                    "source": concept["id"],
                    "target": target["id"],
                    "label": "describes",
                    "type": "describes",
                })

    result = {
        "nodes": all_nodes,
        "edges": all_edges,
        "stats": {
            "total_nodes": len(all_nodes),
            "total_edges": len(all_edges),
            "code_nodes": len([n for n in all_nodes if n.get("file_type") == "code"]),
            "doc_nodes": len([n for n in all_nodes if n.get("file_type") == "doc"]),
            "concept_nodes": len([n for n in all_nodes if n.get("file_type") == "concept"]),
            "agent_nodes": len([n for n in all_nodes if n.get("file_type") == "agent"]),
            "service_nodes": len([n for n in all_nodes if n.get("file_type") == "service"]),
        },
    }

    _GRAPH_CACHE = result
    _GRAPH_CACHE_TIME = time.time()
    return result


@app.get("/api/graph", dependencies=[Depends(verify_token)])
def graph_data(include_code: bool = True):
    """Return the unified knowledge graph (code + docs + agents + services)."""
    graph = _build_unified_graph()
    if not include_code:
        # Return only non-code nodes for a lighter view
        nodes = [n for n in graph["nodes"] if n.get("file_type") != "code"]
        # Filter edges to only include those with valid node ids
        node_ids = {n["id"] for n in nodes}
        edges = [e for e in graph["edges"] if e.get("source") in node_ids and e.get("target") in node_ids]
        return {"nodes": nodes, "edges": edges, "stats": graph["stats"]}
    return graph


@app.get("/api/graph/search", dependencies=[Depends(verify_token)])
def graph_search(q: str = "", limit: int = 20):
    """Semantic search across the knowledge graph. Falls back to text match if embedding fails."""
    if not q:
        return {"query": "", "results": [], "highlighted_nodes": []}

    graph = _build_unified_graph()

    # Try pgvector semantic search first
    highlighted_ids: list[str] = []
    try:
        embedding = _graph_embed(q)
        if embedding:
            conn = _db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT node_id, content, 1 - (embedding <=> %s::vector) AS similarity
                FROM graph_nodes
                WHERE 1 - (embedding <=> %s::vector) > 0.4
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (str(embedding), str(embedding), str(embedding), limit))
            results = cur.fetchall()
            conn.close()
            highlighted_ids = [r["node_id"] for r in results]
            return {
                "query": q,
                "results": results,
                "highlighted_nodes": highlighted_ids,
            }
    except Exception:
        pass

    # Fallback: text-based search across node labels and content
    q_lower = q.lower()
    matches = []
    for node in graph["nodes"]:
        label = (node.get("label") or "").lower()
        content = (node.get("content") or "").lower()
        source = (node.get("source_file") or "").lower()

        score = 0
        if q_lower in label:
            score = 0.9
        elif q_lower in content:
            score = 0.7
        elif q_lower in source:
            score = 0.5

        if score > 0:
            matches.append({
                "node_id": node["id"],
                "content": node.get("content", node.get("label", "")),
                "similarity": score,
            })

    matches.sort(key=lambda x: x["similarity"], reverse=True)
    matches = matches[:limit]
    highlighted_ids = [m["node_id"] for m in matches]

    return {
        "query": q,
        "results": matches,
        "highlighted_nodes": highlighted_ids,
    }


def _graph_embed(text: str) -> list[float] | None:
    """Generate embedding via Ollama for graph search."""
    try:
        ollama_url = os.environ.get("OLLAMA_URL", "http://ollama:11434")
        resp = _httpx.post(
            f"{ollama_url}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text[:500]},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
    except Exception:
        return None


def _init_graph_table():
    """Create the graph_nodes table for semantic search if it doesn't exist."""
    try:
        conn = _db()
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS graph_nodes (
                id SERIAL PRIMARY KEY,
                node_id TEXT UNIQUE NOT NULL,
                label TEXT,
                content TEXT,
                file_type TEXT,
                community_name TEXT,
                embedding vector(768),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_graph_nodes_node_id ON graph_nodes(node_id)")
        conn.commit()
        conn.close()
    except Exception:
        pass


@app.post("/api/graph/index", dependencies=[Depends(verify_token)])
def graph_index():
    """Re-index graph nodes into pgvector for semantic search. Call after graph data changes."""
    _init_graph_table()
    graph = _build_unified_graph()

    # Index non-code nodes (docs, concepts, agents, services) — code nodes are too numerous
    indexable = [n for n in graph["nodes"] if n.get("file_type") in ("doc", "concept", "agent", "service")]

    indexed = 0
    errors = 0
    conn = _db()
    cur = conn.cursor()

    for node in indexable:
        text = f"{node.get('label', '')} — {node.get('content', '')}".strip()
        if not text or text == "—":
            continue

        embedding = _graph_embed(text)
        if not embedding:
            errors += 1
            continue

        try:
            cur.execute("""
                INSERT INTO graph_nodes (node_id, label, content, file_type, community_name, embedding, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (node_id) DO UPDATE SET
                    label = EXCLUDED.label,
                    content = EXCLUDED.content,
                    file_type = EXCLUDED.file_type,
                    community_name = EXCLUDED.community_name,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
            """, (node["id"], node.get("label"), node.get("content"), node.get("file_type"), node.get("community_name"), embedding))
            indexed += 1
        except Exception:
            errors += 1
            conn.rollback()
            cur = conn.cursor()

    conn.commit()
    conn.close()

    return {"indexed": indexed, "errors": errors, "total_candidates": len(indexable)}


# Initialize graph table on startup
_init_graph_table()


# Health monitor is started via lifespan context manager (see top of file)


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

    # Pre-flight: confirm Darius is alive (fast, 5s timeout)
    try:
        _hx.get("http://darius-agent:8000/health", timeout=5)
    except Exception:
        return {"reply": "Darius is not reachable. The agent container may be down or restarting."}

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
            json={"task": f"[Contract Management] {context}\n\nUser: {prompt}", "project": "melanin-contracts", "session_id": "hud-contracts", "model_source": "local"},
            timeout=300,
        )
        data = r.json()
        return {"reply": data.get("args", {}).get("proposal", "No response from Darius.")}
    except _hx.TimeoutException:
        return {"reply": "Darius is still processing your request (took longer than 5 minutes). Try a simpler question or check back shortly."}
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

    # Pre-flight: confirm Darius is alive (fast, 5s timeout)
    try:
        _hx.get("http://darius-agent:8000/health", timeout=5)
    except Exception:
        return {"reply": "Darius is not reachable. The agent container may be down or restarting."}

    gov_dir = "/app/governance" if os.path.isdir("/app/governance") else os.path.join(os.path.dirname(__file__), "../../governance")
    policies = [f.replace(".md", "") for f in os.listdir(gov_dir) if f.endswith(".md")]
    context = f"Governance policies: {', '.join(policies)}. Ask about any specific policy for details."
    try:
        r = _hx.post("http://darius-agent:8000/task",
            json={"task": f"[Governance & Compliance] {context}\n\nUser: {prompt}", "project": "melanin-governance", "session_id": "hud-governance", "model_source": "local"},
            timeout=300)
        data = r.json()
        return {"reply": data.get("args", {}).get("proposal", "No response from Darius.")}
    except _hx.TimeoutException:
        return {"reply": "Darius is still processing your request (took longer than 5 minutes). Try a simpler question or check back shortly."}
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
        "docker-sre-agent-1",
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

    # Pre-flight: confirm Darius is alive (fast, 5s timeout)
    try:
        _hx.get("http://darius-agent:8000/health", timeout=5)
    except Exception:
        return {"reply": "Darius is not reachable. The agent container may be down or restarting."}

    try:
        r = _hx.post("http://darius-agent:8000/task",
            json={"task": f"[SRE — {scope}] You are monitoring Melanin Technologies infrastructure. User: {prompt}", "project": "melanin-sre", "session_id": "hud-sre", "model_source": "local"},
            timeout=300)
        data = r.json()
        return {"reply": data.get("args", {}).get("proposal", "No response from Darius.")}
    except _hx.TimeoutException:
        return {"reply": "Darius is still processing your request (took longer than 5 minutes). Try a simpler question or check back shortly."}
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


# ── LLM Observability ─────────────────────────────────────────────────────────

@app.get("/api/llm/observability", dependencies=[Depends(verify_token)])
def llm_observability():
    """Full LLM observability dashboard data."""
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Recent traces (last 50)
    cur.execute("SELECT trace_id, agent, model, task_preview, input_tokens, output_tokens, latency_ms, status, cached, cost_usd, created_at FROM llm_traces ORDER BY created_at DESC LIMIT 50")
    traces = cur.fetchall()

    # Failure summary
    cur.execute("SELECT failure_type, COUNT(*) as count FROM llm_failures WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY failure_type ORDER BY count DESC")
    failures = cur.fetchall()

    # Unresolved failures
    cur.execute("SELECT id, agent, model, failure_type, error_message, created_at FROM llm_failures WHERE resolved = FALSE ORDER BY created_at DESC LIMIT 20")
    unresolved = cur.fetchall()

    # SLO status
    cur.execute("SELECT name, description, metric, target FROM llm_slos")
    slos = cur.fetchall()

    # Current SLI values (computed from traces)
    cur.execute("SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE status = 'success') as success, PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) as p95_latency, SUM(input_tokens) as total_input_tokens, COUNT(*) FILTER (WHERE cached = TRUE) as cache_hits FROM llm_traces WHERE created_at > NOW() - INTERVAL '24 hours'")
    sli_row = cur.fetchone()

    # Error budget consumption
    total = sli_row["total"] or 1
    success = sli_row["success"] or 0
    availability = (success / total) * 100 if total > 0 else 100
    error_rate = 100 - availability
    cache_hit_rate = ((sli_row["cache_hits"] or 0) / total) * 100 if total > 0 else 0

    sli_values = {
        "availability": round(availability, 2),
        "latency_p95_ms": int(sli_row["p95_latency"] or 0),
        "error_rate": round(error_rate, 2),
        "tokens_today": sli_row["total_input_tokens"] or 0,
        "cache_hit_rate": round(cache_hit_rate, 1),
        "total_calls_24h": total,
    }

    # Latency trend (hourly avg, last 24h)
    cur.execute("SELECT date_trunc('hour', created_at) as hour, AVG(latency_ms) as avg_latency, COUNT(*) as calls FROM llm_traces WHERE created_at > NOW() - INTERVAL '24 hours' GROUP BY hour ORDER BY hour")
    latency_trend = cur.fetchall()

    conn.close()

    # Serialize
    for t in traces:
        t["created_at"] = t["created_at"].isoformat() if t.get("created_at") else None
        t["cost_usd"] = float(t["cost_usd"]) if t.get("cost_usd") else 0
    for f in unresolved:
        f["created_at"] = f["created_at"].isoformat() if f.get("created_at") else None
    for l in latency_trend:
        l["hour"] = l["hour"].isoformat() if l.get("hour") else None
        l["avg_latency"] = int(l["avg_latency"]) if l.get("avg_latency") else 0

    return {
        "traces": traces,
        "failures": failures,
        "unresolved_failures": unresolved,
        "slos": slos,
        "sli_values": sli_values,
        "latency_trend": latency_trend,
        "per_agent": _get_per_agent_sli(conn_str=_DSN),
        "error_budgets": _get_error_budgets(conn_str=_DSN),
        "local_vs_cloud": _get_local_vs_cloud(conn_str=_DSN),
    }


def _get_per_agent_sli(conn_str: str) -> list:
    """Per-agent SLI breakdown."""
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT agent,
                COUNT(*) as total_calls,
                COUNT(*) FILTER (WHERE status='success') as successes,
                COUNT(*) FILTER (WHERE status != 'success') as failures,
                COALESCE(AVG(latency_ms) FILTER (WHERE status='success'), 0) as avg_latency_ms,
                COALESCE(SUM(cost_usd), 0) as total_cost,
                COUNT(*) FILTER (WHERE cached=TRUE) as cache_hits
            FROM llm_traces
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY agent
            ORDER BY total_calls DESC
        """)
        results = cur.fetchall()
        conn.close()
        for r in results:
            r["avg_latency_ms"] = int(r["avg_latency_ms"])
            r["total_cost"] = float(r["total_cost"])
            r["availability"] = round((r["successes"] / max(r["total_calls"], 1)) * 100, 1)
        return results
    except Exception:
        return []


def _get_error_budgets(conn_str: str) -> list:
    """Latest error budget status per SLO."""
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT DISTINCT ON (slo_name) slo_name, budget_total, budget_consumed, budget_remaining, status, created_at
            FROM llm_error_budgets
            ORDER BY slo_name, created_at DESC
        """)
        results = cur.fetchall()
        conn.close()
        for r in results:
            r["budget_total"] = float(r["budget_total"]) if r["budget_total"] else 0
            r["budget_consumed"] = float(r["budget_consumed"]) if r["budget_consumed"] else 0
            r["budget_remaining"] = float(r["budget_remaining"]) if r["budget_remaining"] else 0
            r["created_at"] = r["created_at"].isoformat() if r.get("created_at") else None
        return results
    except Exception:
        return []


def _get_local_vs_cloud(conn_str: str) -> dict:
    """Compare local (Ollama) vs cloud (Claude) model performance from Darius traces."""
    try:
        conn = psycopg2.connect(conn_str)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Query darius_traces for HUD sessions (which use local models)
        # Group by model to compare local vs cloud performance
        cur.execute("""
            SELECT
                model,
                COUNT(*) as total_calls,
                COUNT(*) FILTER (WHERE status = 'success') as successes,
                COUNT(*) FILTER (WHERE status != 'success') as failures,
                COALESCE(AVG(latency_ms) FILTER (WHERE status = 'success'), 0) as avg_latency_ms,
                COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms), 0) as p95_latency_ms,
                COALESCE(AVG(tokens_out) FILTER (WHERE status = 'success'), 0) as avg_tokens_out
            FROM darius_traces
            WHERE created_at > NOW() - INTERVAL '7 days'
              AND phase = 'complete'
              AND model IS NOT NULL
            GROUP BY model
            ORDER BY total_calls DESC
        """)
        by_model = cur.fetchall()

        # Fallback events (local → cloud)
        cur.execute("""
            SELECT COUNT(*) as fallback_count
            FROM darius_traces
            WHERE created_at > NOW() - INTERVAL '7 days'
              AND phase = 'fallback'
        """)
        fallback_row = cur.fetchone()
        fallback_count = fallback_row["fallback_count"] if fallback_row else 0

        conn.close()

        # Categorize into local vs cloud
        local_models = []
        cloud_models = []
        for m in by_model:
            m["avg_latency_ms"] = int(m["avg_latency_ms"])
            m["p95_latency_ms"] = int(m["p95_latency_ms"])
            m["avg_tokens_out"] = int(m["avg_tokens_out"])
            m["availability"] = round((m["successes"] / max(m["total_calls"], 1)) * 100, 1)

            if m["model"] and ("mistral" in m["model"].lower() or "qwen" in m["model"].lower()):
                local_models.append(m)
            else:
                cloud_models.append(m)

        return {
            "local": local_models,
            "cloud": cloud_models,
            "fallback_count_7d": fallback_count,
        }
    except Exception:
        return {"local": [], "cloud": [], "fallback_count_7d": 0}


@app.post("/api/llm/darius", dependencies=[Depends(verify_token)])
def llm_darius(body: dict):
    """Proxy to Darius for LLM observability questions — SLO breaches, error budgets, model performance."""
    import httpx as _hx
    prompt = body.get("message", "")

    # Pre-flight: confirm Darius is alive (fast, 5s timeout)
    try:
        _hx.get("http://darius-agent:8000/health", timeout=5)
    except Exception:
        return {"reply": "Darius is not reachable. The agent container may be down or restarting."}

    # Gather LLM context for Darius
    conn = _db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT name, target, metric FROM llm_slos")
    slos = cur.fetchall()
    cur.execute("SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE status='success') as success, COUNT(*) FILTER (WHERE cached=TRUE) as cached FROM llm_traces WHERE created_at > NOW() - INTERVAL '24 hours'")
    stats = cur.fetchone()
    cur.execute("SELECT failure_type, COUNT(*) as count FROM llm_failures WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY failure_type ORDER BY count DESC LIMIT 5")
    failures = cur.fetchall()
    cur.execute("SELECT agent, COUNT(*) as calls, COUNT(*) FILTER (WHERE status='success') as ok FROM llm_traces WHERE created_at > NOW() - INTERVAL '24 hours' GROUP BY agent ORDER BY calls DESC")
    agents = cur.fetchall()
    budgets = _get_error_budgets(conn_str=_DSN)
    conn.close()

    total = stats["total"] or 0
    success = stats["success"] or 0
    availability = round((success / max(total, 1)) * 100, 1)
    cache_rate = round(((stats["cached"] or 0) / max(total, 1)) * 100, 1)
    slo_summary = "; ".join(f"{s['name']}: target {s['target']} ({s['metric']})" for s in slos)
    failure_summary = ", ".join(f"{f['failure_type']}({f['count']})" for f in failures) or "none"
    agent_summary = "; ".join(f"{a['agent']}: {a['calls']} calls ({a['ok']} ok)" for a in agents)
    budget_summary = "; ".join(f"{b['slo_name']}: {b['status']} ({b['budget_consumed']:.1f}/{b['budget_total']:.1f})" for b in budgets) or "no data"

    context = (
        f"LLM Observability (24h): {total} calls, {availability}% availability, {cache_rate}% cache hit. "
        f"SLOs: {slo_summary}. Failures (7d): {failure_summary}. "
        f"Per-agent: {agent_summary}. Error budgets: {budget_summary}."
    )

    try:
        r = _hx.post("http://darius-agent:8000/task",
            json={"task": f"[LLM Observability] {context}\n\nUser: {prompt}", "project": "melanin-llm", "session_id": "hud-llm", "model_source": "local"},
            timeout=300)
        data = r.json()
        return {"reply": data.get("args", {}).get("proposal", "No response from Darius.")}
    except _hx.TimeoutException:
        return {"reply": "Darius is still processing your request (took longer than 5 minutes). Try a simpler question or check back shortly."}
    except Exception as e:
        return {"reply": f"Darius unavailable: {e}"}


# ── Endpoint Health Monitoring ────────────────────────────────────────────────

_endpoint_alerts: set = set()

def _check_endpoint_health():
    """Check key service endpoints every 5 min via the FULL CHAIN (through nginx). Alert Slack if unreachable."""
    global _endpoint_alerts
    # Probe through nginx (same path as real users) — catches stale IP issues
    endpoints = {
        "melanin-tech.com": "http://host.docker.internal:443",
        "HUD": "http://host.docker.internal:4000/api/health",
        "OrthoFlow": "http://host.docker.internal:5173",
        "OrthoFlow API": "http://host.docker.internal:8000/health",
        "nginx": "http://host.docker.internal:80",
    }

    for name, url in endpoints.items():
        try:
            r = _httpx.get(url, timeout=5, follow_redirects=True)
            if r.status_code < 500:
                # Recovered
                if name in _endpoint_alerts:
                    _endpoint_alerts.discard(name)
                    _send_alert(f"✅ *Recovered:* {name} is back online")
            elif r.status_code == 502:
                # 502 = nginx can't reach upstream — auto-reload nginx
                try:
                    import subprocess
                    subprocess.run(["docker", "exec", "docker-nginx-1", "nginx", "-s", "reload"], capture_output=True, timeout=5)
                except Exception:
                    pass
                if name not in _endpoint_alerts:
                    _endpoint_alerts.add(name)
                    _send_alert(f"🟡 *{name}:* 502 Bad Gateway — nginx reloaded automatically")
            else:
                raise Exception(f"HTTP {r.status_code}")
        except Exception as e:
            if name not in _endpoint_alerts:
                _endpoint_alerts.add(name)
                _send_alert(f"🔴 *Service Down:* {name} — {e}")


# ── Daily Email Triage ────────────────────────────────────────────────────────

def _run_daily_email_triage():
    """Triage CEO inbox and post summary to Slack every morning."""
    try:
        import json, sys
        sys.path.insert(0, '/app')

        creds_path = "/app/integrations/credentials/ceo/gmail.json"
        if not os.path.exists(creds_path):
            return

        from integrations.gmail import GmailConnector
        creds = json.load(open(creds_path))
        gmail = GmailConnector('ceo', creds)

        if not gmail.health_check():
            _send_alert("⚠️ Daily email triage failed — Gmail auth expired. Re-run auth flow.")
            return

        inbox = gmail.read_inbox(max_results=15, query="is:unread")
        if not inbox:
            return  # No unread, no report needed

        # Classify
        categories = {"🟢 Prospect": [], "👤 Client": [], "🔴 Security": [], "💰 Finance": [], "🔧 Vendor": [], "📬 Other": []}
        for e in inbox:
            sender = e.get("from", "").lower()
            subject = e.get("subject", "").lower()
            display = f"{e.get('from', '')[:30]} — {e.get('subject', '')[:45]}"

            if any(k in subject for k in ["opportunity", "project", "proposal", "interested", "quote", "inquiry"]):
                categories["🟢 Prospect"].append(display)
            elif any(k in sender for k in ["orthoflow", "marcallen", "heldtogether", "htc"]):
                categories["👤 Client"].append(display)
            elif any(k in subject for k in ["security", "alert", "breach", "unauthorized"]):
                categories["🔴 Security"].append(display)
            elif any(k in subject for k in ["invoice", "payment", "bill", "declined", "overdue"]):
                categories["💰 Finance"].append(display)
            elif any(k in sender for k in ["google", "slack", "github", "cloudflare", "docker"]):
                categories["🔧 Vendor"].append(display)
            else:
                categories["📬 Other"].append(display)

        # Build Slack message
        lines = [f"📬 *Daily Email Triage* — {len(inbox)} unread", ""]
        for cat, emails in categories.items():
            if emails:
                lines.append(f"*{cat}* ({len(emails)})")
                for e in emails[:3]:
                    lines.append(f"  • {e}")
                if len(emails) > 3:
                    lines.append(f"  _...and {len(emails)-3} more_")
                lines.append("")

        # Flag urgent items
        urgent = categories["🟢 Prospect"] + categories["🔴 Security"] + categories["💰 Finance"]
        if urgent:
            lines.append(f"⚡ *{len(urgent)} items need attention*")

        _send_alert("\n".join(lines))

    except Exception:
        pass
