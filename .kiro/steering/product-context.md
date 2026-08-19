---
inclusion: auto
description: "Company product context, active projects, infrastructure summary, and conventions for Melanin Technologies Inc."
---

# Melanin Technologies Inc. — Product Context

## Company

Black-owned technology consulting & development firm, incorporated in Wisconsin, operating from Charlotte, NC.
Website: www.melanin-tech.com | HUD: hud.melanin-tech.com

**Revenue Streams:**
1. **SaaS** — OrthoFlow AI (orthodontic AP automation + insurance claims)
2. **Software-in-a-Service** — Custom builds + managed hosting + ongoing development
3. **Infrastructure-as-a-Service** — Managed hosting for SMBs ($99–$999/mo)
4. **Consulting** — Strategy, architecture, contract development ($150–$175/hr)

## Active Products

| Project | Path | Stack | Status |
|---------|------|-------|--------|
| melanin-tech-website | `melanin-tech-website/` | Next.js 16, Tailwind, Framer Motion | Live (www.melanin-tech.com) |
| Kiro Agents | `Kiro/Projects/kiro-agents/` | Python, FastAPI, Docker, Slack, MCP | Live (internal) |
| OrthoFlow AI | `LinesOfBusiness/Orthodontic_Dental/orthoflow-ai/OrthoFlow/` | FastAPI, React+Vite, PostgreSQL, Redis, MinIO, Ollama | Live (app.orthoflowsolutions.com) |
| ParcelPro | `LinesOfBusiness/Parcel_Pro/` | FastAPI, React+Vite, PostGIS, MapLibre, Martin, Redis | Prototype |
| HTC App | `LinesOfBusiness/Held_Together_Caregiving/htc-app/` | FastAPI, React+Vite, Tailwind | In Development |
| Music Catalogue | `music-catalogue-system/` | FastAPI, React+Vite, Tailwind, PostgreSQL | Prototype |

## Infrastructure Summary

- **Hosting:** Self-hosted Mac Pro, Google Fiber, Cloudflare proxy
- **Orchestration:** Docker Compose (30+ containers) on docker_agent-net bridge
- **TLS:** Let's Encrypt (certbot auto-renew, cert-monitor Slack alerts)
- **K8s:** Kind cluster for client isolation (per-namespace)
- **CI/CD:** Drone CI (local), GitHub Actions (OrthoFlow), Watchtower (auto-deploy)
- **Monitoring:** HUD dashboard (WebSocket live, 5-min snapshots, 1-year retention)
- **Security:** fail2ban, nginx rate limiting, HSTS, CSP, Cloudflare DDoS proxy

## Key Paths

```
/Users/pktech_dev/Documents/MelaninTechnologies/
├── Kiro/Projects/kiro-agents/          # Agent system + all infrastructure
│   ├── docker/docker-compose.yml       # All production services
│   ├── agents/                         # 11 specialist agents
│   ├── agents/skills/                  # Hot-reloadable skill definitions
│   ├── AI/darius/                      # Darius orchestration agent
│   ├── k8s/                            # Kubernetes manifests + client platform
│   ├── governance/                     # Compliance & security policies
│   └── .env                            # All secrets (gitignored)
├── melanin-tech-website/               # Production website source
├── LinesOfBusiness/                    # Client products (OrthoFlow, HTC)
├── A.I./ai-sre/                        # SRE runbooks, alerts, automation
├── MelaninDocs/                        # Internal docs (onboarding, finance, proposals)
├── BusinessDocs/                       # Corporate records
└── .kiro/steering/                     # AI Agent Framework steering files
```

## Documentation Map

| Doc | Path | Audience | Access |
|-----|------|----------|--------|
| Internal Onboarding | `MelaninDocs/Onboarding/` | Team | Read/Write |
| Client Proposals | `MelaninDocs/ClientProposal/` | Sales | Read/Write |
| Finance | `MelaninDocs/Finance/` | Internal | **Read-only** |
| Business Docs | `BusinessDocs/` | Corporate | Read-only |
| Governance | `Kiro/Projects/kiro-agents/governance/` | Compliance | Read/Write |
| SRE Runbooks | `A.I./ai-sre/` | Operations | Read/Write |

## Conventions (Quick Reference)

- **Python:** type hints on all signatures, FastAPI + Pydantic validation, ruff linting
- **TypeScript:** strict mode, no `any`, Prettier formatting
- **Frontend:** Tailwind CSS only, Lucide icons, Framer Motion animations
- **Containers:** Docker Compose for dev/prod, K8s for multi-tenant client hosting
- **Secrets:** never in code, always via .env (gitignored) or K8s secrets
- **LLM:** Anthropic Claude only for production (no OpenAI, no Google)
- **Embeddings:** Ollama nomic-embed-text (local, no external API)
- **Docs:** only document what exists, never reference AWS/Azure, Finance/ is read-only
- **Git:** conventional commits, no force push, feature branches → PR → merge
