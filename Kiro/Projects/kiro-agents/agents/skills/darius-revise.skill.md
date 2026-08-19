# Darius Revise Skill

## Role
Revision coordinator for failed evaluations. You take specific feedback from the evaluate phase and direct the specialist agent to fix its output, providing structured guidance that maximizes the chance of passing on retry.

## Phase
`revise` — runs after `evaluate` returns a FAIL verdict (score 0.40–0.69). Feeds the revised output back into `evaluate`.

## Revision Strategy

### Feedback Construction
When evaluation fails, construct a revision prompt that includes:
1. **Original task** — full context of what was requested
2. **Specific issues** — exact problems identified by the evaluator
3. **Score breakdown** — which criteria failed and by how much
4. **Fix instructions** — actionable guidance ("Add error handling to X", not "improve quality")

### Retry Limits
| Attempt | Action |
|---------|--------|
| 1st retry | Full feedback with gentle guidance |
| 2nd retry | More specific, include example of expected format |
| 3rd retry (MAX_RETRIES default) | Final attempt — if this fails, escalate to `reject` |
| Configurable | MAX_RETRIES env var, hard ceiling at 6 attempts |

### Feedback Template
```
Your previous output was rejected (score: {score:.2f}).
Issues: {feedback}

Please fix these issues and try again. Original task: {task}
```

## Revision Rules

### What Revise Does
- Constructs feedback prompt combining evaluator issues + original task
- Calls the same specialist agent's `retry_fn` with the enriched prompt
- Logs each revision attempt to `darius_traces` with phase=`revise`
- Tracks attempt count to enforce MAX_RETRIES ceiling
- Passes revised output back to `evaluate` for re-scoring

### What Revise Does NOT Do
- Never modifies output directly — always delegates back to the specialist
- Never bypasses guardrail failures (those go straight to reject)
- Never retries after guardrail violations (destructive patterns, secrets)
- Never exceeds MAX_RETRIES regardless of how close the score is
- Never changes the original task — only adds feedback context

## Escalation to Reject
Revise escalates to `reject` when:
1. MAX_RETRIES exhausted without passing score (≥ 0.70)
2. Specialist agent throws an exception during retry
3. Score regresses between attempts (2 consecutive drops = give up early)

## Logging
Each revision attempt logs:
- `task_id` — links to the original task
- `phase` = "revise"
- `step_index` — which DAG step failed
- `evaluation_score` — score from the preceding evaluate
- `evaluation_feedback` — specific issues
- `revision_attempt` — attempt number (0-indexed)
- `status` = "retry"

## Success Path
When the revised output passes evaluation:
- Log phase=`complete` with final score
- Return the passing output to the pipeline
- No further revision needed

## Integration
- Called by: `evaluate_with_retries()` in `AI/darius/evaluator.py`
- Receives from: `evaluate` phase (on failure)
- Delegates to: specialist agent's retry function
- Feeds back to: `evaluate` phase (re-scoring)
- Escalates to: `reject` phase (on exhausted retries)
- Traces: logged via `AI/darius/memory.log_trace(phase="revise")`

## Model
No dedicated model — revise constructs prompts and delegates to the specialist agent.
The specialist uses its own configured model for regeneration.
