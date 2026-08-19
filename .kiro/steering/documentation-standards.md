---
inclusion: fileMatch
fileMatchPattern: "**/*.md,**/docs/**,**/MelaninDocs/**,**/README*"
description: "Documentation standards and rules for writing and maintaining project docs."
---

# Documentation Standards

## Core Rules

1. **Only document what exists** — never add aspirational or planned features as if they're live
2. **Match existing format** — when updating a doc, preserve its tone, structure, and style
3. **Never reference AWS/Azure** — all infrastructure is self-hosted (Docker + Kind K8s on Mac Pro)
4. **Finance/ is read-only** — never modify files in `MelaninDocs/Finance/`
5. **Be concise** — prefer tables over paragraphs, code over prose
6. **Date all updates** — include "Last Updated: YYYY-MM-DD" in documents that track state

## Document Types

### README.md (per project/service)
Required sections:
- **What it is** — one sentence
- **Stack** — technologies used
- **Setup** — how to run locally
- **Ports** — what ports it uses
- **Environment variables** — list (names only, not values)
- **Deployment** — how it gets to production

### Architecture Docs (`docs/architecture.md`)
Required sections:
- Component diagram (ASCII or Mermaid)
- Service interactions
- Data flow
- Security boundaries

### Runbooks (`ai-sre/observability/runbooks/`)
Required sections:
- Symptoms (what triggered this runbook)
- Diagnosis steps
- Remediation steps
- Verification steps
- Escalation criteria

### Governance Policies (`governance/*.md`)
Required sections:
- Purpose
- Scope
- Policy statements
- Responsibilities
- Exceptions process
- Review schedule

## Automatic Doc Sync

When infrastructure, agent, or steering files change, the sync-docs hook (v2.0) automatically updates:
1. `MelaninDocs/Glossary.md` — New terms added, stale entries corrected
2. `MelaninDocs/MultiAgentArchitecture.md` — Agent list, routing, memory, model selection
3. `MelaninDocs/Onboarding/MelaninTechnologiesInternalOnboarding.md` — Internal Systems table, tech stack
4. `A.I./ai-sre/docs/architecture.md` — Component list, infra section
5. `A.I./ai-sre/automation/scripts/health_check.py` — Service list
6. `A.I./ai-sre/observability/runbooks/incident_response.md` — Agent names, ports
7. `Kiro/Projects/kiro-agents/k8s/README.md` — Port map, image list

**Trigger patterns:** docker-compose.yml, Dockerfile*, k8s manifests, orchestrator/*.py, agents/*.py, AI/darius/*.py, config/settings.py, .kiro/steering/**/*.md, hud/backend/main.py, scripts/security_watchdog.py, governance/**/*.md

Only sections that are factually wrong after the change get updated. The hook preserves existing format and tone.

## Forbidden Patterns

- ❌ "We plan to..." or "In the future..." (aspirational)
- ❌ "Azure" / "AWS" / "GCP" (wrong infra)
- ❌ Actual secret values (use `<REDACTED>` or variable names)
- ❌ Patient data or PII examples (use anonymized placeholders)
- ❌ Version numbers without verification (check running state first)
