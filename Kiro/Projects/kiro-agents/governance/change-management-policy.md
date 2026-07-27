# Change Management Policy

## Change Flow

```
Request → Proposal → Review → Approve → Test → Stage → Production
   │          │         │         │        │       │         │
 Slack     Agent    Guardrail   Human   Auto    Auto    Slack button
 /task     generates  hook      in      deploy  deploy   explicit
           code      scans     Slack   :3002   :3003    approval
```

## Environments

| Environment | Port | Auto-deploy | Purpose |
|-------------|------|-------------|---------|
| Testing | 3002 | On approval | Automated verification |
| Staging | 3003 | After testing passes | Pre-production validation |
| Production | 3000 | Explicit Slack button only | Live traffic |

## Rules

1. **No direct production changes.** All changes flow through the pipeline.
2. **Human approval required** for every code change (Slack approve/modify/reject).
3. **Guardrail hook fires** on every agent/orchestrator file change — blocks violations.
4. **QA agent runs** after every approved change — flags issues before staging.
5. **Production deploy requires explicit Slack button click** — never automatic.
6. **Rollback:** `docker compose up -d --build <service>` with previous git commit.

## Ticket Lifecycle

```
open → in_progress → done
                  → rejected
                  → failed_backlog (after 9 retries, normal priority)
                  → failed_urgent (after 9 retries, urgent priority — stays visible)
```

## Audit Trail

Every change is tracked:
- Git commit history (who, what, when)
- Ticket log field (append-only timestamped status changes)
- Slack message thread (proposal + approval decision)
- pgvector memory (decision stored for future recall)

## Emergency Changes

For critical production issues:
1. CEO can approve via Slack immediately (skip testing/staging)
2. Deploy agent executes directly
3. Post-incident: QA agent reviews the change retroactively
4. Incident logged in ticket system with `priority: urgent`
