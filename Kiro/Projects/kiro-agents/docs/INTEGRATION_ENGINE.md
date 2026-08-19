# Melanin Technologies — Integration Engine

## Purpose

Enable Darius and the agent system to connect to ANY client's business tools (Gmail, Notion, CRM, Calendar, etc.) and run automated workflows on their behalf. This is the core of the AI Automation Agency model.

---

## Architecture

```
Client's Business Tools
    │
    ├── Inbound: Triggers (new email, form submitted, calendar event)
    │   └── Webhook → integration-engine → creates ticket → orchestrator → agent processes
    │
    └── Outbound: Actions (send email, create task, update CRM)
        └── Agent proposes → approval → integration-engine → client's tool
```

## How It Fits Our Existing Stack

| Existing | Extension |
|----------|-----------|
| Slack triggers tasks | Client webhooks also trigger tasks |
| Agents generate proposals | Agents also generate actions (send email, create record) |
| Approval flow (Slack buttons) | Same approval flow for client automations |
| pgvector memory | Stores client workflow patterns for learning |
| Templates (YAML) | Client-specific workflow templates |
| Skills (.skill.md) | Client-specific skills (industry knowledge) |

---

## Integration Registry

Each connector is a Python module in `integrations/`:

```
integrations/
├── __init__.py
├── registry.py          # Central registry of all connectors
├── base.py              # Base connector class (auth, refresh, rate limit)
├── gmail/
│   ├── connector.py     # Send, read, label, search emails
│   └── triggers.py      # New email webhook
├── notion/
│   ├── connector.py     # Create page, update DB, query
│   └── triggers.py      # Page updated webhook
├── google_calendar/
│   ├── connector.py     # Create event, list events
│   └── triggers.py      # Event reminder webhook
├── hubspot/
│   ├── connector.py     # Create contact, update deal
│   └── triggers.py      # New deal webhook
└── quickbooks/
    ├── connector.py     # (already exists in OrthoFlow)
    └── triggers.py
```

## Auth Flow (Managed by Vaultwarden)

1. Client authorizes via OAuth (one-time setup)
2. Tokens stored in Vaultwarden under client's folder
3. Integration engine refreshes tokens automatically
4. If token expires mid-workflow → pause, notify, re-auth

---

## Agency Workflow Pattern

### Phase 1: Discovery (Manual)
- Pick industry (e.g., travel agency)
- Run their workflow yourself for 2 weeks
- Document edge cases in Obsidian/notes
- Identify the repetitive parts

### Phase 2: Skill Creation
- Write a `.skill.md` for the vertical
- Define the workflow as a YAML template
- Create training examples from Phase 1 docs

### Phase 3: Integration
- Connect to client's tools via OAuth
- Wire triggers (new booking → process)
- Wire actions (send confirmation → email)

### Phase 4: Managed Automation
- Deploy as a managed service (SiaS)
- Client pays monthly for the automation
- You monitor via HUD, SRE alerts on failures
- Iterate and improve based on edge cases

---

## Revenue Model (per client)

| Phase | Revenue |
|-------|---------|
| Discovery + Setup | $2,500-5,000 one-time |
| Monthly automation | $499-999/mo managed |
| Per-action (high volume) | $0.10-0.50 per processed item |

## Darius's Role

Darius becomes the **orchestration brain** for client automations:
- Receives triggers from integration engine
- Routes to appropriate skill/template
- Executes multi-step workflows
- Learns from approvals/rejections (training data for local model)
- Chains tools: read email → classify → draft response → get approval → send

---

## First Integration Targets

1. **Gmail** — most businesses run on email (inbound leads, support, confirmations)
2. **Google Calendar** — scheduling, reminders, availability
3. **Notion** — documentation, task management, databases
4. **QuickBooks** — already built for OrthoFlow, generalize it

---

## Implementation Priority

1. Create `integrations/` directory with base connector class
2. Build Gmail connector (read/send/label via Google API)
3. Build trigger receiver (webhook endpoint in orchestrator)
4. Create first vertical skill (document a boring workflow)
5. Wire into YAML template system for repeatable execution

---

*This is the same pattern as OrthoFlow (connect to practice tools → AI processes → human approves) generalized to ANY industry.*
