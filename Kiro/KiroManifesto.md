# Kiro Agents — Manifesto

> A Slack-native, AI-powered multi-agent system built on Claude, designed to route, propose, and execute development tasks with human approval at every step.

---

## What It Is

Kiro Agents is an orchestrated multi-agent framework where a Slack bot acts as the human interface. You issue a task via Slack, the system routes it to the right AI agent, the agent generates a proposal, and you approve, modify, or reject it before anything is executed.

No agent acts autonomously. Every action requires a human decision.

---

## Project Structure

```
kiro-agents/
├── orchestrator/
│   ├── main.py          # Slack bot — /task, /task-internal, /tickets, /agent-status, approve, reject, modify, deploy_production, skip_production
│   ├── router.py        # Keyword classification + support contract gate (timeout: 300s)
│   ├── approval.py      # Proposal UI, modify modal, file execution, auto-deploy pipeline trigger
│   ├── deploy_pipeline.py # Auto-deploy: testing → staging → production approval button
│   ├── contracts.py     # Support contract enforcement (post-launch 90-day + usage-based)
│   ├── tickets.py       # Ticket tracking — open, heartbeat, attempts, priority, log, list
│   ├── memory.py        # Vector memory + conversation memory (pgvector + Ollama)
│   └── watchdog.py      # Stuck agent detection, container restart, retry (max 9), 5hr Slack digest
├── agents/
│   ├── base_agent.py    # Shared FastAPI factory + LLM selector + guardrails (path, model, proposal)
│   ├── design_spec.py   # Melanin Technologies design system — colors, typography, spacing, components
│   ├── scaffold_agent.py
│   ├── backend_agent.py
│   ├── frontend_agent.py  # Injects DESIGN_SPEC into every proposal
│   ├── uxui_agent.py      # Injects DESIGN_SPEC + Playwright visual audit into every proposal
│   ├── deploy_agent.py  # Daemon-aware (detects long-running processes, uses Popen)
│   ├── support_agent.py
│   ├── file_agent.py
│   └── code_agent.py
├── config/
│   ├── settings.py              # Env vars, agent URLs, project base path
│   └── support_contracts.json   # Client support contract store
├── docker/
│   ├── Dockerfile               # Orchestrator container image
│   ├── Dockerfile.agent         # Shared agent container image
│   └── docker-compose.yml       # All services + melanin-website on private bridge network
├── .kiro/
│   ├── steering/
│   │   ├── agent-rules.md       # Hard guardrails — destructive commands, secrets, path traversal, model blocks
│   │   └── agent-skills.md      # Capability map for every agent
│   └── hooks/
│       ├── guardrail-check.yaml # Fires on agent/orchestrator changes — scans for 8 violation types
│       └── sync-steering.yaml   # Keeps skills + rules docs in sync with code changes
├── post_updates.py
├── .env
├── .gitignore
├── .dockerignore
└── requirements.txt
```

---

## How It Works

### 1. Triggering a Task

```
/task client-a: scaffold a new project called invoice-tracker    ← client ticket
/task client-a: backend — add a POST /invoices endpoint
/task client-a: frontend — build the invoices list page
/task client-a: deploy the project
/task client-a: bug — the /invoices endpoint returns 500 on empty db
/task-internal: update the manifesto docs                        ← internal ticket
```

### 2. Routing

| Keywords | Agent |
|---|---|
| `scaffold`, `bootstrap`, `new project`, `init project` | ScaffoldAgent |
| `deploy`, `launch`, `build image`, `go live` | DeployAgent |
| `bug`, `fix`, `broken`, `error`, `issue`, `support`, `crash` | SupportAgent *(contract-gated)* |
| `frontend`, `component`, `page`, `ui`, `next.js`, `react` | FrontendAgent |
| `backend`, `api`, `route`, `endpoint`, `model`, `fastapi` | BackendAgent |
| `file`, `read`, `create`, `delete`, `move`, `folder` | FileAgent |
| everything else | CodeAgent |

### 3. Agent Processing

Each agent is a FastAPI microservice. `base_agent.py` selects a model based on task complexity, sends a heartbeat pulse every 15 seconds while the LLM is generating, and runs three guardrail checks on every proposal before returning it:
- **Model guard** — blocks any `openai/` model name
- **Path guard** — blocks writes outside `/app/Projects` (symlink-safe via `os.path.realpath`)
- **Proposal guard** — scans LLM output for destructive patterns (`rm -rf`, `DROP TABLE`, `TRUNCATE`, etc.)

### 4. Ticket Creation

Every `/task` or `/task-internal` submission automatically opens a ticket in Postgres with:
- `type`: `client` or `internal`
- `priority`: `normal` or `urgent`
- `status`: `open` → `in_progress` → `done` / `rejected` / `failed_backlog` / `failed_urgent`
- `attempts`: incremented on each watchdog retry
- `last_heartbeat`: updated every 15s by the active agent
- `log`: append-only timestamped log of all status changes
- Full task, proposal, agent, and timestamps stored

### 5. Approval Flow

Slack message shows proposal + similar past tasks from vector memory + buttons:
- ✅ Approve → executes, ticket → `done`, stored in memory
- ✏️ Modify → opens modal to edit inline → executes, ticket → `done`
- ❌ Reject → discarded, ticket → `rejected`, stored in memory

### 6. Execution

Approved proposals are parsed for fenced code blocks with path comments:
```python
# api/routes/invoices.py
<code here>
```
Each block is written to the correct file path under the client's project directory.

Deploy proposals detect whether the script is long-running (dev servers, uvicorn, gunicorn) and use `subprocess.Popen` (daemon mode) instead of blocking `subprocess.run`. Daemon processes log to `deploy.log` and return a PID immediately.

### 7. Watchdog

A background thread runs inside the orchestrator and sweeps every 30 seconds:

| Agent | Timeout |
|---|---|
| file | 30s |
| code, support | 2 min |
| backend, frontend | 3 min |
| scaffold | 5 min |
| deploy | 10 min |

When a ticket's `last_heartbeat` expires:
1. Attempt counter incremented
2. Agent container restarted via Docker SDK (`/var/run/docker.sock`)
3. Task requeued with a fresh agent call (non-blocking thread)
4. Slack alert posted with container name + attempt number

After 9 attempts:
- `normal` priority → `failed_backlog`
- `urgent` priority → `failed_urgent` (stays visible, never backlogged)

Every 5 hours the watchdog posts a 12-hour activity digest to Slack grouped by status.

### 8. Support Contracts

Two types managed in `config/support_contracts.json`:
- **post_launch** — 90 days from go-live, then expires
- **usage** — fixed ticket count, decremented per support request

---

## Slack Commands

| Command | Usage |
|---|---|
| `/task` | `/task <client>: <description>` — client-facing ticket |
| `/task-internal` | `/task-internal <project>: <description>` — internal ticket |
| `/tickets` | `/tickets [client] [status] [client\|internal]` — list tickets |
| `/agent-status` | Show latest ticket status, agent, and project |

---

## Services

| Service | Role | Port |
|---|---|---|
| orchestrator | Slack bot, approval queue, routing, watchdog | — |
| scaffold-agent | Project bootstrapping | 8000 (internal) |
| backend-agent | FastAPI code generation | 8000 (internal) |
| frontend-agent | Next.js/TS code generation + design spec injection | 8000 (internal) |
| uxui-agent | Visual design + Playwright audit + design spec injection | 8000 (internal) |
| deploy-agent | Docker deploy execution (daemon-aware) | 8000 (internal) |
| support-agent | Bug diagnosis and fixes | 8000 (internal) |
| file-agent | File operations | 8000 (internal) |
| code-agent | General code generation | 8000 (internal) |
| playwright-mcp | Visual screenshot/audit service | 9001 (host) |
| preview-server | Proposal preview (Next.js) | 3001 (host) |
| testing-server | Auto-deployed on approval | 3002 (host) |
| staging-server | Auto-deployed after testing | 3003 (host) |
| production-server | Deployed on explicit Slack approval | 3000 (host) |
| postgres | Primary DB + vector store + tickets | 5432 (internal) |
| ollama | Local embeddings (nomic-embed-text) | 11434 (internal) |

---

## LLM Configuration

Controlled entirely via `.env`. OpenAI models are blocked at the code level.

```
LLM_PROVIDER=anthropic          # or "openrouter"
OPENROUTER_API_KEY=             # required if using openrouter
MODEL_DEFAULT=anthropic/claude-sonnet-4-5
MODEL_HEAVY=anthropic/claude-opus-4-5
MODEL_LIGHT=anthropic/claude-haiku-4-5
```

To cut over to OpenRouter: set `LLM_PROVIDER=openrouter` and add your key. Model names stay the same — OpenRouter routes to Anthropic's models under the hood.

---

## Running It

### Prerequisites

- Docker + Docker Compose
- Slack app with Socket Mode enabled
- Slash commands registered: `/task`, `/task-internal`, `/tickets`
- Interactive components enabled
- Anthropic API key

### Environment Variables (`.env`)

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...
SLACK_CHANNEL_ID=C...
ANTHROPIC_API_KEY=sk-ant-...
POSTGRES_PASSWORD=...
POSTGRES_DSN=postgresql://kiro:<password>@postgres:5432/kiro
OLLAMA_URL=http://ollama:11434
LLM_PROVIDER=anthropic
OPENROUTER_API_KEY=
MODEL_DEFAULT=anthropic/claude-sonnet-4-5
MODEL_HEAVY=anthropic/claude-opus-4-5
MODEL_LIGHT=anthropic/claude-haiku-4-5
```

### Start

```bash
cd kiro-agents
docker compose -f docker/docker-compose.yml --env-file .env up -d
```

> Always use `--env-file .env` — required for `${POSTGRES_PASSWORD}` interpolation. Never hardcode secrets in `docker-compose.yml`.

---

## Architecture Diagram

```
Slack User
    │
    ├── /task client: description       → type: client
    └── /task-internal: description     → type: internal
                    │
                    ▼
    Orchestrator (slack-bolt, Socket Mode)
        │
        ├── tickets.py   ── open ticket (client|internal|priority)
        ├── contracts.py ── support gate
        ├── memory.py    ── recall similar tasks
        │
        └── router.py ──► Agent :8000 (FastAPI + LLM)
                              │  └── heartbeat every 15s
                        proposal returned
                        (guardrails: model, path, destructive patterns)
                              │
                        Slack approval message
                        (+ similar past tasks)
                              │
              ┌───────────────┼───────────────┐
           Approve         Modify           Reject
              │               │               │
        ticket: in_progress  modal edit    discard +
        write files /        → write files  ticket: rejected
        daemon deploy        ticket: done   store memory
        ticket: done         store memory
        store memory
                    │
            Watchdog (every 30s)
            ├── heartbeat expired? → restart container + requeue
            ├── 9 attempts?        → failed_backlog / failed_urgent
            └── every 5hrs         → 12hr digest to Slack
```

---

## Completed Items

- [x] Multi-agent routing with keyword classification
- [x] Human-in-the-loop approval — Approve / Modify / Reject
- [x] Modify modal — edit proposals inline before execution
- [x] Real file writes — code blocks parsed and written to correct project paths
- [x] Deploy execution — bash scripts generated and executed on approval
- [x] Daemon deploy mode — long-running processes (dev servers, uvicorn) use Popen, return PID immediately
- [x] Vector memory — similar past tasks recalled on every proposal (pgvector + Ollama)
- [x] Conversation memory — CEO interaction context stored in pgvector
- [x] Support contract enforcement — 90-day post-launch + usage-based ticket plans
- [x] Ticket tracking — priority, attempts, heartbeat, append-only log, full lifecycle statuses
- [x] Client vs internal ticket distinction — `/task` vs `/task-internal`
- [x] `/tickets` Slack command — filter by client, status, type, priority
- [x] `/agent-status` Slack command — show latest ticket status, agent, project
- [x] Immediate task acknowledgment — Slack message posted instantly with ETA on `/task`
- [x] Watchdog — stuck agent detection, per-agent timeouts, Docker container restart, 9-attempt retry
- [x] Watchdog 5hr Slack digest — 12hr activity window grouped by status
- [x] Agent heartbeat — 15s pulse from every agent while LLM is generating
- [x] Runtime guardrails — model block, path traversal block, destructive pattern scan
- [x] Kiro steering docs — agent-rules.md + agent-skills.md
- [x] Kiro hooks — guardrail-check.yaml + sync-steering.yaml
- [x] OpenRouter integration — single API key, swap models via env vars
- [x] OpenAI model guard — hard block at model selection and guardrail layer
- [x] Granular Docker volume controls per agent (ro/rw scoped)
- [x] Orchestrator has Docker socket access for watchdog container restarts
- [x] Preview server — `http://localhost:3001` serves Next.js preview builds
- [x] Testing server — `http://localhost:3002` auto-deployed on proposal approval
- [x] Staging server — `http://localhost:3003` auto-deployed after testing
- [x] Production server — `http://localhost:3000` deployed via explicit Slack approval button
- [x] Auto-deploy pipeline — approve → testing → staging → production approval button in Slack
- [x] Frontend agent design spec injection — full Melanin Technologies design system baked into every prompt
- [x] UX/UI agent design spec injection — design system + Playwright visual audit on every task
- [x] MCP proxy server (`mcp-server:9000`) — 4 tools: list_files, read_file, recall_memory, project_info
- [x] MCP context injection — every agent gets project info + past tasks prepended to system prompt
- [x] Frontend agent scoped to melanin-tech-website — knows color system, components, paths
- [x] Deploy agent uses Docker SDK directly for known services — no compose file path issues
- [x] Router timeout increased to 300s — supports large tasks like full site rebuilds
- [x] PYTHONUNBUFFERED=1 on orchestrator — logs visible in Docker immediately
- [x] Secrets clean — no hardcoded values in docker-compose

## Future Plans

### Near-Term

- [ ] Register `/task-internal` and `/tickets` slash commands in Slack
- [ ] Smarter routing — replace keyword matching with LLM-based classifier
- [ ] ProposalAgent — draft client-facing SOWs and proposals

### Medium-Term

- [ ] TestAgent — write and run tests against generated code before approval
- [ ] Client portal — web UI for support ticket submission without Slack
- [ ] Multi-step chains — approved output triggers next agent automatically
- [ ] Clawdarius cutover — replace custom agent harness with Clawdarius (make repo private first)

### Long-Term

- [ ] Self-improving routing — use approval/rejection history to tune decisions
- [ ] Dynamic agent registration — agents self-register at startup
- [ ] Multi-workspace support — serve multiple Slack workspaces with isolated contexts

---

*Last updated: April 19, 2026 — auto-deploy pipeline (testing → staging → production), /agent-status command, immediate task acknowledgment with ETA, design spec injection for frontend/uxui agents, router timeout 300s, PYTHONUNBUFFERED logging*
