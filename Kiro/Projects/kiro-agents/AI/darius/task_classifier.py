"""
Task Classifier — Determines task type for evaluation routing.

Types:
  CODE     — Write/modify code, create files, implement features
  QUESTION — Ask for information, recall context, explain something
  DEPLOY   — Deploy, release, infrastructure changes, container ops
  ANALYSIS — Analyze data, review code, audit, investigate

Used by the evaluator to select appropriate scoring criteria per type.
"""
import re
from enum import Enum


class TaskType(Enum):
    CODE = "code"
    QUESTION = "question"
    DEPLOY = "deploy"
    ANALYSIS = "analysis"


# Keyword sets for classification (order matters — first match wins)
_QUESTION_KEYWORDS = frozenset([
    "what is", "what are", "how do", "how does", "explain", "describe",
    "tell me", "show me", "list the", "what model", "what stack",
    "what tools", "who is", "where is", "when did", "why does",
    "can you explain", "what's the", "recall", "remember",
])

_DEPLOY_KEYWORDS = frozenset([
    "deploy", "release", "rollback", "restart", "scale",
    "docker compose", "container", "watchtower", "health check",
    "nginx", "certificate", "dns", "domain", "ci/cd", "pipeline",
    "migrate database", "run migration",
])

_ANALYSIS_KEYWORDS = frozenset([
    "analyze", "review", "audit", "investigate", "compare",
    "check the", "what's wrong", "troubleshoot", "debug",
    "performance", "optimize", "report on", "summarize",
    "evaluate", "assess",
])

_CODE_KEYWORDS = frozenset([
    "create", "implement", "build", "add a", "write",
    "fix the bug", "refactor", "update the code", "add endpoint",
    "new component", "new service", "scaffold", "generate",
    "modify", "change the", "add feature",
])

# Pattern-based classification for stronger signals
_QUESTION_PATTERNS = [
    re.compile(r"^(what|how|why|when|where|who|which|can you|do we|is there)\b", re.IGNORECASE),
    re.compile(r"\?$"),
]

_DEPLOY_PATTERNS = [
    re.compile(r"deploy\s+(to|the|latest)", re.IGNORECASE),
    re.compile(r"docker\s+(compose|restart|stop|build)", re.IGNORECASE),
    re.compile(r"push\s+to\s+(prod|production|staging)", re.IGNORECASE),
]


def classify_task(task: str) -> TaskType:
    """
    Classify a task into one of the four types.
    Uses keyword matching + pattern matching. Fast (no LLM call).
    """
    task_lower = task.lower().strip()

    # Pattern-based (strongest signal)
    for pattern in _QUESTION_PATTERNS:
        if pattern.search(task_lower):
            # Verify it's not a "how to implement X" (which is CODE)
            if any(kw in task_lower for kw in ("implement", "create", "build", "write", "add")):
                break  # Fall through to keyword matching
            return TaskType.QUESTION

    for pattern in _DEPLOY_PATTERNS:
        if pattern.search(task_lower):
            return TaskType.DEPLOY

    # Keyword-based (check in priority order)
    # Questions first (most common misclassification source)
    question_hits = sum(1 for kw in _QUESTION_KEYWORDS if kw in task_lower)
    deploy_hits = sum(1 for kw in _DEPLOY_KEYWORDS if kw in task_lower)
    analysis_hits = sum(1 for kw in _ANALYSIS_KEYWORDS if kw in task_lower)
    code_hits = sum(1 for kw in _CODE_KEYWORDS if kw in task_lower)

    scores = {
        TaskType.QUESTION: question_hits,
        TaskType.DEPLOY: deploy_hits,
        TaskType.ANALYSIS: analysis_hits,
        TaskType.CODE: code_hits,
    }

    # Return highest scoring type (default to CODE if tied/zero)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return TaskType.CODE  # Default: treat as code task

    return best
