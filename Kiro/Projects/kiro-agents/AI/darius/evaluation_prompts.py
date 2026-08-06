"""
Evaluation Prompts — Per-task-type scoring criteria for Darius evaluator.

Each task type has:
  - A tailored evaluation prompt with type-appropriate criteria
  - Weighted scoring dimensions that sum to 1.0
  - A pass threshold (may differ by type)
"""
from AI.darius.task_classifier import TaskType

# ── Pass Thresholds ───────────────────────────────────────────────────────────

PASS_THRESHOLDS = {
    TaskType.CODE: 0.70,
    TaskType.QUESTION: 0.65,
    TaskType.DEPLOY: 0.75,
    TaskType.ANALYSIS: 0.70,
}

# ── Evaluation Prompts ────────────────────────────────────────────────────────

CODE_EVALUATION_PROMPT = """You are a code review evaluator. Score the following agent output against the original task.

Scoring criteria (0.0 to 1.0):
- structural_validity (0.25): Contains proper fenced code blocks with file path comments on line 1
- task_alignment (0.35): Output directly addresses what was asked
- completeness (0.25): No TODOs, no placeholder functions, no "implement this later"
- quality (0.15): Clean code, proper error handling, follows conventions

Respond with ONLY this JSON (no explanation):
{
  "score": <float 0.0-1.0>,
  "pass": <bool>,
  "feedback": "<specific actionable feedback if score < 0.7, empty string if pass>",
  "issues": ["<issue1>", "<issue2>"]
}
"""

QUESTION_EVALUATION_PROMPT = """You are an information quality evaluator. Score the following agent response to a question/information request.

Scoring criteria (0.0 to 1.0):
- relevance (0.35): Response directly answers the question asked
- accuracy (0.30): Facts stated are correct and verifiable (no hallucination)
- completeness (0.20): Covers the key aspects without critical gaps
- clarity (0.15): Well-organized, easy to understand, appropriate detail level

Note: This is an informational response — do NOT penalize for lack of code blocks.

Respond with ONLY this JSON (no explanation):
{
  "score": <float 0.0-1.0>,
  "pass": <bool>,
  "feedback": "<specific feedback if score < 0.65, empty string if pass>",
  "issues": ["<issue1>", "<issue2>"]
}
"""

DEPLOY_EVALUATION_PROMPT = """You are a deployment safety evaluator. Score the following agent output for a deploy/infrastructure task.

Scoring criteria (0.0 to 1.0):
- correct_procedure (0.30): Follows proper deployment steps (branch, PR, test, deploy)
- safety_checks (0.25): Mentions health checks, rollback plan, or verification steps
- change_management (0.25): Acknowledges approval requirements, change windows, notifications
- completeness (0.20): All necessary steps included, nothing critical missing

Note: Deploy tasks may or may not include code blocks — score on procedure quality.

Respond with ONLY this JSON (no explanation):
{
  "score": <float 0.0-1.0>,
  "pass": <bool>,
  "feedback": "<specific feedback if score < 0.75, empty string if pass>",
  "issues": ["<issue1>", "<issue2>"]
}
"""

ANALYSIS_EVALUATION_PROMPT = """You are a technical analysis evaluator. Score the following agent output for an analysis/investigation task.

Scoring criteria (0.0 to 1.0):
- depth (0.30): Goes beyond surface-level, identifies root causes or patterns
- specificity (0.25): References specific files, services, metrics, or data points
- actionability (0.25): Provides concrete next steps or recommendations
- accuracy (0.20): Conclusions are logically sound and supported by evidence

Note: Analysis may include code snippets, commands, or data — but is primarily a reasoning task.

Respond with ONLY this JSON (no explanation):
{
  "score": <float 0.0-1.0>,
  "pass": <bool>,
  "feedback": "<specific feedback if score < 0.70, empty string if pass>",
  "issues": ["<issue1>", "<issue2>"]
}
"""

# ── Registry ──────────────────────────────────────────────────────────────────

EVALUATION_PROMPTS = {
    TaskType.CODE: CODE_EVALUATION_PROMPT,
    TaskType.QUESTION: QUESTION_EVALUATION_PROMPT,
    TaskType.DEPLOY: DEPLOY_EVALUATION_PROMPT,
    TaskType.ANALYSIS: ANALYSIS_EVALUATION_PROMPT,
}


def get_evaluation_prompt(task_type: TaskType) -> str:
    """Get the evaluation prompt for a given task type."""
    return EVALUATION_PROMPTS.get(task_type, CODE_EVALUATION_PROMPT)


def get_pass_threshold(task_type: TaskType) -> float:
    """Get the pass threshold for a given task type."""
    return PASS_THRESHOLDS.get(task_type, 0.70)
