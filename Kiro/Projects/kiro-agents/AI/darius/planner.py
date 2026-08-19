"""
Darius Planner — decomposes tasks into execution DAGs.

The PlannerTool is invoked by the smolagents ToolCallingAgent as the first step
for complex tasks. It uses the light model to plan quickly, then returns a
structured DAG that the execution engine processes.

DAG format:
  [
    {"id": "step_1", "agent": "frontend", "task": "...", "depends_on": []},
    {"id": "step_2", "agent": "backend", "task": "...", "depends_on": []},
    {"id": "step_3", "agent": "darius", "task": "...", "depends_on": ["step_1", "step_2"]},
  ]

Steps with no shared dependencies execute in parallel.
"""
import os
import json
import time
import logging
from smolagents import Tool
from litellm import completion

logger = logging.getLogger("darius.planner")

_MODEL_PLAN = os.environ.get("DARIUS_MODEL_PLAN", "anthropic/claude-sonnet-4-6")
_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Tasks below this word count skip planning (too simple)
_MIN_COMPLEXITY_WORDS = 8

PLANNING_PROMPT = """You are a task planner for a multi-agent system. Your job is to decompose a user task into an execution plan.

Available agents:
- frontend: React/Next.js/TypeScript/Tailwind code generation
- backend: FastAPI/Python API endpoints and logic
- scaffold: Project bootstrapping and setup
- deploy: Docker/K8s deployment operations
- support: Bug diagnosis and fixes
- code: General-purpose code changes
- file: File system operations (read/write/move)
- darius: Complex reasoning, analysis, multi-step coordination

Rules:
1. Output ONLY valid JSON — an array of step objects
2. Each step: {"id": "step_N", "agent": "<agent>", "task": "<specific task>", "depends_on": [<step_ids>]}
3. Steps with empty depends_on can run in parallel
4. Steps that need output from prior steps must declare dependencies
5. Keep tasks atomic — one clear deliverable per step
6. For simple tasks (single agent, single action), return a single step
7. Maximum 8 steps per plan — decompose further only if genuinely needed
8. Use "darius" agent for analysis/research steps that need reasoning

Output format — ONLY this JSON array, no explanation:
[{"id": "step_1", "agent": "frontend", "task": "...", "depends_on": []}]
"""


def _is_complex_task(task: str) -> bool:
    """Determine if a task needs planning or can be executed directly."""
    words = task.split()
    if len(words) < _MIN_COMPLEXITY_WORDS:
        return False
    # Multi-domain signals
    multi_signals = [
        "and then", "after that", "followed by", "also need",
        "frontend and backend", "full stack", "end to end",
        "multiple", "several", "pipeline", "workflow",
    ]
    task_lower = task.lower()
    if any(s in task_lower for s in multi_signals):
        return True
    # Multiple agent keywords
    agent_keywords = {
        "frontend": ["component", "page", "ui", "react", "tailwind", "layout"],
        "backend": ["api", "endpoint", "route", "database", "model"],
        "deploy": ["deploy", "docker", "build", "launch"],
        "scaffold": ["scaffold", "bootstrap", "new project"],
    }
    domains_hit = sum(
        1 for keywords in agent_keywords.values()
        if any(k in task_lower for k in keywords)
    )
    return domains_hit >= 2


def plan_task(task: str, project: str = "default") -> list[dict]:
    """
    Decompose a task into execution steps.
    Returns a DAG (list of steps with dependencies).
    Simple tasks return a single step without calling the LLM.
    Plans are cached in Redis (5-min TTL) to avoid redundant LLM calls on retries.
    """
    if not _is_complex_task(task):
        # Simple task — single step, no planning overhead
        agent = _quick_classify(task)
        return [{"id": "step_1", "agent": agent, "task": task, "depends_on": []}]

    # Check Redis cache for an existing plan
    import hashlib
    plan_cache_key = f"darius:plan:{hashlib.sha256(f'{project}:{task}'.encode()).hexdigest()[:16]}"
    try:
        import redis
        _redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        r = redis.Redis.from_url(_redis_url, decode_responses=True, socket_connect_timeout=2)
        cached_plan = r.get(plan_cache_key)
        if cached_plan:
            logger.info(f"Plan cache hit for task: {task[:50]}")
            return json.loads(cached_plan)
    except Exception:
        r = None

    # Complex task — use LLM to plan
    start = time.time()
    try:
        response = completion(
            model=_MODEL_PLAN,
            api_key=_API_KEY,
            messages=[
                {"role": "system", "content": [
                    {"type": "text", "text": PLANNING_PROMPT, "cache_control": {"type": "ephemeral"}},
                ]},
                {"role": "user", "content": f"Project: {project}\n\nTask: {task}"},
            ],
            max_tokens=2048,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        latency_ms = int((time.time() - start) * 1000)

        # Parse JSON from response (handle markdown fencing)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        steps = json.loads(raw)

        # Validate structure
        if not isinstance(steps, list) or not steps:
            logger.warning("Planner returned invalid structure, falling back to single step")
            return [{"id": "step_1", "agent": "darius", "task": task, "depends_on": []}]

        # Validate each step
        valid_agents = {"frontend", "backend", "scaffold", "deploy", "support", "code", "file", "darius"}
        validated = []
        for i, step in enumerate(steps[:8]):  # cap at 8 steps
            if not isinstance(step, dict):
                continue
            validated.append({
                "id": step.get("id", f"step_{i+1}"),
                "agent": step.get("agent", "darius") if step.get("agent") in valid_agents else "darius",
                "task": step.get("task", task),
                "depends_on": step.get("depends_on", []) if isinstance(step.get("depends_on"), list) else [],
            })

        if not validated:
            return [{"id": "step_1", "agent": "darius", "task": task, "depends_on": []}]

        # Log planning trace
        try:
            from AI.darius.memory import log_trace
            log_trace(
                task_id=f"plan-{int(time.time())}",
                phase="plan",
                tool_name="planner",
                tool_args={"task": task, "project": project},
                tool_result=json.dumps(validated),
                model=_MODEL_PLAN,
                tokens_in=response.usage.prompt_tokens if response.usage else 0,
                tokens_out=response.usage.completion_tokens if response.usage else 0,
                latency_ms=latency_ms,
            )
        except Exception:
            pass

        # Cache the plan (5-min TTL) — avoids re-planning on retries/fallbacks
        if r:
            try:
                r.setex(plan_cache_key, 300, json.dumps(validated))
            except Exception:
                pass

        return validated

    except json.JSONDecodeError as e:
        logger.warning(f"Planner JSON parse error: {e}, falling back to single step")
        return [{"id": "step_1", "agent": "darius", "task": task, "depends_on": []}]
    except Exception as e:
        logger.error(f"Planner error: {e}, falling back to single step")
        return [{"id": "step_1", "agent": "darius", "task": task, "depends_on": []}]


def _quick_classify(task: str) -> str:
    """Fast keyword-based agent classification (no LLM call)."""
    task_lower = task.lower()
    if any(k in task_lower for k in ["component", "page", "ui", "react", "tailwind", "css", "layout", "website"]):
        return "frontend"
    if any(k in task_lower for k in ["api", "endpoint", "route", "fastapi", "model", "database"]):
        return "backend"
    if any(k in task_lower for k in ["deploy", "docker", "build image", "launch"]):
        return "deploy"
    if any(k in task_lower for k in ["scaffold", "bootstrap", "new project", "init"]):
        return "scaffold"
    if any(k in task_lower for k in ["bug", "fix", "broken", "error", "crash"]):
        return "support"
    if any(k in task_lower for k in ["read file", "write file", "move file", "delete file"]):
        return "file"
    return "darius"


# ── smolagents Tool wrapper ───────────────────────────────────────────────────

class PlannerTool(Tool):
    name = "plan_task"
    description = (
        "Decompose a complex task into an execution plan (DAG of steps). "
        "Call this FIRST for multi-step or multi-agent tasks. "
        "Returns a JSON array of steps with agent assignments and dependencies. "
        "Simple single-agent tasks don't need this — execute them directly."
    )
    inputs = {
        "task": {"type": "string", "description": "The full task to decompose into steps"},
        "project": {"type": "string", "description": "Project name for context", "nullable": True},
    }
    output_type = "string"

    def forward(self, task: str, project: str = "default") -> str:
        steps = plan_task(task, project)
        return json.dumps(steps, indent=2)
