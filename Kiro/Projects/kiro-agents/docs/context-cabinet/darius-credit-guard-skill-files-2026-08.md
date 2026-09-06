# Darius Credit Guard Fix & Skill File Implementation

## Date: 2026-08-23 (credit fix) / 2026-07-20 (skill files)

---

## Issue 1: Darius Auto-Improvement "new_skill_needed" Proposals

**Problem:** Darius daily auto-improvement report kept generating 3 proposals saying "No skill file found for tool 'None' in phase 'evaluate/revise/reject'."

**Root Cause:** The `_find_relevant_skill()` method in `AI/darius/swarm/refiner.py` only mapped tool names to skill files. The evaluate/revise/reject phases are internal Darius phases that log with `tool_name=None` — they had no skill files and no mapping.

**Fix Applied (2026-07-20):**
1. Created 3 skill files:
   - `agents/skills/darius-evaluate.skill.md` — Quality gate: scoring criteria (structural validity 0.25, task alignment 0.35, completeness 0.25, quality 0.15), pass threshold 0.70, guardrail instant-fail rules
   - `agents/skills/darius-revise.skill.md` — Retry coordinator: feedback construction, MAX_RETRIES (default 3, ceiling 6), escalation to reject
   - `agents/skills/darius-reject.skill.md` — Terminal handler: trace logging, Slack notification, clean pipeline exit

2. Patched `AI/darius/swarm/refiner.py` — Added phase-based fallback to `_find_relevant_skill()`:
   ```python
   phase_skill_map = {
       "evaluate": "darius-evaluate.skill.md",
       "revise": "darius-revise.skill.md",
       "reject": "darius-reject.skill.md",
   }
   ```

**Critical Lesson:** Changes to agents/skills/ and AI/ directories are BAKED INTO the Docker image at build time (Dockerfile.darius uses `COPY agents/ ./agents/` and `COPY AI/ ./AI/`). Local file changes require `docker compose build darius-agent && docker compose up -d darius-agent` to take effect. Volume mounts only cover `/app/Projects`.

---

## Issue 2: Agent 500 Error — Credit Budget Exhausted

**Problem:** Tasks submitted to Darius via Slack returned "500 Internal Server Error" from `http://code-agent:8000/task`.

**Root Cause:** `_guard_credit_balance()` in `agents/base_agent.py` queries `llm_traces` table for monthly spend. It was blocking at 95% of budget. Budget was $25 (hardcoded default), spend was $33.15.

**How the guard works:**
- Reads `LLM_MONTHLY_BUDGET_USD` env var (default: $25.00)
- Queries: `SELECT COALESCE(SUM(cost_usd), 0) FROM llm_traces WHERE created_at > date_trunc('month', NOW())`
- Blocks at 95% threshold ($23.75 for a $25 budget)
- Raises `CreditExhaustedError` which becomes a 500

**Fix Applied (2026-08-23):**
1. Set `LLM_MONTHLY_BUDGET_USD=500.00` in `.env` (was $25, Anthropic account limit is $200k)
2. Force-recreated ALL containers: `docker compose up -d --force-recreate`

**Critical Lessons:**
- `docker compose restart` does NOT re-read `.env` files — must use `--force-recreate` or `up -d` with recreate
- ALL agents share the same `.env` via `env_file: ../.env` — budget change affects entire fleet
- The spend tracker is in PostgreSQL, not Anthropic's side — "resetting tokens" on Anthropic doesn't clear local tracking

---

## Pending Items for Post-Migration Revisit

1. **Preview server port conflict** — Port 3001 blocked by orphan artistos containers. Run `docker compose up -d --remove-orphans` to clean up.
2. **VaultWarden argon2id warnings** — Docker compose spits hundreds of warnings about unset variables from the VaultWarden admin token hash containing `$` chars. The token value in `.env` gets interpreted as variable references. Needs quoting fix.
3. **Budget monitoring** — Consider adding a Slack alert when spend hits 75% of budget (early warning before hard block).
4. **Skill file hot-reload** — Consider adding volume mount for `agents/skills/` to avoid rebuilding darius-agent image for every skill file change.

---

## Key File Locations

| What | Where |
|------|-------|
| Credit guard | `agents/base_agent.py` lines 96-130 |
| Evaluator | `AI/darius/evaluator.py` |
| Refiner (skill lookup) | `AI/darius/swarm/refiner.py` |
| Skill files | `agents/skills/darius-{evaluate,revise,reject}.skill.md` |
| Docker compose | `docker/docker-compose.yml` |
| Darius Dockerfile | `docker/Dockerfile.darius` |
| Env file | `.env` (LLM_MONTHLY_BUDGET_USD=500.00) |

## Docker Gotchas Cheat Sheet

| Action | Effect on .env |
|--------|---------------|
| `docker compose restart <svc>` | ❌ Does NOT re-read .env |
| `docker compose up -d <svc>` | ❌ Only recreates if config changed |
| `docker compose up -d --force-recreate <svc>` | ✅ Recreates with fresh .env |
| `docker compose build <svc> && up -d <svc>` | ✅ Rebuilds image + recreates |
