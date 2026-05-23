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
    # Fail2ban (check if running)
    try:
        client = docker.from_env()
        f2b = client.containers.get("docker-fail2ban-1")
        results["fail2ban"] = f2b.status
    except Exception:
        results["fail2ban"] = "not found"
    results["npm_audit"] = "last run: see CI"
    return results


# ── Clients ───────────────────────────────────────────────────────────────────
@app.get("/api/clients", dependencies=[Depends(verify_token)])
def clients():
    """OrthoFlow client accounts — respects separation (shows metadata only, not client data)."""
    try:
        import psycopg2 as pg2
        conn = pg2.connect(os.environ.get("ORTHOFLOW_DSN", "postgresql://orthoflow:changeme@host.docker.internal:5433/orthoflow"))
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, name, created_at FROM practices ORDER BY created_at DESC")
        practices = cur.fetchall()
        cur.execute("SELECT practice_id, COUNT(*) as invoice_count FROM invoices GROUP BY practice_id")
        invoice_counts = {str(r["practice_id"]): r["invoice_count"] for r in cur.fetchall()}
        conn.close()
        for p in practices:
            p["invoice_count"] = invoice_counts.get(str(p["id"]), 0)
        return {"clients": practices}
    except Exception as e:
        return {"clients": [], "error": str(e)}
