"""
Darius DAG Executor — executes planned steps with parallel support.

Steps with no dependencies run concurrently (ThreadPoolExecutor).
Steps that depend on prior steps wait for their dependencies to complete.
Each step's output is evaluated before being passed to dependents.

Architecture:
  1. Build execution graph from plan steps
  2. Identify parallelizable batches (topological sort by levels)
  3. Execute each batch concurrently
  4. Evaluate outputs, retry on failure
  5. Feed results into dependent steps as context
"""
import os
import json
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

import httpx

logger = logging.getLogger("darius.executor")

_MAX_WORKERS = int(os.environ.get("DARIUS_MAX_PARALLEL", "4"))

# Agent URLs — same as chain_tasks
_AGENT_URLS = {
    "frontend": "http://frontend-agent:8000",
    "backend": "http://backend-agent:8000",
    "scaffold": "http://scaffold-agent:8000",
    "deploy": "http://deploy-agent:8000",
    "support": "http://support-agent:8000",
    "code": "http://code-agent:8000",
    "file": "http://file-agent:8000",
}


def _topological_levels(steps: list[dict]) -> list[list[dict]]:
    """
    Group steps into levels for parallel execution.
    Level 0: no dependencies (run first, in parallel)
    Level 1: depends only on level 0 steps
    ...and so on.
    """
    step_map = {s["id"]: s for s in steps}
    in_degree = {s["id"]: len(s.get("depends_on", [])) for s in steps}
    dependents = defaultdict(list)

    for s in steps:
        for dep in s.get("depends_on", []):
            dependents[dep].append(s["id"])

    levels = []
    remaining = set(in_degree.keys())

    while remaining:
        # Find all steps with in_degree 0 among remaining
        ready = [sid for sid in remaining if in_degree[sid] == 0]
        if not ready:
            # Circular dependency — break by forcing remaining steps
            logger.warning(f"Circular dependency detected in DAG, forcing execution of: {remaining}")
            ready = list(remaining)

        level = [step_map[sid] for sid in ready]
        levels.append(level)

        # Remove ready steps and decrement dependents
        for sid in ready:
            remaining.discard(sid)
            for dep_id in dependents.get(sid, []):
                in_degree[dep_id] -= 1

    return levels


def _execute_step(
    step: dict,
    project: str,
    prior_results: dict[str, str],
    session_id: str = None,
) -> tuple[str, str]:
    """
    Execute a single step. Returns (step_id, result_text).

    If the step depends on prior steps, their results are prepended as context.
    """
    step_id = step["id"]
    agent = step.get("agent", "darius")
    task = step.get("task", "")
    step_project = step.get("project") or project

    # Build context from dependencies
    dep_context = ""
    for dep_id in step.get("depends_on", []):
        if dep_id in prior_results:
            dep_context += f"\n[Result from {dep_id}]:\n{prior_results[dep_id][:2000]}\n"

    if dep_context:
        task = f"Context from prior steps:{dep_context}\n\nYour task: {task}"

    start = time.time()

    if agent == "darius":
        # Execute via Darius's own run_task (import here to avoid circular)
        try:
            from AI.darius.agent import run_task
            result = run_task(task, session_id=session_id)
        except Exception as e:
            result = f"ERROR (darius): {e}"
    elif agent in _AGENT_URLS:
        try:
            r = httpx.post(
                f"{_AGENT_URLS[agent]}/task",
                json={"task": task, "project": step_project},
                timeout=180,
            )
            r.raise_for_status()
            data = r.json()
            result = data.get("args", {}).get("proposal", json.dumps(data))[:8000]
        except Exception as e:
            result = f"ERROR ({agent}): {e}"
    else:
        result = f"ERROR: Unknown agent '{agent}'"

    latency_ms = int((time.time() - start) * 1000)

    # Log execution trace
    try:
        from AI.darius.memory import log_trace
        log_trace(
            task_id=session_id or f"exec-{int(time.time())}",
            phase="execute",
            step_index=int(step_id.split("_")[-1]) if "_" in step_id else 0,
            tool_name=f"agent:{agent}",
            tool_args={"task": task[:500], "project": step_project},
            tool_result=result[:5000],
            latency_ms=latency_ms,
            session_id=session_id,
            status="success" if not result.startswith("ERROR") else "error",
        )
    except Exception:
        pass

    return step_id, result


def execute_dag(
    steps: list[dict],
    project: str = "default",
    session_id: str = None,
    evaluate: bool = True,
) -> dict[str, str]:
    """
    Execute a DAG of steps with parallel support.

    Args:
        steps: List of step dicts from the planner
        project: Default project for steps without explicit project
        session_id: For trace logging and memory
        evaluate: Whether to run evaluation on each step's output

    Returns:
        Dict mapping step_id → result_text
    """
    levels = _topological_levels(steps)
    results: dict[str, str] = {}

    logger.info(f"Executing DAG: {len(steps)} steps in {len(levels)} levels")

    for level_idx, level in enumerate(levels):
        logger.info(f"Level {level_idx}: executing {len(level)} steps in parallel")

        if len(level) == 1:
            # Single step — no thread overhead
            step = level[0]
            step_id, result = _execute_step(step, project, results, session_id)
            results[step_id] = result
        else:
            # Multiple steps — parallel execution
            with ThreadPoolExecutor(max_workers=min(len(level), _MAX_WORKERS)) as executor:
                futures = {
                    executor.submit(_execute_step, step, project, results, session_id): step
                    for step in level
                }
                for future in as_completed(futures):
                    step = futures[future]
                    try:
                        step_id, result = future.result()
                        results[step_id] = result
                    except Exception as e:
                        results[step["id"]] = f"ERROR (executor): {e}"
                        logger.error(f"Step {step['id']} failed: {e}")

        # Evaluate outputs from this level (if enabled)
        if evaluate:
            for step in level:
                step_id = step["id"]
                if step_id in results and not results[step_id].startswith("ERROR"):
                    results[step_id] = _evaluate_step_output(
                        step=step,
                        output=results[step_id],
                        project=project,
                        session_id=session_id,
                    )

    return results


def _evaluate_step_output(
    step: dict,
    output: str,
    project: str,
    session_id: str = None,
) -> str:
    """
    Run evaluation on a step's output. If it fails, retry via the specialist.
    Returns the final (possibly revised) output.
    """
    from AI.darius.evaluator import evaluate_with_retries

    agent = step.get("agent", "darius")
    task = step.get("task", "")
    step_project = step.get("project") or project
    step_index = int(step["id"].split("_")[-1]) if "_" in step["id"] else 0

    def retry_fn(original_task: str, feedback: str) -> str:
        """Re-dispatch to the specialist with evaluation feedback."""
        revision_task = f"{feedback}\n\nOriginal task: {original_task}"

        if agent == "darius":
            from AI.darius.agent import run_task
            return run_task(revision_task, session_id=session_id)
        elif agent in _AGENT_URLS:
            r = httpx.post(
                f"{_AGENT_URLS[agent]}/task",
                json={"task": revision_task, "project": step_project},
                timeout=180,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("args", {}).get("proposal", json.dumps(data))[:8000]
        else:
            return output  # can't retry unknown agent

    final_output, passed = evaluate_with_retries(
        task=task,
        output=output,
        retry_fn=retry_fn,
        task_id=session_id or f"eval-{int(time.time())}",
        step_index=step_index,
        session_id=session_id,
    )

    if not passed:
        # Mark as rejected in result so downstream steps know
        return f"[REJECTED after max retries] {final_output}"

    return final_output


def format_dag_results(results: dict[str, str]) -> str:
    """Format DAG results into a readable summary."""
    lines = []
    for step_id in sorted(results.keys()):
        result = results[step_id]
        status = "❌" if result.startswith("ERROR") or result.startswith("[REJECTED") else "✅"
        preview = result[:200].replace("\n", " ")
        lines.append(f"{status} **{step_id}**: {preview}")
    return "\n\n".join(lines)
