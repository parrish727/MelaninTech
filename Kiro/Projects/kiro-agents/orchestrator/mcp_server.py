"""
MCP Proxy Server — Melanin Technologies Inc.

Unified /tools/invoke endpoint — any agent can call any registered skill.
Skills: list_files, read_file, recall_memory, project_info,
        figma_file, figma_node, web_fetch, shell_exec
"""
import os
import json
import subprocess
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Kiro MCP Proxy", version="2.0.0")

PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")
FIGMA_TOKEN   = os.environ.get("FIGMA_ACCESS_TOKEN", "")
FIGMA_FILE_ID = os.environ.get("FIGMA_FILE_ID", "")

# Per-agent allowed path scopes
AGENT_PATH_SCOPES = {
    "FrontendAgent": [PROJECTS_BASE, "/app/melanin-tech-website"],
    "UXUIAgent":     [PROJECTS_BASE, "/app/melanin-tech-website"],
    "BackendAgent":  [PROJECTS_BASE],
    "ScaffoldAgent": [PROJECTS_BASE],
    "DeployAgent":   [PROJECTS_BASE, "/app/docker"],
    "SupportAgent":  [PROJECTS_BASE],
    "CodeAgent":     [os.path.join(PROJECTS_BASE, "CodeAgent")],
    "FileAgent":     [os.path.join(PROJECTS_BASE, "FileAgent")],
}

# Shell exec is restricted to these agents
SHELL_ALLOWED_AGENTS = {"DeployAgent", "ScaffoldAgent"}


# ── Models ───────────────────────────────────────────────────────────────────

class InvokeRequest(BaseModel):
    tool: str
    agent: str
    args: dict = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _check_scope(agent: str, path: str):
    real = os.path.realpath(path)
    scopes = AGENT_PATH_SCOPES.get(agent, [PROJECTS_BASE])
    if not any(real.startswith(os.path.realpath(s)) for s in scopes):
        raise HTTPException(status_code=403, detail=f"Path '{path}' outside {agent} scope.")


# ── Skill implementations ─────────────────────────────────────────────────────

def _list_files(agent: str, args: dict) -> dict:
    path = args["path"]
    _check_scope(agent, path)
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Not a directory: {path}")
    entries = [
        {"name": e.name, "type": "dir" if e.is_dir() else "file",
         "size": e.stat().st_size if e.is_file() else None}
        for e in os.scandir(path)
    ]
    return {"path": path, "entries": entries}


def _read_file(agent: str, args: dict) -> dict:
    path = args["path"]
    _check_scope(agent, path)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    with open(path, "r", errors="replace") as f:
        content = f.read(51200)
    return {"path": path, "content": content, "truncated": os.path.getsize(path) > 51200}


def _recall_memory(agent: str, args: dict) -> dict:
    from orchestrator.memory import recall
    results = recall(args["query"], limit=args.get("limit", 5))
    return {"results": [dict(r) for r in results]}


def _project_info(agent: str, args: dict) -> dict:
    project = args["project"]
    known = {
        "melanin-tech-website": {
            "path": "/app/melanin-tech-website",
            "type": "nextjs",
            "stack": ["Next.js 16", "TypeScript", "Tailwind CSS", "Framer Motion"],
            "components": ["Nav", "Hero", "Services", "HowWeWork", "Culture", "Stack", "Contact", "Footer"],
            "colors": {
                "blue": "#3D5A99", "blue-dark": "#2C4275", "blue-deep": "#1E2E52",
                "gold": "#B5A84B", "gold-light": "#D4C96A", "sage": "#6B9E78", "off-white": "#F5F3EE",
            },
            "fonts": {"headings": "Syne", "body": "Inter"},
        }
    }
    info = known.get(project.lower())
    if not info:
        path = os.path.join(PROJECTS_BASE, project)
        if os.path.isdir(path):
            info = {"path": path, "type": "unknown", "files": os.listdir(path)[:20]}
        else:
            raise HTTPException(status_code=404, detail=f"Unknown project: {project}")
    return info


def _figma_file(agent: str, args: dict) -> dict:
    file_id = args.get("file_id", FIGMA_FILE_ID)
    if not FIGMA_TOKEN:
        raise HTTPException(status_code=503, detail="FIGMA_ACCESS_TOKEN not configured")
    r = httpx.get(
        f"https://api.figma.com/v1/files/{file_id}",
        headers={"X-Figma-Token": FIGMA_TOKEN},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    # Return trimmed metadata — full file can be huge
    return {
        "name": data.get("name"),
        "lastModified": data.get("lastModified"),
        "pages": [p["name"] for p in data.get("document", {}).get("children", [])],
    }


def _figma_node(agent: str, args: dict) -> dict:
    file_id = args.get("file_id", FIGMA_FILE_ID)
    node_id = args["node_id"]
    if not FIGMA_TOKEN:
        raise HTTPException(status_code=503, detail="FIGMA_ACCESS_TOKEN not configured")
    r = httpx.get(
        f"https://api.figma.com/v1/files/{file_id}/nodes?ids={node_id}",
        headers={"X-Figma-Token": FIGMA_TOKEN},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _web_fetch(agent: str, args: dict) -> dict:
    url = args["url"]
    r = httpx.get(url, timeout=20, follow_redirects=True,
                  headers={"User-Agent": "KiroMCPProxy/2.0"})
    r.raise_for_status()
    text = r.text[:20000]  # cap at 20KB
    return {"url": url, "status": r.status_code, "content": text, "truncated": len(r.text) > 20000}


def _shell_exec(agent: str, args: dict) -> dict:
    if agent not in SHELL_ALLOWED_AGENTS:
        raise HTTPException(status_code=403, detail=f"shell_exec not permitted for {agent}")
    cmd = args["command"]
    # Block obviously destructive patterns
    blocked = ["rm -rf /", "mkfs", "dd if=", "> /dev/", "format /"]
    if any(b in cmd for b in blocked):
        raise HTTPException(status_code=400, detail="Blocked command pattern")
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=30,
        cwd=args.get("cwd", PROJECTS_BASE),
    )
    return {"stdout": result.stdout[:10000], "stderr": result.stderr[:2000], "returncode": result.returncode}


# ── MCP sidecar bridge skills ─────────────────────────────────────────────────

def _bridge(sidecar: str, agent: str, args: dict, timeout: int = 30) -> dict:
    from orchestrator.mcp_bridge import invoke_tool
    tool = args.pop("_tool")
    try:
        return invoke_tool(sidecar, tool, args, timeout=timeout)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MCP sidecar '{sidecar}' error: {e}")


def _github(agent: str, args: dict) -> dict:
    return _bridge("github", agent, args)

def _postgres_mcp(agent: str, args: dict) -> dict:
    # Only BackendAgent and SupportAgent may query the DB via MCP
    if agent not in {"BackendAgent", "SupportAgent"}:
        raise HTTPException(status_code=403, detail=f"postgres_mcp not permitted for {agent}")
    return _bridge("postgres", agent, args)

def _figma_mcp(agent: str, args: dict) -> dict:
    return _bridge("figma", agent, args)

def _fetch_mcp(agent: str, args: dict) -> dict:
    return _bridge("fetch", agent, args)


# ── Tool registry ─────────────────────────────────────────────────────────────

TOOLS = {
    "list_files":    (_list_files,    "List files in a directory within agent scope"),
    "read_file":     (_read_file,     "Read file contents within agent scope (50KB cap)"),
    "recall_memory": (_recall_memory, "Recall semantically similar past tasks from vector memory"),
    "project_info":  (_project_info,  "Get structured metadata about a named project"),
    "figma_file":    (_figma_file,    "Get Figma file metadata and page list"),
    "figma_node":    (_figma_node,    "Get a specific Figma node by ID"),
    "web_fetch":     (_web_fetch,     "Fetch a URL and return its text content (20KB cap)"),
    "shell_exec":    (_shell_exec,    "Execute a shell command (DeployAgent/ScaffoldAgent only)"),
    # MCP sidecar bridge tools
    "github":        (_github,        "Call any GitHub MCP tool — pass _tool + args (e.g. search_repositories, get_file_contents, create_pull_request)"),
    "postgres_mcp":  (_postgres_mcp,  "Call any Postgres MCP tool — pass _tool + args (BackendAgent/SupportAgent only)"),
    "figma_mcp":     (_figma_mcp,     "Call any Figma MCP tool — pass _tool + args"),
    "fetch_mcp":     (_fetch_mcp,     "Fetch and extract web content via MCP fetch server — pass _tool='fetch' + url"),
}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/tools/invoke")
def invoke(req: InvokeRequest):
    """Unified tool invocation endpoint."""
    handler = TOOLS.get(req.tool)
    if not handler:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {req.tool}. Available: {list(TOOLS)}")
    fn, _ = handler
    try:
        return fn(req.agent, req.args)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
def list_tools():
    return {"tools": [{"name": k, "description": v[1]} for k, v in TOOLS.items()]}


@app.get("/tools/sidecar/{sidecar}")
def sidecar_tools(sidecar: str):
    """List tools available on a specific MCP sidecar."""
    from orchestrator.mcp_bridge import list_tools
    try:
        return {"sidecar": sidecar, "tools": list_tools(sidecar)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Legacy endpoints (backward compat) ───────────────────────────────────────

@app.post("/tools/list_files")
def legacy_list_files(req: dict):
    return _list_files(req.get("agent", ""), req)

@app.post("/tools/read_file")
def legacy_read_file(req: dict):
    return _read_file(req.get("agent", ""), req)

@app.post("/tools/recall_memory")
def legacy_recall_memory(req: dict):
    return _recall_memory(req.get("agent", ""), req)

@app.post("/tools/project_info")
def legacy_project_info(req: dict):
    return _project_info("", req)
