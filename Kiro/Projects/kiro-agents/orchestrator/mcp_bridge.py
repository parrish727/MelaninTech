"""
MCP Bridge — calls MCP sidecar servers via JSON-RPC 2.0 over HTTP/SSE.
GitHub MCP uses POST /mcp with Bearer token (SSE response).
Other sidecars use POST /message (JSON response).
"""
import os
import json
import httpx

_GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

_SIDECARS = {
    "github":   ("http://mcp-github:9010", "mcp"),
    "postgres": ("http://mcp-postgres:9011", "message"),
    "figma":    ("http://mcp-figma:9012", "message"),
    "fetch":    ("http://mcp-fetch:9013", "message"),
}

_id = 0


def _next_id() -> int:
    global _id
    _id += 1
    return _id


def _parse_sse(text: str) -> dict:
    """Extract the first JSON-RPC result from an SSE stream."""
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[5:].strip())
    raise ValueError("No data line found in SSE response")


def call(sidecar: str, method: str, params: dict, timeout: int = 30) -> dict:
    """Send a JSON-RPC request to a named MCP sidecar. Returns the result dict."""
    entry = _SIDECARS.get(sidecar)
    if not entry:
        raise ValueError(f"Unknown MCP sidecar: {sidecar}. Available: {list(_SIDECARS)}")

    base, path = entry
    payload = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": method,
        "params": params,
    }
    headers = {"Content-Type": "application/json"}
    if sidecar == "github" and _GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {_GITHUB_TOKEN}"

    r = httpx.post(f"{base}/{path}", json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()

    # GitHub MCP returns SSE; others return plain JSON
    content_type = r.headers.get("content-type", "")
    if "text/event-stream" in content_type or sidecar == "github":
        body = _parse_sse(r.text)
    else:
        body = r.json()

    if "error" in body:
        raise RuntimeError(f"MCP error from {sidecar}: {body['error']}")
    return body.get("result", {})


def list_tools(sidecar: str) -> list[dict]:
    """Return the tool manifest from a sidecar."""
    result = call(sidecar, "tools/list", {})
    return result.get("tools", [])


def invoke_tool(sidecar: str, tool: str, arguments: dict, timeout: int = 30) -> dict:
    """Call a specific tool on a sidecar."""
    return call(sidecar, "tools/call", {"name": tool, "arguments": arguments}, timeout=timeout)
