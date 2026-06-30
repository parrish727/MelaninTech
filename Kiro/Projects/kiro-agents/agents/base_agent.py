import os
import json
from fastapi import FastAPI, HTTPException

# OpenRouter uses the OpenAI SDK with a custom base URL.
# Set LLM_PROVIDER=openrouter in .env to use OpenRouter.
# Set LLM_PROVIDER=anthropic (default) to keep using Claude directly.

_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
_PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")
_SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")

# --- Skill Loader ---
def load_skill(skill_name: str) -> str:
    """Load a skill.md file and return its content as a system prompt.
    Falls back to empty string if not found (backward compatible).
    """
    # Check env override first (for dynamic agents)
    skill_file = os.environ.get("SKILL_FILE")
    if skill_file and os.path.isfile(skill_file):
        with open(skill_file, "r") as f:
            return f.read()

    # Standard path
    path = os.path.join(_SKILLS_DIR, f"{skill_name}.skill.md")
    if os.path.isfile(path):
        with open(path, "r") as f:
            return f.read()
    return ""

# --- Guardrails ---
_BLOCKED_PATTERNS = ["rm -rf", "DROP TABLE", "DROP DATABASE", "TRUNCATE", "format /", "mkfs"]

# --- Project Isolation Registry ---
# Each client project is completely isolated. Agents ONLY access their assigned project.
PROJECT_REGISTRY = {
    "melanin-tech-website": "/app/melanin-tech-website",
    "orthoflow-ai": "/app/orthoflow-frontend",
    "orthoflow-backend": "/app/orthoflow-backend",
}

_ISOLATION_PROMPT = """
CRITICAL — PROJECT ISOLATION RULES:
- You are working on PROJECT: {project} ONLY
- NEVER reference, read, or modify files from any other project
- Each client project is completely separate — different codebase, different data, different namespace
- You already know the file structure, framework, and styling. Never ask about those.
- You MAY ask brief clarification about intent (e.g. "which pages?" or "what style?") but never about technical setup.

CRITICAL — OUTPUT FORMAT:
Your response MUST contain fenced code blocks with the EXACT file path on the first line as a comment.
The orchestrator parses these to write files. If you don't follow this format, your code will NOT be saved.

CORRECT (follow this exactly):
```python
# app/api/routes/invoices.py
from fastapi import APIRouter
...
```

```tsx
// src/pages/Dashboard.tsx
import React from 'react'
...
```

WRONG (will be rejected):
- Plain text explanations without code blocks
- Code blocks without a file path comment on line 1
- Mixing explanation text between code blocks

Output ONLY fenced code blocks with file paths. One block per file. No prose.
"""

def _guard_model(model: str):
    if model.startswith("openai/"):
        raise ValueError(f"OpenAI models are not approved. Got: {model}")

def _guard_path(path: str):
    real = os.path.realpath(path)
    base = os.path.realpath(_PROJECTS_BASE)
    # Allow paths under PROJECTS_BASE or any registered project path
    allowed = [base] + [os.path.realpath(p) for p in PROJECT_REGISTRY.values()]
    if not any(real.startswith(a) for a in allowed):
        raise ValueError(f"Path traversal blocked: {path} is outside allowed paths")

def _guard_proposal(text: str):
    for pattern in _BLOCKED_PATTERNS:
        if pattern.lower() in text.lower():
            raise ValueError(f"Blocked pattern detected in proposal: '{pattern}'")


_MCP_URL = os.environ.get("MCP_URL", "http://mcp-server:9000")

# ── Redis Response Cache ──────────────────────────────────────────────────────
import hashlib

_REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
_CACHE_TTL = 86400  # 24 hours
_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        try:
            import redis
            _redis = redis.Redis.from_url(_REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            _redis.ping()
        except Exception:
            _redis = None
    return _redis


def _cache_key(system_prompt: str, task_text: str, model: str) -> str:
    content = f"{model}:{system_prompt[:200]}:{task_text}"
    return f"llm:{hashlib.sha256(content.encode()).hexdigest()[:16]}"


def _cache_get(system_prompt: str, task_text: str, model: str) -> str | None:
    r = _get_redis()
    if not r:
        return None
    try:
        return r.get(_cache_key(system_prompt, task_text, model))
    except Exception:
        return None


def _cache_set(system_prompt: str, task_text: str, model: str, response: str):
    r = _get_redis()
    if not r:
        return
    try:
        r.setex(_cache_key(system_prompt, task_text, model), _CACHE_TTL, response)
    except Exception:
        pass


def call_tool(agent_name: str, tool: str, args: dict, timeout: int = 15) -> dict | None:
    """Call any MCP skill by name. Returns parsed JSON or None on failure."""
    try:
        import httpx
        r = httpx.post(
            f"{_MCP_URL}/tools/invoke",
            json={"tool": tool, "agent": agent_name, "args": args},
            timeout=timeout,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def fetch_mcp_context(agent_name: str, project: str) -> str:
    """Fetch project context from MCP server to prepend to the LLM prompt."""
    context_parts = []

    info = call_tool(agent_name, "project_info", {"project": project})
    if info:
        context_parts.append(f"Project info:\n{json.dumps(info, indent=2)}")

    memory = call_tool(agent_name, "recall_memory", {"query": project, "limit": 3})
    if memory and memory.get("results"):
        lines = [f"- [{x['decision']}] {x['task']}" for x in memory["results"]]
        context_parts.append("Similar past tasks:\n" + "\n".join(lines))

    return "\n\n".join(context_parts)

if _PROVIDER == "openrouter":
    from openai import OpenAI
    _client = OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )
else:
    import anthropic as _anthropic
    _anthropic_client = _anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def select_model(task_text: str) -> str:
    task_lower = task_text.lower()
    if _PROVIDER == "openrouter":
        if any(k in task_lower for k in ["architect", "design", "refactor", "optimize", "review", "analyze"]):
            model = os.environ.get("MODEL_HEAVY", "anthropic/claude-opus-4-5")
        elif any(k in task_lower for k in ["rename", "move", "delete", "list", "read", "simple", "quick"]):
            model = os.environ.get("MODEL_LIGHT", "anthropic/claude-haiku-4-5")
        else:
            model = os.environ.get("MODEL_DEFAULT", "anthropic/claude-sonnet-4-5")
    else:
        if any(k in task_lower for k in ["architect", "design", "refactor", "optimize", "review", "analyze"]):
            model = "claude-opus-4-6"
        elif any(k in task_lower for k in ["rename", "move", "delete", "list", "read", "simple", "quick"]):
            model = "claude-haiku-4-5-20251001"
        else:
            model = "claude-sonnet-4-6"
    _guard_model(model)
    return model


def _log_usage(agent: str, model: str, project: str, input_tokens: int, output_tokens: int):
    """Log LLM usage to database for cost tracking."""
    # Cost per 1M tokens (approximate)
    costs = {
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
        "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    }
    rate = costs.get(model, {"input": 3.0, "output": 15.0})
    cost = (input_tokens * rate["input"] / 1_000_000) + (output_tokens * rate["output"] / 1_000_000)
    try:
        import psycopg2
        conn = psycopg2.connect(os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro"))
        cur = conn.cursor()
        cur.execute("INSERT INTO llm_usage (agent, model, project, input_tokens, output_tokens, cost_usd) VALUES (%s,%s,%s,%s,%s,%s)",
                    (agent, model, project, input_tokens, output_tokens, cost))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _complete(model: str, system_prompt: str, task_text: str, max_tokens: int = 8096) -> str:
    # Check Redis cache first
    cached = _cache_get(system_prompt, task_text, model)
    if cached:
        return cached

    input_est = len(system_prompt + task_text) // 4  # rough token estimate
    if _PROVIDER == "openrouter":
        response = _client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task_text},
            ],
            extra_headers={"X-Title": "Melanin Technologies"},
        )
        output = response.choices[0].message.content
        output_est = len(output) // 4
        _log_usage("agent", model, "default", input_est, output_est)
    else:
        message = _anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": task_text}],
        )
        output = message.content[0].text
        _log_usage("agent", model, "default", message.usage.input_tokens, message.usage.output_tokens)

    # Store in Redis (24hr TTL)
    _cache_set(system_prompt, task_text, model, output)
    return output


def create_app(agent_name: str, system_prompt: str, handle_task_fn):
    """Create a FastAPI app for an agent.
    system_prompt can be:
      - A string (backward compatible, used as-is)
      - None (will attempt to load from skills/{agent_name}.skill.md)
    """
    # Load from skill file if prompt is None or empty
    if not system_prompt:
        skill_name = agent_name.lower().replace("agent", "")
        system_prompt = load_skill(skill_name) or "You are a helpful AI agent."

    app = FastAPI()

    @app.post("/task")
    def task(body: dict):
        import threading

        task_text = body["task"]
        project = body.get("project", "default")
        callback_id = body.get("callback_id")
        model = select_model(task_text)

        # heartbeat thread — pulses every 15s while LLM is working
        _stop = threading.Event()
        def _pulse():
            while not _stop.is_set():
                if callback_id:
                    try:
                        from orchestrator.tickets import heartbeat as hb
                        hb(callback_id, f"{agent_name}: generating with {model}")
                    except Exception:
                        pass
                _stop.wait(15)

        pulse_thread = threading.Thread(target=_pulse, daemon=True)
        pulse_thread.start()

        try:
            # enrich prompt with MCP context (project info + past tasks)
            mcp_context = fetch_mcp_context(agent_name, project)
            # Enforce project isolation on EVERY agent call
            isolation = _ISOLATION_PROMPT.format(project=project)
            enriched_prompt = f"{system_prompt}\n\n{isolation}\n\n{mcp_context}" if mcp_context else f"{system_prompt}\n\n{isolation}"
            proposal_text = _complete(model, enriched_prompt, task_text)
            _guard_proposal(proposal_text)
            project_path = os.path.join(_PROJECTS_BASE, project)
            _guard_path(project_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            _stop.set()

        return handle_task_fn(task_text, project, proposal_text, model)

    return app
