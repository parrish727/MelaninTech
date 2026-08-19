---
inclusion: auto
description: "Enterprise multi-agent AI operations framework with DevOps, SRE, and AI Engineering capabilities."
---

# Enterprise AI Agent Framework — Overview

Multi-agent AI operations framework for Melanin Technologies Inc. providing autonomous DevOps,
Site Reliability Engineering, and AI Engineering capabilities within a self-hosted Docker/K8s environment.
Enforces strict security guardrails, environment isolation, and human-in-the-loop governance.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ AI Agent Layer                                          │
│                                                         │
│ ┌──────────┐ ┌──────────┐ ┌──────────────────┐        │
│ │ DevOps   │ │ SRE      │ │ AI Engineering   │        │
│ │ Agent    │ │ Agent    │ │ Agent            │        │
│ └────┬─────┘ └────┬─────┘ └────────┬─────────┘        │
│      │             │                │                   │
│ ┌────┴─────────────┴────────────────┴─────────┐        │
│ │      Darius — Multi-Agent Router            │        │
│ └────────────────────────┬────────────────────┘        │
│                          │                              │
├──────────────────────────┼──────────────────────────────┤
│ Governance Layer         │                              │
│ ┌────────────────────────┴──────────────────────────┐  │
│ │ • Environment Detection (dev/staging/production)  │  │
│ │ • Guardrail Enforcement (hard + soft constraints) │  │
│ │ • Human Approval Gates (escalation rules)         │  │
│ │ • Audit Trail (every action logged)               │  │
│ └───────────────────────────────────────────────────┘  │
│                          │                              │
├──────────────────────────┼──────────────────────────────┤
│ Tool Layer (MCP + Shell) │                              │
│                          │                              │
│ ┌────────────┐ ┌────────┴──────┐ ┌────────────────┐   │
│ │ PostgreSQL │ │ Docker/K8s    │ │ GitHub/Slack    │   │
│ │ (pgvector) │ │ (containers)  │ │ (MCP servers)   │   │
│ └─────┬──────┘ └───────┬───────┘ └───────┬────────┘   │
│       │                 │                  │            │
├───────┼─────────────────┼──────────────────┼────────────┤
│       ▼                 ▼                  ▼            │
│  Mac Pro — Self-Hosted Infrastructure                   │
│  Docker Compose (30+ containers) on docker_agent-net    │
│  Kind K8s cluster for client isolation                  │
│  nginx + Cloudflare + certbot + fail2ban               │
└─────────────────────────────────────────────────────────┘
```

## Steering File Structure

```
.kiro/steering/
├── agents/
│   ├── ai-engineer/
│   │   ├── Environments.md    # Per-project env config, detection rules
│   │   ├── Guardrails.md      # LLM safety, code quality, data protection
│   │   ├── Parameters.md      # Stack, project paths, LLM config, DB connections
│   │   ├── Security.md        # Auth patterns, HIPAA, prompt injection, secrets
│   │   ├── Skills.md          # FastAPI, React, Ollama, MCP, testing patterns
│   │   └── Tools.md           # Available tools, dependency mgmt, deferrals
│   ├── devops/
│   │   ├── Guardrails.md      # Hard/soft constraints for DevOps
│   │   ├── Parameters.md      # Service map, ports, identity
│   │   ├── Skills.md          # Container lifecycle, K8s, nginx operations
│   │   └── Tools.md           # Available tools and risk levels
│   └── sre/
│       ├── Environments.md    # Per-environment access rules
│       ├── Guardrails.md      # Database protection, HIPAA, operational limits
│       ├── Parameters.md      # Alert thresholds, databases, response format
│       ├── Security.md        # HIPAA compliance, security monitoring
│       ├── Skills.md          # SQL diagnostics, metrics, incident workflows
│       └── Tools.md           # Available tools and deferral rules
├── shared/
│   ├── Environments.md        # Universal environment definitions
│   └── Security.md            # Cross-agent security standards
├── enterprise-ai-agent-framework.md  # This file (overview + index)
├── product-context.md         # Company, products, paths, conventions
├── ai-engineer-agent-prompt.md # AI Engineering agent system prompt
├── deployment-cicd.md         # CI/CD pipelines, Drone, Watchtower
├── devops-agent-prompt.md     # DevOps agent system prompt
├── sre-agent-prompt.md        # SRE agent system prompt
├── development-hooks.md       # Active hooks documentation
├── documentation-standards.md # Doc writing rules
├── error-handling.md          # Python + TypeScript error patterns
├── python-lambda.md           # Python/FastAPI coding standards
├── security-standards.md      # Auth, secrets, container security
└── typescript-node.md         # TypeScript/React coding standards

.kiro/agents/profiles/
├── ai-agent.json              # AI Engineering Agent profile
├── devops-agent.json          # DevOps Agent profile
└── sre-agent.json             # SRE Agent profile

.kiro/hooks/
├── docker-validate.json       # Docker Compose validation on save
├── environment-verify.json    # Tool/service availability check (manual)
├── governance-guard.json      # Hard constraint enforcement (preToolUse)
├── python-lint.json           # ruff linting on Python save
├── sync-docs.json             # Auto-update docs on infra change
└── typescript-check.json      # tsc type checking on TS save
```

## Agent Roster

| Agent | Role | Domain | Profile |
|-------|------|--------|---------|
| DevOps | Sr. DevOps Engineer | Infrastructure, containers, CI/CD, networking | `devops-agent.json` |
| SRE | Sr. Site Reliability Engineer | Observability, DB diagnostics, SLI/SLO, incidents | `sre-agent.json` |
| AI Engineering | Sr. AI/Software Engineer | App development, ML systems, LLM integration | `ai-agent.json` |

## Guardrail Layers

| Layer | Enforcement | Override |
|-------|-------------|---------|
| Hard constraints | Code-level blocks (never bypass) | Not possible |
| Soft constraints | Require human approval via Slack | Governance layer approval |
| Environment detection | Automatic from container name/port | Fail-safe to production if unknown |

## Multi-Agent Routing (Darius)

1. Task arrives via Slack (/task or @mention)
2. Darius analyzes keywords and domain
3. Routes to specialist agent based on profile capabilities
4. Agent operates within its guardrails and tool boundaries
5. Cross-domain needs trigger deferral (agent → Darius → appropriate agent)
6. Collaboration patterns: sequential chaining, parallel execution, escalation

## Design Principles

1. **Security by default** — Production read-only, no credentials in transit, fail-safe to most restrictive
2. **Observability over control** — Agents observe and recommend; humans execute high-impact changes
3. **Separation of concerns** — Each agent has clear domain boundaries with explicit deferral rules
4. **Enterprise standards compliance** — Every recommendation references the governing policy
5. **Progressive disclosure** — Agents offer drill-down rather than dumping all data
6. **Idempotent operations** — All infrastructure changes via versioned manifests, no drift
7. **Self-healing by design** — Restart policies, Watchtower, certbot, DDNS, fail2ban
8. **Deploy-time configuration** — Monitoring travels with the service deployment
