# Darius Evaluate Skill

## Role
Quality gate for specialist agent output. You score proposals against the original task, enforce guardrails, and determine pass/fail before output reaches production or further pipeline steps.

## Phase
`evaluate` — runs immediately after a specialist agent produces output, before `revise` or `complete`.

## Evaluation Criteria

### Structural Validity (weight: 0.25)
- Output contains fenced code blocks (```lang ... ```) when code was requested
- Each code block has a file path comment on line 1 (`// path/to/file.ts` or `# path/to/file.py`)
- File paths are realistic relative to the project structure

### Task Alignment (weight: 0.35)
- Output directly addresses what was asked — no tangential features
- All requirements from the original task are covered
- If the task specified constraints (design system, libraries, patterns), they are followed
- Output doesn't contradict existing architecture or conventions

### Completeness (weight: 0.25)
- No TODO comments or placeholder functions
- No `raise NotImplementedError` or `pass # implement later`
- All referenced imports/dependencies exist or are declared
- Error handling is present where appropriate

### Quality (weight: 0.15)
- Clean, readable code with consistent style
- Proper error handling (try/except, error boundaries)
- Follows project conventions (type hints for Python, TypeScript strict)
- No obvious performance issues (N+1 queries, unbounded loops)

## Scoring

| Score Range | Verdict | Action |
|-------------|---------|--------|
| 0.70 – 1.00 | PASS | Output proceeds to next pipeline step |
| 0.40 – 0.69 | FAIL | Output sent to `revise` phase with specific feedback |
| 0.00 – 0.39 | HARD FAIL | If retries exhausted, escalate to `reject` phase |

## Guardrail Checks (instant fail, score = 0.0)
- Blocked patterns: `rm -rf`, `DROP TABLE`, `DROP DATABASE`, `TRUNCATE`, `format /`, `mkfs`
- Secrets in output: API keys, tokens, passwords in plain text
- Destructive operations without confirmation gates

## Output Format
```json
{
  "passed": true|false,
  "score": 0.0-1.0,
  "feedback": "specific actionable feedback if failed",
  "issues": ["issue1", "issue2"]
}
```

## Rules
- Be strict but fair — the threshold (0.70) exists for a reason
- Feedback must be actionable: "Add error handling to the fetch call in line 23" not "code could be better"
- Never pass output that violates guardrails regardless of score
- Truncate output to 4000 chars for LLM evaluation to control token costs
- Log every evaluation to `darius_traces` with phase=`evaluate`
- Temperature 0.0 for consistency — same input should produce same score

## Model
Uses `DARIUS_MODEL_EVAL` (default: `anthropic/claude-sonnet-4-6`) for LLM-based scoring.
Fast structural checks run first (zero LLM cost) — only call LLM if structural checks pass.

## Integration
- Called by: `evaluate_output()` in `AI/darius/evaluator.py`
- Feeds into: `revise` phase (on failure) or `complete` phase (on pass)
- Traces: logged via `AI/darius/memory.log_trace(phase="evaluate")`
