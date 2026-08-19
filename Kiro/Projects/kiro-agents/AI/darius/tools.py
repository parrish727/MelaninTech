"""
Darius Tools — smolagents Tool subclasses.
Each tool is self-contained and safe-guarded.

Features:
- Auto-discovers MCP tools at startup (zero token cost)
- Destructive tool confirmation via callback (zero token cost)
"""
import os
import subprocess
import httpx
from smolagents import Tool

_PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")
_MCP_URL = os.environ.get("MCP_URL", "http://mcp-server:9000")
_BLOCKED = ["rm -rf /", "mkfs", "dd if=", "> /dev/", "DROP TABLE", "DROP DATABASE"]

# Destructive patterns that require confirmation
_DESTRUCTIVE = ["rm ", "git push", "git reset", "docker rm", "docker stop", "DROP", "TRUNCATE", "DELETE FROM"]

# Confirmation callback — set externally by agent runner
_confirm_callback = None


def set_confirm_callback(fn):
    """Set a callback for destructive action confirmation. fn(tool, args) -> bool"""
    global _confirm_callback
    _confirm_callback = fn


def _guard(text: str):
    for pattern in _BLOCKED:
        if pattern.lower() in text.lower():
            raise ValueError(f"Blocked pattern: '{pattern}'")


def _needs_confirmation(text: str) -> bool:
    return any(p.lower() in text.lower() for p in _DESTRUCTIVE)


def _confirm(tool_name: str, detail: str) -> bool:
    """Check if destructive action is approved."""
    if _confirm_callback:
        return _confirm_callback(tool_name, detail)
    return True  # no callback = auto-approve (backward compatible)


# ── File tools ────────────────────────────────────────────────────────────────

class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file. Returns text content (capped at 50KB)."
    inputs = {"path": {"type": "string", "description": "Absolute or relative file path"}}
    output_type = "string"

    def forward(self, path: str) -> str:
        path = os.path.realpath(path)
        if not os.path.isfile(path):
            return f"ERROR: File not found: {path}"
        with open(path, "r", errors="replace") as f:
            content = f.read(51200)
        truncated = os.path.getsize(path) > 51200
        return content + ("\n[TRUNCATED]" if truncated else "")


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file, creating parent directories as needed."
    inputs = {
        "path": {"type": "string", "description": "File path to write"},
        "content": {"type": "string", "description": "Content to write"},
    }
    output_type = "string"

    def forward(self, path: str, content: str) -> str:
        _guard(content)
        path = os.path.realpath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Written: {path} ({len(content)} bytes)"


class ListDirTool(Tool):
    name = "list_dir"
    description = "List files and directories at a given path."
    inputs = {"path": {"type": "string", "description": "Directory path to list"}}
    output_type = "string"

    def forward(self, path: str) -> str:
        path = os.path.realpath(path)
        if not os.path.isdir(path):
            return f"ERROR: Not a directory: {path}"
        entries = []
        for e in sorted(os.scandir(path), key=lambda x: (x.is_file(), x.name)):
            kind = "DIR " if e.is_dir() else "FILE"
            entries.append(f"{kind}  {e.name}")
        return "\n".join(entries) or "(empty)"


# ── Shell tool (with confirmation) ────────────────────────────────────────────

class ShellTool(Tool):
    name = "shell"
    description = "Run a shell command and return stdout + stderr. Timeout: 60s. Destructive commands require confirmation."
    inputs = {
        "command": {"type": "string", "description": "Shell command to execute"},
        "cwd": {"type": "string", "description": "Working directory (optional)", "nullable": True},
    }
    output_type = "string"

    def forward(self, command: str, cwd: str = None) -> str:
        _guard(command)
        if _needs_confirmation(command) and not _confirm("shell", command):
            return "BLOCKED: Destructive command requires confirmation. Not approved."
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=60, cwd=cwd or _PROJECTS_BASE,
        )
        out = result.stdout[:8000]
        err = result.stderr[:2000]
        return f"[rc={result.returncode}]\n{out}" + (f"\nSTDERR: {err}" if err else "")


# ── Git tool (with confirmation for push/reset) ──────────────────────────────

class GitTool(Tool):
    name = "git"
    description = "Run a git command in a repo directory. Push/reset require confirmation."
    inputs = {
        "subcommand": {"type": "string", "description": "Git subcommand and args (without 'git' prefix)"},
        "repo_path": {"type": "string", "description": "Path to the git repo"},
    }
    output_type = "string"

    def forward(self, subcommand: str, repo_path: str) -> str:
        _guard(subcommand)
        if _needs_confirmation(f"git {subcommand}") and not _confirm("git", subcommand):
            return "BLOCKED: Destructive git command requires confirmation. Not approved."
        result = subprocess.run(
            f"git {subcommand}", shell=True, capture_output=True, text=True,
            timeout=30, cwd=os.path.realpath(repo_path),
        )
        return result.stdout[:8000] or result.stderr[:2000]


# ── MCP bridge tool (auto-discovers available tools) ──────────────────────────

def _discover_mcp_tools() -> str:
    """Query MCP server for available tools at startup. Zero token cost."""
    try:
        r = httpx.get(f"{_MCP_URL}/tools", timeout=5)
        if r.status_code == 200:
            tools = r.json()
            if isinstance(tools, list):
                return ", ".join(t.get("name", t) if isinstance(t, dict) else str(t) for t in tools)
            if isinstance(tools, dict) and "tools" in tools:
                return ", ".join(t.get("name", "") for t in tools["tools"])
    except Exception:
        pass
    return "list_files, read_file, recall_memory, project_info, web_fetch, shell_exec, github, postgres_mcp, figma_mcp, fetch_mcp"


def _load_registry_descriptions() -> str:
    """Load tool descriptions from _registry.json for richer LLM context."""
    import os
    registry_paths = [
        "/app/_registry.json",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "_registry.json"),
    ]
    for path in registry_paths:
        try:
            with open(path) as f:
                import json as _json
                registry = _json.load(f)
            # Build a concise description of all available tools
            lines = []
            # MCP sidecars
            for name, sidecar in registry.get("mcp_sidecars", {}).items():
                if sidecar.get("status") == "planned":
                    continue
                for tool in sidecar.get("tools", []):
                    lines.append(f"{name}.{tool['name']}: {tool['description']}")
            # Gateway tools
            gateway = registry.get("mcp_sidecars", {}).get("slack", {})
            # Internal tools
            for name, service in registry.get("internal_tools", {}).items():
                for tool in service.get("tools", []):
                    lines.append(f"{name}.{tool['name']}: {tool['description']}")
            return "\n".join(lines[:40])  # Cap to avoid prompt bloat
        except Exception:
            continue
    return ""


_MCP_TOOLS_DESC = _discover_mcp_tools()
_REGISTRY_DESC = _load_registry_descriptions()

# Build a richer description if registry is available
_MCP_FULL_DESC = _MCP_TOOLS_DESC
if _REGISTRY_DESC:
    _MCP_FULL_DESC = f"Available tools:\n{_REGISTRY_DESC}"


class MCPTool(Tool):
    name = "mcp"
    description = f"Call any MCP skill via the Kiro MCP proxy. {_MCP_TOOLS_DESC}."
    inputs = {
        "tool": {"type": "string", "description": "MCP tool name"},
        "args": {"type": "object", "description": "Tool arguments as a dict"},
    }
    output_type = "string"

    def forward(self, tool: str, args: dict) -> str:
        import json
        try:
            r = httpx.post(
                f"{_MCP_URL}/tools/invoke",
                json={"tool": tool, "agent": "DariusAgent", "args": args},
                timeout=30,
            )
            r.raise_for_status()
            return json.dumps(r.json(), indent=2)[:10000]
        except Exception as e:
            return f"MCP error: {e}"


_GATEWAY_URL = os.environ.get("MCP_GATEWAY_URL", "http://mcp-gateway:9014")


class GatewayTool(Tool):
    name = "gateway"
    description = (
        "Call Slack, Google, Cloudflare, or Docker tools via the MCP gateway. "
        "Tools: slack.send_message, slack.read_channel, google.gsc_query, google.gmail_read, "
        "google.gmail_send, cloudflare.purge_cache, cloudflare.list_dns, cloudflare.update_dns, "
        "docker.list_containers, docker.restart, docker.logs, docker.build_deploy"
    )
    inputs = {
        "tool": {"type": "string", "description": "Gateway tool name (e.g. 'slack.send_message', 'docker.restart')"},
        "args": {"type": "object", "description": "Tool arguments as a dict"},
    }
    output_type = "string"

    def forward(self, tool: str, args: dict) -> str:
        import json
        try:
            r = httpx.post(
                f"{_GATEWAY_URL}/rpc",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool, "arguments": args}},
                timeout=60,
            )
            r.raise_for_status()
            body = r.json()
            if "error" in body:
                return f"Gateway error: {body['error']}"
            return json.dumps(body.get("result", {}), indent=2)[:10000]
        except Exception as e:
            return f"Gateway error: {e}"


class AgentDispatchTool(Tool):
    name = "dispatch"
    description = (
        "Dispatch a task to a specialist agent. "
        "agents: frontend, backend, scaffold, deploy, support, code, file. "
        "Use this instead of writing files yourself when the task is well-defined."
    )
    inputs = {
        "agent": {"type": "string", "description": "Agent name: frontend, backend, scaffold, deploy, support, code, file"},
        "task": {"type": "string", "description": "The specific task for the agent"},
        "project": {"type": "string", "description": "Project name (e.g. melanin-tech-website)", "nullable": True},
    }
    output_type = "string"

    def forward(self, agent: str, task: str, project: str = "default") -> str:
        import json
        urls = {
            "frontend":  "http://frontend-agent:8000",
            "backend":   "http://backend-agent:8000",
            "scaffold":  "http://scaffold-agent:8000",
            "deploy":    "http://deploy-agent:8000",
            "support":   "http://support-agent:8000",
            "code":      "http://code-agent:8000",
            "file":      "http://file-agent:8000",
        }
        url = urls.get(agent.lower())
        if not url:
            return f"Unknown agent: {agent}. Available: {list(urls)}"
        try:
            r = httpx.post(f"{url}/task", json={"task": task, "project": project}, timeout=120)
            r.raise_for_status()
            data = r.json()
            return data.get("args", {}).get("proposal", json.dumps(data))[:5000]
        except Exception as e:
            return f"Dispatch error: {e}"


# ── Tool registry ─────────────────────────────────────────────────────────────

# ── Web Search via SearXNG ─────────────────────────────────────────────────────

_SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng:8080")


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web using private SearXNG instance. Returns titles, URLs, and snippets. Use for research, market analysis, and current information."
    inputs = {
        "query": {"type": "string", "description": "Search query"},
        "num_results": {"type": "integer", "description": "Number of results (default 5)", "nullable": True},
    }
    output_type = "string"

    def forward(self, query: str, num_results: int = 5) -> str:
        import json
        try:
            r = httpx.get(
                f"{_SEARXNG_URL}/search",
                params={"q": query, "format": "json", "engines": "google,duckduckgo,brave", "pageno": 1},
                timeout=15,
            )
            r.raise_for_status()
            results = r.json().get("results", [])[:num_results]
            formatted = []
            for res in results:
                formatted.append(f"**{res.get('title', '')}**\n{res.get('url', '')}\n{res.get('content', '')}\n")
            return "\n---\n".join(formatted) if formatted else "No results found."
        except Exception as e:
            return f"Search error: {e}"


# ── Tool registry ─────────────────────────────────────────────────────────────

ALL_TOOLS = [ReadFileTool(), WriteFileTool(), ListDirTool(), ShellTool(), GitTool(), MCPTool(), GatewayTool(), AgentDispatchTool(), WebSearchTool()]
