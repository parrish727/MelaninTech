"""
Darius Evaluator — scores specialist agent output and triggers revision loops.

Evaluation criteria:
  1. Structural validity — contains proper code blocks with file paths
  2. Task alignment — output addresses the requested task
  3. Guardrail compliance — no blocked patterns
  4. Completeness — doesn't leave TODOs or placeholder functions

Retry policy:
  - Max retries: MAX_RETRIES (default 3, configurable up to 6)
  - On each failure: provides specific feedback to the specialist for revision
  - On final failure: rejects task and notifies CEO via Slack

All evaluation passes are logged to darius_traces for training data.
"""
import os
import re
import json
import time
import logging
from smolagents import Tool
from litellm import completion

logger = logging.getLogger("darius.evaluator")

_MODEL_EVAL = os.environ.get("DARIUS_MODEL_EVAL", "anthropic/claude-sonnet-4-6")
_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
_SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")
_SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

# Retry configuration — hard ceiling at 6, default 3
MAX_RETRIES = min(int(os.environ.get("DARIUS_MAX_EVAL_RETRIES", "3")), 6)

# Guardrail patterns (same as base_agent.py)
_BLOCKED_PATTERNS = ["rm -rf", "DROP TABLE", "DROP DATABASE", "TRUNCATE", "format /", "mkfs"]

# Minimum score to pass — now task-type-aware
from AI.darius.task_classifier import classify_task, TaskType
from AI.darius.evaluation_prompts import get_evaluation_prompt, get_pass_threshold, PASS_THRESHOLDS

_PASS_THRESHOLD = 0.7  # Default fallback


def _check_structural_validity(output: str) -> tuple[bool, list[str]]:
    """Fast pre-check — does the output have code blocks with file paths?"""
    issues = []

    # Check for code blocks
    code_blocks = re.findall(r"```[\w]*\n(.*?)```", output, re.DOTALL)
    if not code_blocks:
        # Some outputs are valid text responses (analysis, explanations)
        # Only flag if the task likely expected code
        issues.append("No code blocks found in output")
        return False, issues

    # Check file path comments on first line of each code block
    path_patterns = [r"^(//|#)\s*\S+\.\w+", r"^(//|#)\s*\S+/\S+"]
    blocks_with_paths = 0
    for block in code_blocks:
        first_line = block.strip().split("\n")[0] if block.strip() else ""
        if any(re.match(p, first_line) for p in path_patterns):
            blocks_with_paths += 1

    if code_blocks and blocks_with_paths == 0:
        issues.append("Code blocks missing file path comments on first line")

    return len(issues) == 0, issues


def _check_guardrails(output: str) -> tuple[bool, list[str]]:
    """Check for blocked patterns."""
    issues = []
    for pattern in _BLOCKED_PATTERNS:
        if pattern.lower() in output.lower():
            issues.append(f"Blocked pattern detected: '{pattern}'")
    return len(issues) == 0, issues


def _check_completeness(output: str) -> tuple[bool, list[str]]:
    """Check for TODO/placeholder patterns."""
    issues = []
    todo_patterns = [
        r"#\s*TODO",
        r"//\s*TODO",
        r"pass\s*#\s*implement",
        r"raise NotImplementedError",
        r"\.\.\.\s*#",
        r"placeholder",
        r"implement this later",
        r"add implementation here",
    ]
    for pattern in todo_patterns:
        matches = re.findall(pattern, output, re.IGNORECASE)
        if matches:
            issues.append(f"Incomplete implementation: found '{matches[0]}'")
            break  # one is enough

    return len(issues) == 0, issues


def evaluate_output(
    task: str,
    output: str,
    task_id: str = None,
    step_index: int = 0,
    attempt: int = 0,
) -> dict:
    """
    Evaluate specialist agent output.

    Returns:
        {
            "passed": bool,
            "score": float,
            "feedback": str,
            "issues": list[str],
        }
    """
    # Fast structural checks (no LLM cost)
    guardrail_ok, guardrail_issues = _check_guardrails(output)
    if not guardrail_ok:
        result = {
            "passed": False,
            "score": 0.0,
            "feedback": f"Guardrail violation: {'; '.join(guardrail_issues)}",
            "issues": guardrail_issues,
        }
        _log_evaluation(task_id, step_index, attempt, result)
        return result

    # Classify task type — only apply structural checks to CODE tasks
    task_type = classify_task(task)
    threshold = get_pass_threshold(task_type)

    struct_ok, struct_issues = True, []
    complete_ok, complete_issues = True, []

    if task_type == TaskType.CODE:
        struct_ok, struct_issues = _check_structural_validity(output)
        complete_ok, complete_issues = _check_completeness(output)

    all_issues = struct_issues + complete_issues

    # LLM evaluation with task-type-appropriate prompt
    if struct_ok and complete_ok:
        llm_result = _llm_evaluate(task, output)
        if llm_result:
            score = llm_result.get("score", 0.5)
            result = {
                "passed": score >= threshold,
                "score": score,
                "feedback": llm_result.get("feedback", ""),
                "issues": llm_result.get("issues", []),
            }
            _log_evaluation(task_id, step_index, attempt, result)
            return result

    # Fast checks found issues — score accordingly
    # Structural: 0.25 weight, completeness: 0.25 weight
    score = 1.0
    if not struct_ok:
        score -= 0.25
    if not complete_ok:
        score -= 0.25

    passed = score >= _PASS_THRESHOLD and not all_issues
    feedback = "; ".join(all_issues) if all_issues else ""

    result = {
        "passed": passed,
        "score": score,
        "feedback": feedback,
        "issues": all_issues,
    }
    _log_evaluation(task_id, step_index, attempt, result)
    return result


def _llm_evaluate(task: str, output: str) -> dict | None:
    """Use the light model to evaluate task alignment and quality."""
    try:
        # Truncate output to save tokens — evaluation doesn't need full file contents
        truncated_output = output[:4000] if len(output) > 4000 else output

        response = completion(
            model=_MODEL_EVAL,
            api_key=_API_KEY,
            messages=[
                {"role": "system", "content": get_evaluation_prompt(classify_task(task))},
                {"role": "user", "content": f"TASK:\n{task}\n\nAGENT OUTPUT:\n{truncated_output}"},
            ],
            max_tokens=512,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()

        # Parse JSON (handle markdown fencing)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        return json.loads(raw)
    except Exception as e:
        logger.warning(f"LLM evaluation failed: {e}")
        return None


def _log_evaluation(task_id: str, step_index: int, attempt: int, result: dict):
    """Log evaluation to traces."""
    if not task_id:
        return
    try:
        from AI.darius.memory import log_trace
        log_trace(
            task_id=task_id,
            phase="evaluate",
            step_index=step_index,
            evaluation_score=result["score"],
            evaluation_feedback=result["feedback"],
            revision_attempt=attempt,
            status="pass" if result["passed"] else "fail",
        )
    except Exception:
        pass


def notify_rejection(task: str, task_id: str, step_index: int, attempts: int, final_feedback: str):
    """Notify CEO on Slack that a task was rejected after max retries."""
    if not _SLACK_TOKEN or not _SLACK_CHANNEL:
        logger.warning("Cannot notify rejection — no Slack credentials")
        return

    try:
        import httpx
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚫 Darius Task Rejected"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Task:* {task[:200]}\n"
                        f"*Task ID:* `{task_id}`\n"
                        f"*Step:* {step_index}\n"
                        f"*Attempts:* {attempts}/{MAX_RETRIES}\n"
                        f"*Reason:* {final_feedback[:500]}"
                    ),
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Agent output failed quality evaluation after maximum retries. Manual intervention required.",
                    }
                ],
            },
        ]

        httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {_SLACK_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "channel": _SLACK_CHANNEL,
                "text": f"🚫 Darius rejected task after {attempts} attempts: {task[:100]}",
                "blocks": blocks,
            },
            timeout=10,
        )
        logger.info(f"Rejection notification sent for task {task_id}")
    except Exception as e:
        logger.error(f"Failed to send rejection notification: {e}")


def evaluate_with_retries(
    task: str,
    output: str,
    retry_fn,
    task_id: str = None,
    step_index: int = 0,
    session_id: str = None,
) -> tuple[str, bool]:
    """
    Evaluate output and retry if it fails.

    Args:
        task: The original task
        output: The specialist's current output
        retry_fn: Callable(task, feedback) -> new_output
        task_id: For trace logging
        step_index: DAG step index
        session_id: For trace logging

    Returns:
        (final_output, passed) — the best output we got and whether it passed
    """
    current_output = output

    for attempt in range(MAX_RETRIES):
        result = evaluate_output(
            task=task,
            output=current_output,
            task_id=task_id,
            step_index=step_index,
            attempt=attempt,
        )

        if result["passed"]:
            # Log success
            if task_id:
                try:
                    from AI.darius.memory import log_trace
                    log_trace(
                        task_id=task_id,
                        phase="complete",
                        step_index=step_index,
                        evaluation_score=result["score"],
                        revision_attempt=attempt,
                        status="pass",
                        session_id=session_id,
                    )
                except Exception:
                    pass
            return current_output, True

        # Failed — log revision attempt
        if task_id:
            try:
                from AI.darius.memory import log_trace
                log_trace(
                    task_id=task_id,
                    phase="revise",
                    step_index=step_index,
                    evaluation_score=result["score"],
                    evaluation_feedback=result["feedback"],
                    revision_attempt=attempt,
                    status="retry",
                    session_id=session_id,
                )
            except Exception:
                pass

        # If this is the last attempt, don't retry
        if attempt == MAX_RETRIES - 1:
            break

        # Retry with feedback
        feedback = (
            f"Your previous output was rejected (score: {result['score']:.2f}). "
            f"Issues: {result['feedback']}\n\n"
            f"Please fix these issues and try again. Original task: {task}"
        )
        try:
            current_output = retry_fn(task, feedback)
        except Exception as e:
            logger.error(f"Retry {attempt + 1} failed with exception: {e}")
            break

    # All retries exhausted — reject and notify
    final_feedback = result.get("feedback", "Unknown evaluation failure")

    if task_id:
        try:
            from AI.darius.memory import log_trace
            log_trace(
                task_id=task_id,
                phase="reject",
                step_index=step_index,
                evaluation_score=result["score"],
                evaluation_feedback=final_feedback,
                revision_attempt=MAX_RETRIES,
                status="rejected",
                session_id=session_id,
            )
        except Exception:
            pass

    # Notify Slack
    notify_rejection(task, task_id or "unknown", step_index, MAX_RETRIES, final_feedback)

    return current_output, False


# ── smolagents Tool wrapper ───────────────────────────────────────────────────

class EvaluatorTool(Tool):
    name = "evaluate_output"
    description = (
        "Evaluate the quality of an agent's output against the original task. "
        "Returns a score (0.0-1.0), pass/fail, and actionable feedback. "
        "Use this after receiving output from a specialist agent to verify quality."
    )
    inputs = {
        "task": {"type": "string", "description": "The original task that was requested"},
        "output": {"type": "string", "description": "The agent output to evaluate"},
    }
    output_type = "string"

    def forward(self, task: str, output: str) -> str:
        result = evaluate_output(task, output)
        return json.dumps(result, indent=2)
