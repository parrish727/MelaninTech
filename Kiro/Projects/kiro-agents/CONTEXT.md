# Melanin Technologies Inc. — Project Context (May 2026)

## Company
- Technology consulting & development firm, Charlotte, NC
- Four revenue streams: SaaS, Software-in-a-Service, Infrastructure-as-a-Service, Consulting
- Website: www.melanin-tech.com (self-hosted, Google Fiber, Cloudflare)
- HUD: hud.melanin-tech.com (internal monitoring, secured)
- Domain: melanin-tech.com (Cloudflare DNS)
- Contact: info@melanin-tech.com
- Integration email: developer.integrator@melanin-tech.com

## Infrastructure
- Mac Pro (home server), Google Fiber, ports 80/443 forwarded
- Docker Compose: 30+ containers on docker_agent-net
- Cloudflare DDNS auto-updates IP every 5 min
- nginx: TLS termination, rate limiting, security headers
- certbot: auto-renewing Let's Encrypt certs (melanin-tech.com + orthoflowsolutions.com)
- fail2ban: intrusion detection
- Kind K8s cluster (local, for future scaling)

## Agent System (Kiro)
- 11 agents: orchestrator, frontend, backend, scaffold, deploy, support, code, file, uxui, darius, qa
- Skill/Script/Template pattern: agents/skills/*.skill.md (hot-reloadable)
- Dynamic spawning: agents/template/spawn.py
- Darius v1.1: chaining, replay, MCP auto-discovery, tool confirmation
- Orchestrator: Slack-triggered (/task or @mention), approval flow, semantic memory (pgvector)
- Router keywords determine agent routing
- QA agent runs after every approved change
- Project isolation enforced at prompt + filesystem level

## HUD (Internal Monitoring)
- URL: https://hud.melanin-tech.com (live, TLS secured)
- Auth: password + TOTP 2FA
- 10 tabs: Executive, Agents, Infrastructure, Darius, Projects, Tickets, Memory, Security, Clients, Contracts
- WebSocket live updates (10s), health snapshots every 5 min (1-year retention)
- Container failure alerts to Slack
- Darius AI integrated (contract intelligence, rate optimization)
- LLM token/cost tracking per agent/model

## OrthoFlow AI (Client Product)
- URL: app.orthoflowsolutions.com / api.orthoflowsolutions.com
- Repo: github.com/parrish727/OrthoFlow (private, feature/orthoflow_v1 branch)
- Stack: FastAPI backend (8000), React frontend (5173), PostgreSQL (5433), Redis (6380), MinIO (9100), Ollama (11435)
- Features: invoice upload, OCR, LLM classification, approval, QuickBooks sync
- Integrations: QuickBooks (OAuth), Plaid (ACH), Ortho2 (API), Dentrix/Eaglesoft (file import)
- AI: custom orthoflow-classify model (auto-created on worker startup), spend intelligence, vendor insights
- Security: ClamAV virus scanning, JWT practice-scoped auth, SMS OTP MFA, HIPAA audit logs
- Tier system: Standard (multi-tenant) / Enterprise (single-tenant K8s namespace)
- Demo accounts: admin@testortho.com/test123 (generic), demo@marcallenortho.com/demo123 (client demo)
- Watchtower auto-deploys from GHCR on merge to main
- Privacy policy + Terms of Service at /privacy and /terms

## Git Repos
- github.com/parrish727/MelaninTech (private) — internal infrastructure, agents, HUD, docs
- github.com/parrish727/OrthoFlow (private) — OrthoFlow product code
- melanin-tech-website has its own local git (not pushed to remote)

## Key Paths
- /Users/pktech_dev/Documents/MelaninTechnologies/ — root
- Kiro/Projects/kiro-agents/ — agent system, docker-compose, HUD
- Kiro/Projects/kiro-agents/.env — all secrets
- Kiro/Projects/kiro-agents/docker/docker-compose.yml — all services
- melanin-tech-website/ — company website source (Next.js)
- LinesOfBusiness/Orthodontic_Dental/orthoflow-ai/OrthoFlow/ — OrthoFlow repo

## Ports
- 80/443: nginx (routes by domain)
- 3000: melanin-tech.com production
- 3001: preview, 3002: testing, 3003: staging
- 4000: HUD frontend
- 5173: OrthoFlow frontend
- 8000: OrthoFlow backend
- 8080: HUD backend (internal)
- 5433: OrthoFlow postgres
- 11434: Kiro Ollama, 11435: OrthoFlow Ollama

## Current Backlog
- OrthoFlow: email verification (needs SMTP app password), logo, registration ToS checkbox, password reset UI
- OrthoFlow v2.1: Medicare/Medicaid insurance claims processing (Ticket #74)
- HUD Contracts: persistence layer — Postgres CRUD + upload form (Ticket #75)
- Governance: container vulnerability scanning, non-root migration, pen test, DR test, BAA execution
- Multi-location dashboard (when client needs it)
- Dentrix API partnership application (in progress)
- Website: add Infrastructure/Hosting section, SiaS messaging, consulting + development positioning
