"""
Darius Agent — smolagents ToolCallingAgent wired to Anthropic Claude.

Features (v2.0):
- Task planning: decomposes complex tasks into DAGs
- Parallel DAG execution for independent steps
- Agent output evaluation with retry loop (max 3, Slack notify on reject)
- Compressed context: auto-summarizes every 5 turns
- Richer trace logging: full reasoning chain for future training data
- Model selection (heavy/light) based on task keywords
- Local model support (Ollama) for HUD-scoped tasks
- Session persistence and replay
- Rate limit retry with backoff
"""
import os
import time
import logging
import uuid
from smolagents import ToolCallingAgent, LiteLLMModel
from AI.darius.tools import ALL_TOOLS
from AI.darius.planner import PlannerTool, plan_task
from AI.darius.evaluator import EvaluatorTool
from AI.darius.context import maybe_compress, build_context
from AI.darius.executor import execute_dag, format_dag_results
from AI.darius.memory import log_trace

logging.getLogger("smolagents").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

# ── Cloud Models (Anthropic Claude — production) ──────────────────────────────
# Tiered model selection: task complexity → appropriate model
_MODEL_APEX = os.environ.get("DARIUS_MODEL_APEX", "anthropic/claude-opus-4-6")         # Architecture, complex refactors, system design
_MODEL_HEAVY = os.environ.get("DARIUS_MODEL_HEAVY", "anthropic/claude-sonnet-5")       # Heavy coding, multi-step implementation
_MODEL_DEFAULT = os.environ.get("DARIUS_MODEL", "anthropic/claude-sonnet-4-6")         # Standard coding, most agent tasks
_MODEL_LIGHT = os.environ.get("DARIUS_MODEL_LIGHT", "anthropic/claude-haiku-4-5-20251001")  # Fast: planning, classification, routing
_MODEL_CREATIVE = os.environ.get("DARIUS_MODEL_CREATIVE", "anthropic/claude-fable-5")  # Narrative: docs, client comms, marketing
_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Local Models (Ollama — HUD internal testing) ─────────────────────────────
_LOCAL_MODEL_HEAVY = os.environ.get("DARIUS_LOCAL_HEAVY", "ollama/mistral-small:24b")
_LOCAL_MODEL_LIGHT = os.environ.get("DARIUS_LOCAL_LIGHT", "ollama/qwen3:14b")
_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
_LOCAL_TIMEOUT = int(os.environ.get("DARIUS_LOCAL_TIMEOUT", "180"))  # 3 min max for local models

# Task classification keywords for model routing
_APEX_KEYWORDS = [
    "architect", "redesign entire", "rewrite from scratch", "system design",
    "migration strategy", "infrastructure overhaul",
]
_HEAVY_KEYWORDS = [
    "refactor", "rewrite", "analyze", "review all", "optimize",
    "implement", "build", "create", "fix", "debug",
    "components", "pipeline", "integrate", "multi-step",
]
_CREATIVE_KEYWORDS = [
    "write documentation", "write docs", "marketing", "client email",
    "proposal", "readme", "blog post", "copy", "narrative",
]
_LIGHT_KEYWORDS = [
    "rename", "move", "delete", "list", "read", "simple", "quick",
    "what is", "check", "status", "summarize",
]


def _select_model(task: str, model_source: str = None, model_override: str = None) -> tuple[str, str]:
    """
    Select model based on task complexity, source, and override.

    Tiers (cloud):
      apex    → Opus 4.6     — architecture, system design, complex refactors
      heavy   → Sonnet 5     — heavy coding, multi-step implementation
      default → Sonnet 4.6   — standard agent tasks
      light   → Haiku 4.5    — fast classification, planning, routing
      creative→ Fable 5      — documentation, client comms, narrative

    Returns: (model_id, model_label) where model_label is for tracing.
    """
    # Explicit override takes priority
    if model_override == "light":
        if model_source == "local":
            return _LOCAL_MODEL_LIGHT, "qwen3:14b"
        return _MODEL_LIGHT, "claude-haiku-4-5"
    elif model_override == "heavy":
        if model_source == "local":
            return _LOCAL_MODEL_HEAVY, "mistral-small:24b"
        return _MODEL_HEAVY, "claude-sonnet-5"
    elif model_override == "apex":
        return _MODEL_APEX, "claude-opus-4-6"
    elif model_override == "creative":
        return _MODEL_CREATIVE, "claude-fable-5"

    # Auto-detect from task keywords
    t = task.lower()

    if model_source == "local":
        is_heavy = any(k in t for k in _HEAVY_KEYWORDS + _APEX_KEYWORDS)
        if is_heavy:
            return _LOCAL_MODEL_HEAVY, "mistral-small:24b"
        return _LOCAL_MODEL_LIGHT, "qwen3:14b"

    # Cloud tiered selection
    if any(k in t for k in _APEX_KEYWORDS):
        return _MODEL_APEX, "claude-opus-4-6"
    if any(k in t for k in _CREATIVE_KEYWORDS):
        return _MODEL_CREATIVE, "claude-fable-5"
    if any(k in t for k in _HEAVY_KEYWORDS):
        return _MODEL_HEAVY, "claude-sonnet-5"
    if any(k in t for k in _LIGHT_KEYWORDS):
        return _MODEL_LIGHT, "claude-haiku-4-5"

    # Default: Sonnet 4.6 (proven workhorse)
    return _MODEL_DEFAULT, "claude-sonnet-4-6"


def _check_ollama_health() -> bool:
    """Quick check if Ollama is reachable."""
    import httpx
    try:
        r = httpx.get(f"{_OLLAMA_URL}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


SYSTEM_PROMPT = """You are Darius, an AI orchestration agent built by Melanin Technologies.

You have access to specialist agents (frontend, backend, scaffold, deploy, support, code, file) and direct tools (read_file, write_file, shell, git, mcp, web_search).

You also have planning and evaluation capabilities:
- plan_task: Decompose complex tasks into a DAG of steps (use for multi-step work)
- evaluate_output: Score agent output quality before passing it through

Strategy — always prefer this order:
1. For complex/multi-agent tasks: call plan_task first, then execute the plan
2. For single-agent tasks: dispatch directly to the specialist
3. Use read_file or mcp tools to understand the codebase first when needed
4. Only use write_file or shell directly when no specialist agent fits

For multi-step workflows, execute steps in sequence. Report progress after each step.
Be concise in reasoning. Process one file or sub-task at a time.
"""

# Load Enterprise AI Agent Framework shared context for Darius
_DARIUS_STEERING = ""
try:
    from agents.steering_loader import load_shared_steering
    _DARIUS_STEERING = load_shared_steering()
except ImportError:
    pass

if _DARIUS_STEERING:
    SYSTEM_PROMPT = f"{SYSTEM_PROMPT}\n\n--- ENTERPRISE AI AGENT FRAMEWORK ---\n\n{_DARIUS_STEERING}"


# Register new tools alongside existing ones
_ALL_TOOLS = ALL_TOOLS + [PlannerTool(), EvaluatorTool()]


def build_agent(task: str = "", model_source: str = None, model_override: str = None) -> tuple[ToolCallingAgent, str]:
    """
    Build a Darius agent with the appropriate model.

    Args:
        task: The task text (used for heavy/light classification)
        model_source: "local" for Ollama models, None for Claude

    Returns:
        (agent, model_label) tuple for tracing
    """
    model_id, model_label = _select_model(task, model_source, model_override)

    if model_source == "local":
        # LiteLLM handles ollama/ prefix — needs api_base for routing
        model = LiteLLMModel(
            model_id=model_id,
            api_base=_OLLAMA_URL,
            api_key="ollama",  # LiteLLM requires a non-empty key
        )
    else:
        model = LiteLLMModel(model_id=model_id, api_key=_API_KEY)

    agent = ToolCallingAgent(
        tools=_ALL_TOOLS,
        model=model,
        max_steps=20,
        verbosity_level=0,
    )
    agent.prompt_templates["system_prompt"] = SYSTEM_PROMPT
    return agent, model_label


def run_task(task: str, session_id: str = None, model_source: str = None, model_override: str = None) -> str:
    """
    Run a task through Darius with planning, execution, evaluation, and compressed context.

    Args:
        task: The task to execute
        session_id: For session persistence
        model_source: "local" for Ollama models, None for Claude (default)
        model_override: "light" forces Haiku, "heavy" forces Sonnet — overrides auto-selection

    Flow:
      1. Build enriched context from session history
      2. Plan the task (if complex)
      3. Execute via DAG engine (parallel where possible)
      4. Evaluate outputs (retry up to MAX_RETRIES on failure)
      5. Compress context if threshold reached
      6. Log full trace for training data
    """
    from AI.darius.memory import save_turn, load_session

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    start_time = time.time()

    # If local model requested, verify Ollama is reachable — fallback to Claude if not
    actual_source = model_source
    if model_source == "local" and not _check_ollama_health():
        actual_source = None  # Fallback to Claude
        log_trace(
            task_id=task_id,
            phase="fallback",
            session_id=session_id,
            tool_name="model_router",
            tool_args={"requested": "local", "reason": "ollama_unreachable"},
            tool_result="Falling back to Claude — Ollama not reachable",
            status="warning",
        )

    # 1. Build enriched context
    enriched_task = task
    if session_id:
        context = build_context(session_id, task)
        if context:
            enriched_task = f"{context}\n\n--- Current Task ---\n{task}"

    # 2. Plan the task (always uses Claude Haiku for speed — planning is cheap)
    plan = plan_task(task, project=session_id or "default")

    # Log the plan
    _, model_label = _select_model(task, actual_source, model_override)
    log_trace(
        task_id=task_id,
        phase="plan",
        session_id=session_id,
        tool_name="planner",
        tool_args={"task": task[:500], "model_source": actual_source or "cloud"},
        tool_result=str(plan),
        model=model_label,
        status="success",
    )

    # 3. Execute
    if len(plan) == 1 and plan[0]["agent"] == "darius":
        # Single darius step — use the smolagents agent directly (most flexible)
        agent, model_label = build_agent(task, model_source=actual_source, model_override=model_override)

        timeout_limit = _LOCAL_TIMEOUT if actual_source == "local" else 300

        for attempt in range(3):
            try:
                result = agent.run(enriched_task)
                break
            except Exception as e:
                error_str = str(e).lower()
                if "rate_limit" in error_str and attempt < 2:
                    time.sleep(60 * (attempt + 1))
                    agent, model_label = build_agent(task, model_source=actual_source, model_override=model_override)
                elif actual_source == "local" and ("timeout" in error_str or "connection" in error_str) and attempt < 2:
                    # Local model failed — fallback to Claude
                    actual_source = None
                    agent, model_label = build_agent(task, model_source=None)
                    log_trace(
                        task_id=task_id,
                        phase="fallback",
                        session_id=session_id,
                        tool_name="model_router",
                        tool_args={"attempt": attempt, "error": str(e)[:200]},
                        tool_result=f"Local model failed, falling back to Claude ({model_label})",
                        status="warning",
                    )
                else:
                    raise

        result = str(result)
    else:
        # Multi-step plan — execute via DAG engine
        dag_results = execute_dag(
            steps=plan,
            project=session_id or "default",
            session_id=task_id,
            evaluate=True,  # evaluation is built into the DAG executor
        )
        result = format_dag_results(dag_results)

    # 4. Log completion
    latency_ms = int((time.time() - start_time) * 1000)
    log_trace(
        task_id=task_id,
        phase="complete",
        session_id=session_id,
        latency_ms=latency_ms,
        tool_result=result[:5000],
        model=model_label,
        status="success",
        tool_args={"model_source": actual_source or "cloud"},
    )

    # 5. Save turn and compress context
    if session_id:
        save_turn(session_id, "user", task)
        save_turn(session_id, "assistant", result)
        maybe_compress(session_id)

    return result


def replay_session(session_id: str, from_turn: int = 0) -> list[str]:
    """Replay a session from a specific turn. Re-runs each user turn through the agent."""
    from AI.darius.memory import load_session

    history = load_session(session_id)
    if not history:
        return [f"No session found: {session_id}"]

    user_turns = [t for t in history if t["role"] == "user"]
    if from_turn >= len(user_turns):
        return [f"Turn {from_turn} out of range (session has {len(user_turns)} user turns)"]

    results = []
    replay_id = f"{session_id}-replay"
    for turn in user_turns[from_turn:]:
        result = run_task(turn["content"], session_id=replay_id)
        results.append(result)

    return results


def chain_tasks(tasks: list[dict], session_id: str = None) -> list[str]:
    """
    Execute a sequence of agent tasks — now powered by the DAG executor.

    Each task dict: {"agent": "frontend", "task": "...", "project": "..."}
    If agent is "darius", runs directly. Otherwise dispatches to specialist.

    Returns list of results, one per step.
    """
    # Convert to DAG format
    dag_steps = []
    for i, step in enumerate(tasks):
        dag_steps.append({
            "id": f"step_{i+1}",
            "agent": step.get("agent", "darius"),
            "task": step.get("task", ""),
            "project": step.get("project"),
            "depends_on": [f"step_{i}"] if i > 0 else [],  # sequential by default
        })

    # Execute DAG
    results = execute_dag(
        steps=dag_steps,
        project=session_id or "default",
        session_id=session_id,
        evaluate=True,
    )

    # Return in order
    return [results.get(f"step_{i+1}", "ERROR: step not found") for i in range(len(tasks))]


def run_template(trigger: str, params: dict = None, session_id: str = None) -> list[str]:
    """
    Execute a YAML template by trigger name.
    Resolves params, then runs chain_tasks with the resolved steps.
    Approval gates are flagged but not blocking (orchestrator handles approval via Slack).
    """
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from orchestrator.template_engine import load_template, resolve_template

    template = load_template(trigger)
    if not template:
        return [f"Template '{trigger}' not found."]

    steps = resolve_template(template, params or {})
    return chain_tasks(steps, session_id=session_id or f"template-{trigger}")
