"""
Darius FastAPI server — receives tasks from the orchestrator router.
Endpoints:
  POST /task          — single task execution
  POST /chain         — multi-step workflow execution
  GET  /health        — health check
  GET  /status        — dashboard: sessions, recent activity
"""
import os
import uvicorn
from fastapi import FastAPI
from AI.darius.agent import run_task, chain_tasks, run_template
from AI.darius.memory import list_sessions, load_session

# Initialize distributed tracing
try:
    from integrations.tracing import init_tracing, traced, span, get_trace_id, record_llm_call
    init_tracing("darius", version="3.0.0")
except Exception:
    # Graceful degradation — tracing is non-critical
    def traced(name=None, attributes=None):
        def decorator(func):
            return func
        return decorator

    def get_trace_id():
        return "no-trace"

    def record_llm_call(*a, **kw):
        pass

app = FastAPI(title="Darius Agent")


@app.post("/task")
@traced("darius.task", attributes={"component": "darius"})
def task(body: dict):
    task_text = body["task"]
    project = body.get("project", "default")
    session_id = body.get("session_id", project)
    model_source = body.get("model_source")  # "local" for Ollama, None for default (Claude)
    model_override = body.get("model_override")  # "light" = Haiku, "heavy" = Sonnet/Opus

    result = run_task(task_text, session_id=session_id, model_source=model_source, model_override=model_override)

    # Determine which model was actually used for the response metadata
    if model_source == "local":
        model_used = "local/ollama"
    elif model_override == "light":
        model_used = "claude-haiku"
    else:
        model_used = "claude-sonnet-4-6"

    return {
        "agent": "DariusAgent",
        "model": model_used,
        "description": f"Darius completed: {task_text[:80]}",
        "action": "code",
        "args": {
            "task": task_text,
            "project": project,
            "proposal": result,
        },
    }


@app.post("/chain")
def chain(body: dict):
    """Execute a multi-step workflow.
    Body: {"tasks": [{"agent": "frontend", "task": "...", "project": "..."}], "session_id": "..."}
    """
    tasks = body.get("tasks", [])
    session_id = body.get("session_id", "chain")

    if not tasks:
        return {"error": "No tasks provided"}

    results = chain_tasks(tasks, session_id=session_id)

    return {
        "agent": "DariusAgent",
        "action": "chain",
        "steps": len(tasks),
        "results": results,
    }


@app.get("/health")
def health():
    return {"status": "ok", "agent": "DariusAgent", "version": "2.0"}


@app.post("/task/delta")
def task_delta(body: dict):
    """
    Execute a task using the DeltaExecutor (v3 engine).
    Same interface as /task but uses delta context management.
    ~70-85% fewer tokens than the smolagents /task endpoint.

    Body: {"task": "...", "project": "...", "session_id": "...", "model": "..."}
    Returns: {"agent": "DariusAgent", "engine": "delta", "result": {...}}
    """
    from AI.darius.swarm.executor import DeltaExecutor
    from AI.darius.context import build_context

    task_text = body["task"]
    project = body.get("project", "default")
    session_id = body.get("session_id", project)
    model = body.get("model")  # optional: override model selection

    # Build context from session history (if available)
    context = ""
    try:
        context = build_context(session_id, task_text) or ""
    except Exception:
        pass

    # Execute with DeltaExecutor
    executor = DeltaExecutor(task_id=session_id, model=model)
    result = executor.run(task=task_text, context=context)

    return {
        "agent": "DariusAgent",
        "engine": "delta",
        "model": result.get("model"),
        "task_id": result.get("task_id"),
        "step_count": result.get("step_count"),
        "token_usage": result.get("token_usage"),
        "latency_ms": result.get("latency_ms"),
        "args": {
            "task": task_text,
            "project": project,
            "proposal": result.get("final_output", ""),
        },
    }


@app.post("/task/swarm")
def task_swarm(body: dict):
    """
    Execute a complex task using the Agent Swarm (v3 engine).
    Decomposes into parallel specialist agents with shared memory coordination.
    Best for multi-domain tasks that benefit from parallel execution.

    Body: {"task": "...", "project": "...", "session_id": "..."}
    Returns: {"agent": "DariusAgent", "engine": "swarm", "result": {...}}
    """
    from AI.darius.swarm.swarm import AgentSwarm
    from AI.darius.context import build_context

    task_text = body["task"]
    project = body.get("project", "default")
    session_id = body.get("session_id", project)

    # Build context
    context = ""
    try:
        context = build_context(session_id, task_text) or ""
    except Exception:
        pass

    # Execute swarm
    swarm = AgentSwarm(task_id=session_id)
    result = swarm.execute(task=task_text, context=context)

    # Record for adaptive selection
    try:
        from AI.darius.swarm.selector import record_execution
        token_usage = result.get("token_usage", {})
        record_execution(
            task=task_text,
            engine="swarm",
            success=all(a.get("status") == "complete" for a in result.get("agents", [])),
            tokens=token_usage.get("input", 0) + token_usage.get("output", 0),
            latency_ms=result.get("latency_ms", 0),
            cost=token_usage.get("cost", 0),
        )
    except Exception:
        pass

    return {
        "agent": "DariusAgent",
        "engine": "swarm",
        "task_id": result.get("task_id"),
        "agent_count": result.get("agent_count"),
        "wave_count": result.get("wave_count"),
        "token_usage": result.get("token_usage"),
        "latency_ms": result.get("latency_ms"),
        "agents": result.get("agents"),
        "args": {
            "task": task_text,
            "project": project,
            "proposal": result.get("final_output", ""),
        },
    }


@app.post("/task/auto")
def task_auto(body: dict):
    """
    Smart task routing — automatically selects the best engine based on
    historical performance data for similar task types.

    Body: {"task": "...", "project": "...", "session_id": "..."}
    """
    from AI.darius.swarm.selector import select_engine, classify_task

    task_text = body["task"]
    project = body.get("project", "default")
    session_id = body.get("session_id", project)
    classification = classify_task(task_text)

    # Fast path: simple questions, status checks, and SRE diagnostics
    # that need live data + reasoning but NOT multi-step execution
    is_fast = classification in ("simple", "analysis") or any(
        k in task_text.lower() for k in [
            "why is", "what is", "check", "status", "is it", "show me", "explain",
            "why", "how many", "how come", "what are", "which", "tell me", "list",
            "is there", "are there", "can you", "do we", "does", "should",
            "what happened", "when did", "where is", "who",
        ]
    )

    if is_fast:
        # Single-shot completion with the context already in the task — fast, no planning overhead
        import time as _t
        from litellm import completion as _completion
        import os

        start = _t.time()
        _api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        _model = os.environ.get("DARIUS_MODEL", "anthropic/claude-sonnet-4-6")

        system = (
            "You are Darius, the AI operations brain for Melanin Technologies. "
            "You have LIVE infrastructure access — the data in the user's message is REAL and CURRENT (gathered from Docker and PostgreSQL by the HUD). "
            "Answer directly using that data. State the cause and the fix. "
            "If something is down, explain WHY based on the container status shown. "
            "If action is needed, state exactly what command or step resolves it. "
            "Be concise, authoritative, and specific. Never ask the user for data that's already in the message."
        )

        try:
            resp = _completion(
                model=_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": task_text},
                ],
                api_key=_api_key,
                max_tokens=2048,
            )
            result_text = resp.choices[0].message.content.strip()
            latency = int((_t.time() - start) * 1000)

            return {
                "agent": "DariusAgent",
                "engine": "fast",
                "model": _model,
                "latency_ms": latency,
                "args": {"task": task_text, "project": project, "proposal": result_text},
            }
        except Exception as e:
            pass  # Fall through to full engine

    # Full engine routing for complex tasks
    engine = select_engine(task_text)

    # Route to the selected engine
    if engine == "swarm":
        return task_swarm(body)
    elif engine == "delta":
        return task_delta(body)
    else:
        return task(body)


@app.post("/improve")
def improve(body: dict = None):
    """
    Run the self-improvement cycle:
    1. Analyze traces for patterns
    2. Generate refinement proposals
    3. Return insights + proposals (never auto-applies)

    Body (optional): {"days": 7, "post_to_slack": true}
    """
    from AI.darius.swarm.analyzer import analyze
    from AI.darius.swarm.refiner import SkillRefiner
    from AI.darius.swarm.selector import get_all_performance

    body = body or {}
    days = body.get("days", 7)
    post_to_slack = body.get("post_to_slack", True)

    # 1. Analyze
    insights = analyze(days=days)

    # 2. Refine
    refiner = SkillRefiner()
    proposals = refiner.refine(insights)

    # 3. Get engine performance
    engine_perf = get_all_performance()

    # 4. Build report
    report = {
        "analyzed_at": insights.get("analyzed_at"),
        "period_days": days,
        "summary": insights.get("summary"),
        "recommendations": insights.get("recommendations"),
        "proposals": proposals,
        "engine_performance": engine_perf,
    }

    # 5. Post to Slack if requested
    if post_to_slack:
        _post_improvement_report(report, refiner.format_proposals())

    return report


def _post_improvement_report(report: dict, proposals_text: str):
    """Post improvement cycle results to Slack."""
    import httpx as _hx

    slack_token = os.environ.get("SLACK_BOT_TOKEN", "")
    slack_channel = os.environ.get("SLACK_CHANNEL_ID", "")
    if not slack_token or not slack_channel:
        return

    summary = report.get("summary", {})
    recs = report.get("recommendations", [])

    text = f"""🔄 *Darius Self-Improvement Cycle — {report.get('period_days', 7)}d Analysis*

*Summary:*
• Executions: {summary.get('total_executions', 0)} ({summary.get('success_rate', 0)}% success)
• Avg latency: {summary.get('avg_latency_ms', 0)}ms
• Total tokens: {summary.get('total_tokens', 0):,}

*Recommendations:*
{chr(10).join(f'• {r}' for r in recs[:5])}

*Refinement Proposals:* {len(report.get('proposals', []))}
{proposals_text[:800] if proposals_text else 'None generated.'}"""

    try:
        _hx.post("https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {slack_token}", "Content-Type": "application/json"},
            json={"channel": slack_channel, "text": text},
            timeout=10)
    except Exception:
        pass


@app.post("/chat")
def chat(body: dict):
    """
    Lightweight chat endpoint for HUD — direct litellm.completion().
    No smolagents, no tool calling, no DAG planning.
    Uses local models (Ollama) first, falls back to Claude on failure.

    Body: {"message": "...", "context": "...", "session_id": "..."}
    Returns: {"reply": "...", "model": "...", "latency_ms": ...}
    """
    import os
    import time
    import httpx
    from litellm import completion

    message = body.get("message", body.get("task", ""))
    context = body.get("context", "")
    session_id = body.get("session_id", "hud-chat")

    OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
    LOCAL_LIGHT = os.environ.get("DARIUS_LOCAL_LIGHT", "ollama/qwen3:14b")
    LOCAL_HEAVY = os.environ.get("DARIUS_LOCAL_HEAVY", "ollama/mistral-small:24b")
    CLAUDE_LIGHT = "anthropic/claude-haiku-4-5-20251001"
    API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

    # Determine if heavy or light based on context length
    is_heavy = len(message) > 200 or any(k in message.lower() for k in ["analyze", "review", "explain", "compare"])

    system_prompt = (
        "You are Darius, the AI operations intelligence layer for Melanin Technologies, embedded in the HUD (internal monitoring dashboard). "
        "You HAVE access to live infrastructure data — it is provided to you in the context below. "
        "You can see container status, service health, ticket queues, LLM traces, governance policies, contracts, and more based on what tab the user is viewing. "
        "You are NOT a generic chatbot with no system access — you are the brain behind a fully autonomous agent swarm that builds, deploys, monitors, and maintains Melanin Tech's infrastructure. "
        "\n\n"
        "Rules:\n"
        "- Answer based on the LIVE DATA in your context — never say you can't access systems\n"
        "- Be direct. Lead with the answer, then supporting detail.\n"
        "- Use specific numbers, container names, and status values from the context\n"
        "- If the context doesn't contain what's needed, say what specific data is missing — don't give generic troubleshooting steps\n"
        "- You can recommend actions, create tickets, and escalate to Slack\n"
        "- Speak as the CTO's technical right hand, not as a helpdesk\n\n"
    )
    if context:
        system_prompt += f"--- LIVE SYSTEM DATA ---\n{context}\n--- END LIVE DATA ---\n\n"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]

    start = time.time()
    model_used = None
    reply = None

    # Try local model first (Ollama) — 10s timeout, fall back to Claude if slow/unavailable
    try:
        ollama_health = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        if ollama_health.status_code == 200:
            # Check if a model is actually loaded (warm) — skip if cold
            try:
                ps_resp = httpx.get(f"{OLLAMA_URL}/api/ps", timeout=3)
                running = ps_resp.json().get("models", [])
                if not running:
                    raise Exception("No model loaded")
            except Exception:
                raise Exception("Ollama cold")

            local_model = LOCAL_HEAVY if is_heavy else LOCAL_LIGHT
            response = completion(
                model=local_model,
                messages=messages,
                api_base=OLLAMA_URL,
                api_key="ollama",
                max_tokens=1024,
                temperature=0.3,
                timeout=10,
            )
            reply = response.choices[0].message.content
            if reply and reply.strip():
                reply = reply.strip()
                model_used = local_model.replace("ollama/", "")
    except Exception:
        pass  # Fall through to Claude

    # Fallback to Claude
    if reply is None:
        try:
            response = completion(
                model=CLAUDE_LIGHT,
                messages=messages,
                api_key=API_KEY,
                max_tokens=1024,
                temperature=0.3,
            )
            reply = response.choices[0].message.content.strip()
            model_used = "claude-haiku"
        except Exception as e:
            reply = f"Unable to process: {str(e)[:200]}"
            model_used = "error"

    latency_ms = int((time.time() - start) * 1000)

    # Log trace
    try:
        from AI.darius.memory import log_trace
        log_trace(
            task_id=f"chat-{int(time.time())}",
            phase="complete",
            session_id=session_id,
            tool_name="chat",
            tool_args={"message": message[:200]},
            tool_result=reply[:2000],
            model=model_used,
            latency_ms=latency_ms,
            status="success" if model_used != "error" else "error",
        )
    except Exception:
        pass

    return {"reply": reply, "model": model_used, "latency_ms": latency_ms}


@app.post("/template")
def template(body: dict):
    """Execute a YAML workflow template.
    Body: {"trigger": "deploy-website", "params": {"project": "melanin-tech-website"}}
    """
    trigger = body.get("trigger", "")
    params = body.get("params", {})

    if not trigger:
        return {"error": "No trigger provided"}

    results = run_template(trigger, params, session_id=body.get("session_id"))

    return {
        "agent": "DariusAgent",
        "action": "template",
        "template": trigger,
        "steps": len(results),
        "results": results,
    }


@app.get("/status")
def status():
    """Dashboard: list sessions and recent activity."""
    sessions = list_sessions()
    recent = []
    for sid in sessions[-5:]:  # last 5 sessions
        turns = load_session(sid)
        recent.append({
            "session_id": sid,
            "turns": len(turns),
            "last_task": next((t["content"][:100] for t in reversed(turns) if t["role"] == "user"), ""),
        })

    return {
        "agent": "DariusAgent",
        "total_sessions": len(sessions),
        "recent_sessions": recent,
    }


# ── Start Autonomous Heartbeat on Server Startup ──────────────────────────────
from AI.darius.swarm.autonomous import start as _start_autonomous
_start_autonomous()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
