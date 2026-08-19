"""
Custom MCP Gateway — exposes Slack, Google, Cloudflare, and Docker as MCP-compatible tools.

Runs as a single FastAPI service on port 9014-9017 (or combined on 9014).
Accepts JSON-RPC 2.0 requests, routes to the appropriate integration.

This avoids needing separate containers for each — one gateway handles all custom MCPs.
"""
import os
import json
import subprocess
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-gateway")

app = FastAPI(title="Melanin MCP Gateway", version="1.0.0")

# ── Config ────────────────────────────────────────────────────────────────────

SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")
CLOUDFLARE_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_ZONE_ID = os.environ.get("CLOUDFLARE_ZONE_ID", "")


# ── Models ────────────────────────────────────────────────────────────────────

class RPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int = 1
    method: str
    params: dict = {}


# ── Tool Definitions ──────────────────────────────────────────────────────────

TOOLS = {
    # Slack
    "slack.send_message": {
        "description": "Send a message to a Slack channel",
        "params": {"channel": "string (optional, defaults to main)", "text": "string (required)"},
    },
    "slack.read_channel": {
        "description": "Read recent messages from a Slack channel",
        "params": {"channel": "string (optional)", "limit": "integer (default 20)"},
    },
    # Google (GSC, Gmail, Calendar wrappers)
    "google.gsc_query": {
        "description": "Query Google Search Console for keyword performance",
        "params": {"domain": "string", "days_back": "integer (default 28)", "limit": "integer (default 50)"},
    },
    "google.gmail_read": {
        "description": "Read recent inbox emails",
        "params": {"max_results": "integer (default 10)"},
    },
    "google.gmail_send": {
        "description": "Send an email via Gmail",
        "params": {"to": "string", "subject": "string", "body": "string"},
    },
    # Cloudflare
    "cloudflare.purge_cache": {
        "description": "Purge Cloudflare cache for a domain",
        "params": {"purge_everything": "boolean (default true)"},
    },
    "cloudflare.list_dns": {
        "description": "List DNS records for the zone",
        "params": {"type": "string (optional, e.g. A, CNAME, TXT)"},
    },
    "cloudflare.update_dns": {
        "description": "Update a DNS record",
        "params": {"record_id": "string", "content": "string", "type": "string"},
    },
    # Docker
    "docker.list_containers": {
        "description": "List running Docker containers",
        "params": {},
    },
    "docker.restart": {
        "description": "Restart a Docker container by name",
        "params": {"container": "string (required)"},
    },
    "docker.logs": {
        "description": "Get recent logs from a container",
        "params": {"container": "string (required)", "tail": "integer (default 50)"},
    },
    "docker.build_deploy": {
        "description": "Build and redeploy a docker-compose service",
        "params": {"service": "string (required)"},
    },
}


# ── Tool Implementations ──────────────────────────────────────────────────────

def _slack_send(params: dict) -> dict:
    import httpx
    channel = params.get("channel", SLACK_CHANNEL)
    text = params.get("text", "")
    if not text:
        return {"error": "text is required"}
    r = httpx.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {SLACK_TOKEN}", "Content-Type": "application/json"},
        json={"channel": channel, "text": text},
        timeout=10,
    )
    data = r.json()
    return {"ok": data.get("ok"), "ts": data.get("ts"), "error": data.get("error")}


def _slack_read(params: dict) -> dict:
    import httpx
    channel = params.get("channel", SLACK_CHANNEL)
    limit = params.get("limit", 20)
    r = httpx.get(
        "https://slack.com/api/conversations.history",
        headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
        params={"channel": channel, "limit": limit},
        timeout=10,
    )
    data = r.json()
    messages = [{"text": m.get("text", ""), "user": m.get("user"), "ts": m.get("ts")} for m in data.get("messages", [])]
    return {"messages": messages, "count": len(messages)}


def _google_gsc_query(params: dict) -> dict:
    import sys
    sys.path.insert(0, "/app")
    from integrations.seo.gsc import GSCConnector
    from integrations.seo.models import get_site, get_gsc_data
    domain = params.get("domain", "melanin-tech.com")
    site = get_site(domain)
    if not site:
        return {"error": f"Site {domain} not registered"}
    data = get_gsc_data(site["id"], limit=params.get("limit", 50), days_back=params.get("days_back", 28))
    return {"rows": data, "count": len(data)}


def _google_gmail_read(params: dict) -> dict:
    import sys
    sys.path.insert(0, "/app")
    from integrations.gmail import GmailConnector
    import json as _json
    creds_path = "/app/integrations/credentials/melanin-tech/gmail.json"
    try:
        with open(creds_path) as f:
            creds = _json.load(f)
        gmail = GmailConnector("melanin-tech", creds)
        emails = gmail.read_inbox(max_results=params.get("max_results", 10))
        return {"emails": emails}
    except Exception as e:
        return {"error": str(e)}


def _google_gmail_send(params: dict) -> dict:
    import sys
    sys.path.insert(0, "/app")
    from integrations.gmail import GmailConnector
    import json as _json
    creds_path = "/app/integrations/credentials/melanin-tech/gmail.json"
    try:
        with open(creds_path) as f:
            creds = _json.load(f)
        gmail = GmailConnector("melanin-tech", creds)
        result = gmail.send_email(to=params["to"], subject=params["subject"], body=params["body"])
        return {"sent": True, "message_id": result}
    except Exception as e:
        return {"error": str(e)}


def _cloudflare_purge(params: dict) -> dict:
    import httpx
    if not CLOUDFLARE_TOKEN or not CLOUDFLARE_ZONE_ID:
        return {"error": "Cloudflare credentials not configured"}
    r = httpx.post(
        f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/purge_cache",
        headers={"Authorization": f"Bearer {CLOUDFLARE_TOKEN}", "Content-Type": "application/json"},
        json={"purge_everything": params.get("purge_everything", True)},
        timeout=15,
    )
    return r.json()


def _cloudflare_list_dns(params: dict) -> dict:
    import httpx
    if not CLOUDFLARE_TOKEN or not CLOUDFLARE_ZONE_ID:
        return {"error": "Cloudflare credentials not configured"}
    query_params = {}
    if params.get("type"):
        query_params["type"] = params["type"]
    r = httpx.get(
        f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records",
        headers={"Authorization": f"Bearer {CLOUDFLARE_TOKEN}"},
        params=query_params,
        timeout=15,
    )
    data = r.json()
    records = [{"id": rec["id"], "type": rec["type"], "name": rec["name"], "content": rec["content"]} for rec in data.get("result", [])]
    return {"records": records, "count": len(records)}


def _cloudflare_update_dns(params: dict) -> dict:
    import httpx
    if not CLOUDFLARE_TOKEN or not CLOUDFLARE_ZONE_ID:
        return {"error": "Cloudflare credentials not configured"}
    record_id = params.get("record_id")
    if not record_id:
        return {"error": "record_id is required"}
    r = httpx.patch(
        f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{record_id}",
        headers={"Authorization": f"Bearer {CLOUDFLARE_TOKEN}", "Content-Type": "application/json"},
        json={"content": params.get("content"), "type": params.get("type", "A")},
        timeout=15,
    )
    return r.json()


def _docker_list(params: dict) -> dict:
    result = subprocess.run(["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"], capture_output=True, text=True, timeout=10)
    containers = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            containers.append({"name": parts[0], "status": parts[1], "image": parts[2]})
    return {"containers": containers, "count": len(containers)}


def _docker_restart(params: dict) -> dict:
    container = params.get("container")
    if not container:
        return {"error": "container name is required"}
    result = subprocess.run(["docker", "restart", container], capture_output=True, text=True, timeout=30)
    return {"success": result.returncode == 0, "output": result.stdout.strip(), "error": result.stderr.strip()}


def _docker_logs(params: dict) -> dict:
    container = params.get("container")
    if not container:
        return {"error": "container name is required"}
    tail = str(params.get("tail", 50))
    result = subprocess.run(["docker", "logs", container, "--tail", tail], capture_output=True, text=True, timeout=10)
    return {"logs": result.stdout[-5000:], "stderr": result.stderr[-2000:]}


def _docker_build_deploy(params: dict) -> dict:
    service = params.get("service")
    if not service:
        return {"error": "service name is required"}
    compose_dir = "/app/docker"
    build = subprocess.run(["docker", "compose", "build", service], capture_output=True, text=True, timeout=300, cwd=compose_dir)
    if build.returncode != 0:
        return {"success": False, "phase": "build", "error": build.stderr[-2000:]}
    up = subprocess.run(["docker", "compose", "up", "-d", service], capture_output=True, text=True, timeout=60, cwd=compose_dir)
    return {"success": up.returncode == 0, "phase": "deploy", "output": up.stdout[-1000:]}


# ── Dispatch ──────────────────────────────────────────────────────────────────

_HANDLERS = {
    "slack.send_message": _slack_send,
    "slack.read_channel": _slack_read,
    "google.gsc_query": _google_gsc_query,
    "google.gmail_read": _google_gmail_read,
    "google.gmail_send": _google_gmail_send,
    "cloudflare.purge_cache": _cloudflare_purge,
    "cloudflare.list_dns": _cloudflare_list_dns,
    "cloudflare.update_dns": _cloudflare_update_dns,
    "docker.list_containers": _docker_list,
    "docker.restart": _docker_restart,
    "docker.logs": _docker_logs,
    "docker.build_deploy": _docker_build_deploy,
}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/rpc")
def rpc(req: RPCRequest):
    """JSON-RPC 2.0 endpoint — route to the appropriate tool handler."""
    if req.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {"tools": [{"name": k, **v} for k, v in TOOLS.items()]},
        }

    if req.method == "tools/call":
        tool_name = req.params.get("name", "")
        arguments = req.params.get("arguments", {})
        handler = _HANDLERS.get(tool_name)
        if not handler:
            return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}
        try:
            result = handler(arguments)
            return {"jsonrpc": "2.0", "id": req.id, "result": result}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32000, "message": str(e)}}

    return {"jsonrpc": "2.0", "id": req.id, "error": {"code": -32601, "message": f"Unknown method: {req.method}"}}


@app.get("/tools")
def list_tools():
    """REST endpoint for tool discovery."""
    return {"tools": [{"name": k, "description": v["description"]} for k, v in TOOLS.items()]}


@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-gateway", "tools": len(TOOLS)}
