"""
Darius Agent — smolagents ToolCallingAgent wired to Anthropic Claude.

Features:
- Model selection (heavy/light) based on task keywords
- Session persistence and replay
- Agent chaining for multi-step workflows
- Rate limit retry with backoff
"""
import os
import time
import logging
from smolagents import ToolCallingAgent, LiteLLMModel
from AI.darius.tools import ALL_TOOLS

logging.getLogger("smolagents").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

_MODEL_HEAVY = os.environ.get("DARIUS_MODEL_HEAVY", "anthropic/claude-sonnet-4-6")
_MODEL_LIGHT = os.environ.get("DARIUS_MODEL_LIGHT", "anthropic/claude-haiku-4-5-20251001")
_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

_HEAVY_KEYWORDS = [
    "refactor", "architect", "redesign", "rewrite", "analyze", "review all",
    "optimize", "migrate", "implement", "build", "create", "fix", "debug",
    "components", "pipeline", "system", "integrate",
]


def _select_model(task: str) -> str:
    t = task.lower()
    if any(k in t for k in _HEAVY_KEYWORDS):
        return _MODEL_HEAVY
    return _MODEL_LIGHT


SYSTEM_PROMPT = """You are Darius, an AI orchestration agent built by Melanin Technologies.

You have access to specialist agents (frontend, backend, scaffold, deploy, support, code, file) and direct tools (read_file, write_file, shell, git, mcp).

Strategy — always prefer this order:
1. Use read_file or mcp tools to understand the codebase first
2. Break the task into specific sub-tasks
3. Dispatch each sub-task to the appropriate specialist agent using the dispatch tool
4. Only use write_file or shell directly when no specialist agent fits

For multi-step workflows, execute steps in sequence. Report progress after each step.
Be concise in reasoning. Process one file or sub-task at a time.
"""


def build_agent(task: str = "") -> ToolCallingAgent:
    model_id = _select_model(task)
    model = LiteLLMModel(model_id=model_id, api_key=_API_KEY)
    agent = ToolCallingAgent(
        tools=ALL_TOOLS,
        model=model,
        max_steps=20,
        verbosity_level=0,
    )
    agent.prompt_templates["system_prompt"] = SYSTEM_PROMPT
    return agent


def run_task(task: str, session_id: str = None) -> str:
    """Run a task through Darius and optionally persist the session."""
    from AI.darius.memory import save_turn, load_session

    agent = build_agent(task)

    if session_id:
        history = load_session(session_id)
        if history:
            context = "\n".join(f"[{t['role']}]: {t['content']}" for t in history[-10:])
            task = f"Previous context:\n{context}\n\nCurrent task: {task}"

    for attempt in range(3):
        try:
            result = agent.run(task)
            break
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt < 2:
                time.sleep(60 * (attempt + 1))
                agent = build_agent(task)
            else:
                raise

    if session_id:
        save_turn(session_id, "user", task)
        save_turn(session_id, "assistant", str(result))

    return str(result)


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
    Execute a sequence of agent tasks in order.
    Each task dict: {"agent": "frontend", "task": "...", "project": "..."}
    If agent is "darius", runs directly. Otherwise dispatches to specialist.

    Returns list of results, one per step.
    """
    from AI.darius.memory import save_turn
    import httpx
    import json

    results = []
    urls = {
        "frontend": "http://frontend-agent:8000",
        "backend": "http://backend-agent:8000",
        "scaffold": "http://scaffold-agent:8000",
        "deploy": "http://deploy-agent:8000",
        "support": "http://support-agent:8000",
        "code": "http://code-agent:8000",
        "file": "http://file-agent:8000",
    }

    for i, step in enumerate(tasks):
        agent_name = step.get("agent", "darius").lower()
        task_text = step["task"]
        project = step.get("project", "default")

        if agent_name == "darius":
            result = run_task(task_text, session_id=session_id)
        elif agent_name in urls:
            try:
                r = httpx.post(
                    f"{urls[agent_name]}/task",
                    json={"task": task_text, "project": project},
                    timeout=120,
                )
                r.raise_for_status()
                data = r.json()
                result = data.get("args", {}).get("proposal", json.dumps(data))[:5000]
            except Exception as e:
                result = f"Chain step {i+1} failed ({agent_name}): {e}"
        else:
            result = f"Unknown agent in chain: {agent_name}"

        results.append(result)

        if session_id:
            save_turn(session_id, "user", f"[chain step {i+1}/{len(tasks)}] {task_text}")
            save_turn(session_id, "assistant", result)

    return results
