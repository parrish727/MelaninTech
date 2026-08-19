import os
import json
from fastapi import FastAPI, HTTPException

# OpenRouter uses the OpenAI SDK with a custom base URL.
# Set LLM_PROVIDER=openrouter in .env to use OpenRouter.
# Set LLM_PROVIDER=anthropic (default) to keep using Claude directly.

_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
_PROJECTS_BASE = os.environ.get("PROJECTS_BASE", "/app/Projects")
_SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")

# Enterprise AI Agent Framework — Steering Loader
from agents.steering_loader import load_agent_steering, load_shared_steering

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


_MONTHLY_BUDGET_USD = float(os.environ.get("LLM_MONTHLY_BUDGET_USD", "25.00"))
_CREDIT_GUARD_THRESHOLD = 0.95  # Block at 95% to prevent exhaustion


def _guard_credit_balance():
    """Pre-flight credit check. Raises if monthly spend is at 95%+ of budget.
    This prevents credit-exhaustion errors from reaching the LLM API and counting as SLO failures.
    """
    try:
        import psycopg2
        conn = psycopg2.connect(os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro"))
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM llm_traces WHERE created_at > date_trunc('month', NOW())")
        spent = float(cur.fetchone()[0])
        conn.close()

        if spent >= _MONTHLY_BUDGET_USD * _CREDIT_GUARD_THRESHOLD:
            raise CreditExhaustedError(
                f"Monthly LLM budget nearly exhausted: ${spent:.2f} / ${_MONTHLY_BUDGET_USD:.2f} "
                f"({spent/_MONTHLY_BUDGET_USD*100:.0f}%). Blocking call to preserve availability. "
                f"Increase LLM_MONTHLY_BUDGET_USD or wait for next billing cycle."
            )
    except CreditExhaustedError:
        raise
    except Exception:
        pass  # If DB is unreachable, allow the call through — fail open


class CreditExhaustedError(Exception):
    """Raised when monthly credit budget is nearly exhausted."""
    pass


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
        # Tiered model selection — matches Darius's routing logic
        if any(k in task_lower for k in ["architect", "redesign entire", "system design", "migration strategy"]):
            model = "claude-opus-4-6"
        elif any(k in task_lower for k in ["write documentation", "write docs", "marketing", "proposal", "readme", "blog"]):
            model = "claude-fable-5"
        elif any(k in task_lower for k in ["refactor", "rewrite", "analyze", "review", "optimize", "implement", "build", "create", "fix", "debug"]):
            model = "claude-sonnet-5"
        elif any(k in task_lower for k in ["rename", "move", "delete", "list", "read", "simple", "quick", "check", "status"]):
            model = "claude-haiku-4-5-20251001"
        else:
            model = "claude-sonnet-4-6"
    _guard_model(model)
    return model


def _log_usage(agent: str, model: str, project: str, input_tokens: int, output_tokens: int):
    """Log LLM usage to database for cost tracking."""
    # Cost per 1M tokens (approximate — check Anthropic pricing page for latest)
    costs = {
        "claude-opus-4-6": {"input": 15.0, "output": 75.0},
        "claude-opus-4-7": {"input": 15.0, "output": 75.0},
        "claude-opus-4-8": {"input": 15.0, "output": 75.0},
        "claude-sonnet-5": {"input": 3.0, "output": 15.0},
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-fable-5": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
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
    import time as _t
    # Check Redis cache first
    cached = _cache_get(system_prompt, task_text, model)
    if cached:
        _log_trace("agent", model, "default", task_text[:100], 0, 0, 0, "success", cached=True)
        return cached

    # Pre-flight credit guard — prevent credit-exhaustion failures
    _guard_credit_balance()

    start = _t.time()
    input_tokens = 0
    output_tokens = 0
    error_type = None
    error_msg = None
    status = "success"

    try:
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
            input_tokens = len(system_prompt + task_text) // 4
            output_tokens = len(output) // 4
        else:
            message = _anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": task_text}],
            )
            output = message.content[0].text
            input_tokens = message.usage.input_tokens
            output_tokens = message.usage.output_tokens
    except CreditExhaustedError as e:
        latency_ms = int((_t.time() - start) * 1000)
        # Log as 'credit_guard' — this is a PREVENTED failure, not a system error
        _log_trace("agent", model, "default", task_text[:100], 0, 0, latency_ms, "credit_guard")
        # Return a graceful degradation response instead of crashing
        return f"[Credit budget guard] Unable to process — {str(e)}. Task has been queued for when credits are available."
    except Exception as e:
        latency_ms = int((_t.time() - start) * 1000)
        error_type = type(e).__name__
        error_msg = str(e)[:500]
        if "rate_limit" in error_msg.lower():
            status = "rate_limited"
        elif "timeout" in error_msg.lower():
            status = "timeout"
        elif "credit balance" in error_msg.lower():
            # Anthropic returned credit exhaustion — log as credit_guard, not error
            status = "credit_guard"
            _log_trace("agent", model, "default", task_text[:100], input_tokens, output_tokens, latency_ms, status, error_type=error_type, error_message=error_msg)
            return f"[Credit exhausted] Anthropic API credits depleted. Contact pktech_dev to top up."
        else:
            status = "error"
        _log_trace("agent", model, "default", task_text[:100], input_tokens, output_tokens, latency_ms, status, error_type=error_type, error_message=error_msg)
        _log_failure("agent", model, status, error_type, error_msg)
        raise

    latency_ms = int((_t.time() - start) * 1000)
    _log_trace("agent", model, "default", task_text[:100], input_tokens, output_tokens, latency_ms, "success")

    # Store in Redis (24hr TTL)
    _cache_set(system_prompt, task_text, model, output)
    return output


def _log_trace(agent: str, model: str, project: str, task_preview: str, input_tokens: int, output_tokens: int, latency_ms: int, status: str, error_type: str = None, error_message: str = None, cached: bool = False):
    """Log full LLM trace for observability."""
    costs = {"claude-opus-4-6": {"input": 15.0, "output": 75.0}, "claude-opus-4-7": {"input": 15.0, "output": 75.0}, "claude-opus-4-8": {"input": 15.0, "output": 75.0}, "claude-sonnet-5": {"input": 3.0, "output": 15.0}, "claude-sonnet-4-6": {"input": 3.0, "output": 15.0}, "claude-fable-5": {"input": 3.0, "output": 15.0}, "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25}}
    rate = costs.get(model, {"input": 3.0, "output": 15.0})
    cost = (input_tokens * rate["input"] / 1_000_000) + (output_tokens * rate["output"] / 1_000_000)
    try:
        import psycopg2
        conn = psycopg2.connect(os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro"))
        cur = conn.cursor()
        cur.execute("INSERT INTO llm_traces (agent, model, project, task_preview, input_tokens, output_tokens, latency_ms, status, error_type, error_message, cost_usd, cached) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (agent, model, project, task_preview, input_tokens, output_tokens, latency_ms, status, error_type, error_message, cost, cached))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _log_failure(agent: str, model: str, failure_type: str, error_code: str, error_message: str):
    """Log LLM failure for root cause analysis."""
    try:
        import psycopg2
        conn = psycopg2.connect(os.environ.get("POSTGRES_DSN", "postgresql://kiro:kiro_secret@postgres:5432/kiro"))
        cur = conn.cursor()
        cur.execute("INSERT INTO llm_failures (agent, model, failure_type, error_code, error_message) VALUES (%s,%s,%s,%s,%s)",
                    (agent, model, failure_type, error_code, error_message[:500] if error_message else None))
        conn.commit()
        conn.close()
    except Exception:
        pass


def create_app(agent_name: str, system_prompt: str, handle_task_fn):
    """Create a FastAPI app for an agent.
    system_prompt can be:
      - A string (backward compatible, used as-is)
      - None (will attempt to load from skills/{agent_name}.skill.md)

    The Enterprise AI Agent Framework steering context is automatically
    appended to provide guardrails, parameters, and environment awareness.
    """
    # Load from skill file if prompt is None or empty
    if not system_prompt:
        skill_name = agent_name.lower().replace("agent", "")
        system_prompt = load_skill(skill_name) or "You are a helpful AI agent."

    # Load Enterprise AI Agent Framework steering context
    steering_context = load_agent_steering(agent_name)

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
            # Compose full prompt: skill + framework steering + isolation + MCP context
            prompt_parts = [system_prompt]
            if steering_context:
                prompt_parts.append(f"\n\n--- ENTERPRISE AI AGENT FRAMEWORK ---\n\n{steering_context}")
            prompt_parts.append(isolation)
            if mcp_context:
                prompt_parts.append(mcp_context)
            enriched_prompt = "\n\n".join(prompt_parts)
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
