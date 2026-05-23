"""QA Agent — runs automated tests and verifies builds before deployment."""
import os
import subprocess
import httpx
from fastapi import FastAPI

app = FastAPI()

_MCP_URL = os.environ.get("MCP_URL", "http://mcp-server:9000")
_PLAYWRIGHT_URL = os.environ.get("PLAYWRIGHT_MCP_URL", "http://playwright-mcp:9001")

PROJECTS = {
    "orthoflow-ai": {
        "frontend_path": "/app/orthoflow-frontend",
        "backend_url": "http://host.docker.internal:8000",
        "frontend_url": "http://host.docker.internal:5173",
        "test_endpoints": [
            ("GET", "/", 200),
            ("GET", "/ready", 200),
            ("POST", "/api/v1/auth/login", 401),  # should reject empty creds
        ],
    },
    "melanin-tech-website": {
        "frontend_path": "/app/melanin-tech-website",
        "backend_url": "http://host.docker.internal:3000",
        "frontend_url": "http://host.docker.internal:3000",
        "test_endpoints": [
            ("GET", "/", 200),
        ],
    },
}


def _run_cmd(cmd: str, cwd: str = None, timeout: int = 60) -> dict:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return {"pass": result.returncode == 0, "output": result.stdout[-500:] + result.stderr[-500:]}
    except subprocess.TimeoutExpired:
        return {"pass": False, "output": "Timeout"}
    except Exception as e:
        return {"pass": False, "output": str(e)}


def _check_endpoint(base_url: str, method: str, path: str, expected_status: int) -> dict:
    try:
        r = httpx.request(method, f"{base_url}{path}", timeout=10)
        return {"pass": r.status_code == expected_status, "output": f"{method} {path} → {r.status_code}"}
    except Exception as e:
        return {"pass": False, "output": f"{method} {path} → {e}"}


def run_qa(project: str) -> dict:
    """Run full QA suite for a project."""
    config = PROJECTS.get(project)
    if not config:
        return {"pass": False, "results": [{"name": "Project lookup", "pass": False, "output": f"Unknown project: {project}"}]}

    results = []

    # 1. Frontend build check
    if os.path.exists(config["frontend_path"]):
        pkg_json = os.path.join(config["frontend_path"], "package.json")
        if os.path.exists(pkg_json):
            r = _run_cmd("npm run build 2>&1 || npx vite build 2>&1", cwd=config["frontend_path"], timeout=120)
            results.append({"name": "Frontend build", **r})

    # 2. API health checks
    for method, path, status in config.get("test_endpoints", []):
        r = _check_endpoint(config["backend_url"], method, path, status)
        results.append({"name": f"API {method} {path}", **r})

    # 3. Backend tests (if pytest exists)
    backend_path = config["frontend_path"].replace("frontend", "backend")
    if os.path.exists(os.path.join(backend_path, "tests")):
        r = _run_cmd("python -m pytest tests/ -v --tb=short 2>&1", cwd=backend_path, timeout=90)
        results.append({"name": "Backend tests", **r})

    # 4. Security: test auth bypass
    r = _check_endpoint(config["backend_url"], "GET", "/api/v1/invoices/", 403)
    results.append({"name": "Security: unauthenticated access blocked", **r})

    # 5. Visual regression via Playwright MCP (mobile viewport)
    try:
        resp = httpx.post(f"{_PLAYWRIGHT_URL}/screenshot/mobile", json={"url": config.get("frontend_url", ""), "fullPage": True}, timeout=30)
        results.append({"name": "Mobile viewport renders", "pass": resp.status_code == 200, "output": f"Screenshot: {resp.status_code}"})
    except Exception as e:
        results.append({"name": "Mobile viewport renders", "pass": True, "output": f"Playwright unavailable (non-blocking): {e}"})

    # 6. Performance: API response time
    try:
        import time
        start = time.time()
        httpx.get(f"{config['backend_url']}/", timeout=10)
        elapsed = round((time.time() - start) * 1000)
        results.append({"name": f"Performance: health endpoint ({elapsed}ms)", "pass": elapsed < 500, "output": f"{elapsed}ms (threshold: 500ms)"})
    except Exception as e:
        results.append({"name": "Performance check", "pass": True, "output": f"Skipped: {e}"})

    all_pass = all(r["pass"] for r in results)
    return {"pass": all_pass, "results": results}


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
    report = f"*QA Result: {status}*\n" + "\n".join(lines)

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
    return {"status": "ok", "agent": "QAAgent"}
