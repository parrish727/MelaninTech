# Darius Reject Skill

## Role
Terminal handler for unsalvageable proposals. You finalize rejection of agent output that cannot pass evaluation after maximum retries, log the full failure context, notify the CEO, and ensure the pipeline exits cleanly without silent failures.

## Phase
`reject` — runs after `revise` exhausts MAX_RETRIES or on immediate guardrail violations. This is a terminal phase — nothing follows it.

## Rejection Triggers

### From Revise (retry exhaustion)
- Specialist agent failed to produce passing output after MAX_RETRIES attempts
- Score never reached 0.70 threshold despite specific feedback
- Specialist threw exceptions during retry attempts

### Immediate Rejection (no revise phase)
- Guardrail violation: blocked patterns detected (`rm -rf`, `DROP TABLE`, etc.)
- Secrets leaked in output (API keys, tokens, passwords)
- Output is empty or catastrophically malformed (no parseable content)

## Rejection Procedure

### 1. Log to Traces
Record the rejection with full diagnostic context:
```
task_id: {task_id}
phase: "reject"
step_index: {step_index}
evaluation_score: {final_score}
evaluation_feedback: {final_feedback}
revision_attempt: {MAX_RETRIES}
status: "rejected"
```

### 2. Notify CEO via Slack
Post a structured rejection notification:
```
🚫 Darius Task Rejected

Task: {task description, truncated to 200 chars}
Task ID: {task_id}
Step: {step_index}
Attempts: {attempts}/{MAX_RETRIES}
Reason: {final_feedback, truncated to 500 chars}

"Agent output failed quality evaluation after maximum retries. Manual intervention required."
```

### 3. Return Failure to Pipeline
Return the best output received (last attempt) with `passed=False` so the pipeline can:
- Skip dependent steps that require this output
- Mark the task as `failed` in the ticket system
- Include partial output in the rejection report for debugging

## What Reject Does NOT Do
- Never retries — that's the revise phase's job
- Never modifies the output — it failed, we accept that
- Never auto-resolves — always requires human intervention
- Never suppresses the notification — CEO must know
- Never deletes traces — full history preserved for training data export

## Escalation Path
1. Reject logs to `darius_traces` (permanent record)
2. Reject notifies `SLACK_CHANNEL_ID` (immediate visibility)
3. If Slack delivery fails, log error but still return failure to pipeline
4. CEO reviews rejection context and decides: re-attempt manually, re-task, or drop

## Post-Rejection Actions
After rejection, the pipeline may:
- Create a support ticket for manual review
- Flag the finding/task for human re-specification
- Feed the failure pattern to the analyzer for skill refinement proposals
- Export the trace chain as negative training data

## Metrics Tracked
- Rejection rate (rejections / total evaluations) — target: < 10%
- Time to rejection (first attempt → final reject) — informational
- Rejection reasons (categorized for pattern analysis)
- Repeat rejections (same task type failing repeatedly → skill gap signal)

## Integration
- Called by: `evaluate_with_retries()` in `AI/darius/evaluator.py` (after retry loop)
- Called by: `evaluate_output()` directly (on guardrail violations)
- Notifies: Slack via `notify_rejection()` in `AI/darius/evaluator.py`
- Traces: logged via `AI/darius/memory.log_trace(phase="reject")`
- Feeds: `AI/darius/swarm/analyzer.py` (failure pattern detection)
- Feeds: `AI/darius/swarm/refiner.py` (skill refinement proposals)
