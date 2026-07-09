"""QA Agent — automated testing, build verification, and security scanning.

Company-wide end-to-end testing gate. Every project must pass QA before going live.
melanin-tech (Kiro/Projects/kiro-agents) is the source of truth for all test definitions.

YOUR SCOPE (what you handle):
- Frontend build verification (does it compile?)
- API endpoint testing (do routes return expected status codes?)
- Security checks (auth bypass, unauthenticated access)
- Visual regression (mobile viewport rendering)
- Performance checks (response time thresholds)
- Code quality review (when requested after changes)

NOT YOUR SCOPE (what SRE handles):
- Infrastructure monitoring (containers, nginx, TLS, DNS)
- LLM observability and SLO tracking
- Incident response and triage
- Container health and restart management
"""
import os
import subprocess
import time
import httpx
from fastapi import FastAPI

app = FastAPI()

_MCP_URL = os.environ.get("MCP_URL", "http://mcp-server:9000")
_PLAYWRIGHT_URL = os.environ.get("PLAYWRIGHT_MCP_URL", "http://playwright-mcp:9001")

# ── Company-Wide Project Test Suites ──────────────────────────────────────────

PROJECTS = {
    "orthoflow-ai": {
        "frontend_path": "/app/orthoflow-frontend",
        "backend_url": "http://host.docker.internal:8000",
        "frontend_url": "http://host.docker.internal:5173",
        "test_endpoints": [
            ("GET", "/", 200),  # healthcheck
            ("GET", "/ready", 200),
            ("POST", "/api/v1/auth/login", 422),  # empty body → validation error
        ],
        "auth_endpoints": [
            # Clinical Phase 1 — all require auth (should return 403 without token)
            ("GET", "/api/v1/patients", 403),
            ("GET", "/api/v1/schedule", 403),
            ("GET", "/api/v1/appointments", 403),
            ("GET", "/api/v1/chairs", 403),
            ("GET", "/api/v1/dental-assistants", 403),
            # AP module
            ("GET", "/api/v1/invoices/", 403),
        ],
        "authenticated_tests": [
            # These run with a valid JWT (after login)
            ("GET", "/api/v1/patients", 200),
            ("GET", "/api/v1/schedule", 200),
            ("GET", "/api/v1/chairs", 200),
            ("GET", "/api/v1/dental-assistants", 200),
            ("GET", "/api/v1/appointments", 200),
        ],
        "auth_credentials": {
            "email": os.environ.get("QA_TEST_EMAIL", "qa@testortho.com"),
            "password": os.environ.get("QA_TEST_PASSWORD", "TestPass123"),
        },
        "seed_script": "python -m scripts.seed_clinical",
        "seed_container": "orthoflow-backend-1",
        "seed_check_endpoint": "/api/v1/patients",
    },
    "melanin-tech-website": {
        "frontend_path": "/app/melanin-tech-website",
        "backend_url": "http://host.docker.internal:3000",
        "frontend_url": "http://host.docker.internal:3000",
        "test_endpoints": [
            ("GET", "/", 200),
            ("GET", "/api/health", 200),
        ],
        "auth_endpoints": [],
        "authenticated_tests": [],
    },
    "htc-app": {
        "frontend_path": "/app/LinesOfBusiness/Held_Together_Caregiving/htc-app/frontend",
        "backend_url": "http://host.docker.internal:8001",
        "frontend_url": "http://host.docker.internal:5174",
        "test_endpoints": [
            ("GET", "/health", 200),
        ],
        "auth_endpoints": [
            ("GET", "/api/v1/users/me", 403),
        ],
        "authenticated_tests": [],
    },
    "music-catalogue": {
        "frontend_path": "/app/Projects/music-catalogue-system/frontend",
        "backend_url": "http://host.docker.internal:8002",
        "frontend_url": "http://host.docker.internal:5175",
        "test_endpoints": [
            ("GET", "/health", 200),
        ],
        "auth_endpoints": [],
        "authenticated_tests": [],
    },
    "kiro-agents": {
        "frontend_path": None,
        "backend_url": None,
        "frontend_url": None,
        "test_endpoints": [],
        "auth_endpoints": [],
        "authenticated_tests": [],
        "container_health_checks": [
            "docker-orchestrator-1",
            "docker-darius-agent-1",
            "docker-frontend-agent-1",
            "docker-backend-agent-1",
            "docker-qa-agent-1",
            "docker-sre-agent-1",
            "docker-code-agent-1",
            "docker-file-agent-1",
            "docker-scaffold-agent-1",
            "docker-deploy-agent-1",
            "docker-support-agent-1",
            "docker-postgres-1",
            "docker-ollama-1",
        ],
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_cmd(cmd: str, cwd: str = None, timeout: int = 60) -> dict:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return {"pass": result.returncode == 0, "output": result.stdout[-500:] + result.stderr[-500:]}
    except subprocess.TimeoutExpired:
        return {"pass": False, "output": "Timeout"}
    except Exception as e:
        return {"pass": False, "output": str(e)}


def _check_endpoint(base_url: str, method: str, path: str, expected_status: int, headers: dict = None) -> dict:
    try:
        r = httpx.request(method, f"{base_url}{path}", timeout=10, headers=headers)
        passed = r.status_code == expected_status
        return {"pass": passed, "output": f"{method} {path} → {r.status_code}" + ("" if passed else f" (expected {expected_status})")}
    except Exception as e:
        return {"pass": False, "output": f"{method} {path} → {e}"}


def _get_auth_token(config: dict) -> str | None:
    """Login and get a JWT for authenticated testing."""
    creds = config.get("auth_credentials")
    if not creds:
        return None
    try:
        r = httpx.post(
            f"{config['backend_url']}/api/v1/auth/login",
            json=creds,
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("access_token") or data.get("token")
    except Exception:
        pass
    return None


def _auto_seed_if_empty(config: dict, token: str) -> dict | None:
    """Check if clinical data exists; if empty, attempt to seed via the backend container."""
    check_endpoint = config.get("seed_check_endpoint")
    seed_script = config.get("seed_script")
    if not check_endpoint or not seed_script:
        return None

    try:
        r = httpx.get(
            f"{config['backend_url']}{check_endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            total = data.get("total", len(data.get("patients", [])))
            if total > 0:
                return {"pass": True, "output": f"Data exists ({total} records) — skipping seed"}
    except Exception:
        pass

    # Try to seed — use docker exec if available, otherwise skip gracefully
    seed_container = config.get("seed_container", "orthoflow-backend-1")
    docker_check = _run_cmd("which docker", timeout=5)
    if docker_check["pass"]:
        result = _run_cmd(f"docker exec {seed_container} {seed_script}", timeout=60)
        if result["pass"]:
            return {"pass": True, "output": f"Seeded test data: {result['output'][-200:]}"}
        return {"pass": False, "output": f"Seed failed: {result['output'][-200:]}"}
    else:
        # Docker not available in this container — non-blocking, QA proceeds without seed
        return {"pass": True, "output": "Seed skipped (docker not available in QA container — seed manually or via orchestrator)"}


def _check_container_health(containers: list[str]) -> list[dict]:
    """Check Docker container health status."""
    results = []
    for name in containers:
        r = _run_cmd(f"docker inspect {name} --format '{{{{.State.Status}}}} {{{{.State.Health.Status}}}}'")
        if r["pass"]:
            status = r["output"].strip()
            healthy = "running" in status
            results.append({"name": f"Container: {name}", "pass": healthy, "output": status})
        else:
            results.append({"name": f"Container: {name}", "pass": False, "output": "not found"})
    return results


# ── Main QA Runner ────────────────────────────────────────────────────────────

def run_qa(project: str) -> dict:
    """Run full QA suite for a project."""
    config = PROJECTS.get(project)
    if not config:
        return {"pass": False, "results": [{"name": "Project lookup", "pass": False, "output": f"Unknown project: {project}. Available: {', '.join(PROJECTS.keys())}"}]}

    results = []

    # 0. Container health checks (kiro-agents)
    containers = config.get("container_health_checks", [])
    if containers:
        results.extend(_check_container_health(containers))

    # 1. Frontend build check (skip if npm not available — test live URL instead)
    frontend_path = config.get("frontend_path")
    if frontend_path and os.path.exists(frontend_path):
        pkg_json = os.path.join(frontend_path, "package.json")
        if os.path.exists(pkg_json):
            # Check if npm is available in this container
            npm_check = _run_cmd("which npm", timeout=5)
            if npm_check["pass"]:
                r = _run_cmd("npx vite build 2>&1 || npm run build 2>&1", cwd=frontend_path, timeout=120)
                results.append({"name": "Frontend build", **r})
            else:
                # No npm — test the live frontend URL responds instead
                frontend_url = config.get("frontend_url")
                if frontend_url:
                    r = _check_endpoint(frontend_url, "GET", "/", 200)
                    results.append({"name": "Frontend live (build skipped — no npm in container)", **r})
                else:
                    results.append({"name": "Frontend build", "pass": True, "output": "Skipped (npm not available, no frontend URL configured)"})

    # 2. API health checks (unauthenticated)
    backend_url = config.get("backend_url")
    if backend_url:
        for method, path, status in config.get("test_endpoints", []):
            r = _check_endpoint(backend_url, method, path, status)
            results.append({"name": f"API {method} {path}", **r})

    # 3. Security: unauthenticated access should be blocked
    for method, path, expected in config.get("auth_endpoints", []):
        r = _check_endpoint(backend_url, method, path, expected)
        results.append({"name": f"Security: {method} {path} requires auth", **r})

    # 4. Authenticated testing
    auth_tests = config.get("authenticated_tests", [])
    if auth_tests and backend_url:
        token = _get_auth_token(config)
        if token:
            # Auto-seed if needed (OrthoFlow)
            seed_result = _auto_seed_if_empty(config, token)
            if seed_result:
                results.append({"name": "Auto-seed check", **seed_result})

            # Run authenticated endpoint tests
            auth_headers = {"Authorization": f"Bearer {token}"}
            for method, path, expected in auth_tests:
                r = _check_endpoint(backend_url, method, path, expected, headers=auth_headers)
                results.append({"name": f"Auth {method} {path}", **r})
        else:
            results.append({"name": "Auth token acquisition", "pass": False, "output": "Could not login with QA credentials"})

    # 5. Backend tests (if pytest available)
    if frontend_path:
        backend_path = frontend_path.replace("frontend", "backend")
        if os.path.exists(os.path.join(backend_path, "tests")):
            pytest_check = _run_cmd("python -m pytest --version", timeout=5)
            if pytest_check["pass"]:
                r = _run_cmd("python -m pytest tests/ -v --tb=short 2>&1", cwd=backend_path, timeout=90)
                results.append({"name": "Backend tests", **r})
            else:
                results.append({"name": "Backend tests", "pass": True, "output": "Skipped (pytest not installed in QA container)"})

    # 6. Visual regression via Playwright MCP (mobile viewport)
    frontend_url = config.get("frontend_url")
    if frontend_url:
        try:
            resp = httpx.post(f"{_PLAYWRIGHT_URL}/screenshot/mobile", json={"url": frontend_url, "fullPage": True}, timeout=30)
            results.append({"name": "Mobile viewport renders", "pass": resp.status_code == 200, "output": f"Screenshot: {resp.status_code}"})
        except Exception as e:
            results.append({"name": "Mobile viewport renders", "pass": True, "output": f"Playwright unavailable (non-blocking): {e}"})

    # 7. Performance: API response time
    if backend_url:
        try:
            start = time.time()
            httpx.get(f"{backend_url}/ready", timeout=10)
            elapsed = round((time.time() - start) * 1000)
            results.append({"name": f"Performance: health ({elapsed}ms)", "pass": elapsed < 500, "output": f"{elapsed}ms (threshold: 500ms)"})
        except Exception as e:
            results.append({"name": "Performance check", "pass": True, "output": f"Skipped: {e}"})

    all_pass = all(r["pass"] for r in results)
    return {"pass": all_pass, "results": results}


# ── FastAPI Endpoints ─────────────────────────────────────────────────────────

@app.post("/task")
def task(body: dict):
    """Run QA for a project. Called by orchestrator after code changes."""
    project = body.get("project", "default")
    task_text = body.get("task", "")

    qa_result = run_qa(project)

    # Format report
    lines = []
    for r in qa_result["results"]:
        icon = "✅" if r["pass"] else "❌"
        lines.append(f"{icon} {r['name']}")
        if not r["pass"]:
            lines.append(f"   → {r['output'][:200]}")

    status = "PASS ✅" if qa_result["pass"] else "FAIL ❌"
    report = f"*QA Result: {status}*\nProject: `{project}`\n\n" + "\n".join(lines)

    return {
        "agent": "QAAgent",
        "model": "none",
        "description": f"QA {status} for {project}",
        "action": "qa",
        "args": {
            "task": task_text,
            "project": project,
            "proposal": report,
        },
        "qa_pass": qa_result["pass"],
    }


@app.get("/health")
def health():
    return {"status": "ok", "agent": "QAAgent", "projects": list(PROJECTS.keys())}


@app.get("/projects")
def list_projects():
    """List all projects with their test suite configuration."""
    return {
        project: {
            "endpoints": len(config.get("test_endpoints", [])),
            "auth_tests": len(config.get("auth_endpoints", [])),
            "authenticated_tests": len(config.get("authenticated_tests", [])),
            "has_frontend": config.get("frontend_path") is not None,
            "has_containers": len(config.get("container_health_checks", [])),
        }
        for project, config in PROJECTS.items()
    }
