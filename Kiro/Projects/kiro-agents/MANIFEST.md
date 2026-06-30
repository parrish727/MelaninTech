# Melanin Technologies Inc. — System Manifest

**Last Updated:** May 30, 2026

---

## Company

Melanin Technologies Inc. — Technology consulting & development firm, Charlotte, NC.
Website: https://www.melanin-tech.com
HUD: https://hud.melanin-tech.com

**Revenue Streams:**
1. **SaaS** — OrthoFlow AI (orthodontic AP automation + insurance claims)
2. **Software-in-a-Service** — Custom builds + managed hosting + ongoing development
3. **Infrastructure-as-a-Service** — Managed hosting for SMBs ($99–$999/mo)
4. **Consulting** — Strategy, architecture, and direct contract development ($150–$175/hr)

---

## Infrastructure Overview

### Production Website
- **Domain:** www.melanin-tech.com
- **Stack:** Next.js 16 + Tailwind CSS + Framer Motion
- **Hosting:** Self-hosted (Mac Pro, Google Fiber) → Docker → nginx → Cloudflare
- **TLS:** Let's Encrypt (auto-renew via certbot, expires Aug 2, 2026)
- **Security:** nginx rate limiting, HSTS, CSP, fail2ban, Cloudflare DDoS proxy
- **DDNS:** Cloudflare DDNS updater (5-min interval)

### Agent System (Kiro)
- **Orchestrator:** Slack-based task routing with approval flow
- **Agents:** 9 specialist agents + Darius (orchestration)
  - Frontend, Backend, Scaffold, Deploy, Support, Code, File, UX/UI, Darius
- **Darius v1.1:** Agent chaining, task replay, MCP discovery, tool confirmation prompts
- **Agent Architecture:** Skill / Script / Template
  - **Skill** (`agents/skills/*.skill.md`) — hot-reloadable declarative instructions
  - **Script** (`agents/scripts/`) — deterministic multi-step automation
  - **Template** (`agents/template/spawn.py`) — dynamic agent spawning per project
- **Memory:** PostgreSQL + pgvector (semantic search via Ollama nomic-embed-text)
- **LLM:** Anthropic Claude (Sonnet/Haiku/Opus) via direct API
- **MCP Sidecars:** GitHub, PostgreSQL, Figma, Fetch
- **CI/CD:** Drone CI (port 1616/1661)

### Docker Services (Running)
| Service | Port | Status |
|---------|------|--------|
| production-server | 3000 | ✅ Live (www.melanin-tech.com) |
| preview-server | 3001 | ✅ Running |
| testing-server | 3002 | ✅ Running |
| staging-server | 3003 | ✅ Running |
| nginx | 80/443 | ✅ TLS termination |
| orchestrator | internal | ✅ Slack connected |
| postgres (pgvector) | 5432 | ✅ Running |
| ollama | 11434 | ✅ Running |
| cloudflare-ddns | host | ✅ Updating DNS |
| certbot | internal | ✅ Auto-renewing |
| fail2ban | host | ✅ Monitoring |
| cert-monitor | internal | ✅ Slack alert 30d before expiry |
| playwright-mcp | 9001 | ✅ Screenshots |
| darius-agent | internal | ✅ v1.1 (chaining, replay, MCP discovery) |

### K8s (Kind Cluster — Local)
- Namespace: `melanin-tech` — agent infrastructure
- Namespace: `melanin-website` — website environments
- Ready for client namespaces via `onboard-client.sh`

### Client Hosting Platform
- **Structure:** Per-client K8s namespace, isolated network
- **Custom Domains:** nginx-ingress + cert-manager (Let's Encrypt)
- **AWS Migration:** Terraform scaffold ready, swap ingress to ALB
- **Onboarding:** `k8s/clients/onboard-client.sh --slug X --domain X --image X`

---

## Repositories

| Repo | Location | Purpose |
|------|----------|---------|
| kiro-agents | Local + internal | Agent system, orchestrator, infrastructure |
| melanin-tech-website | Local | Company website (Next.js) |
| OrthoFlow | github.com/parrish727/OrthoFlow | Active project — AP automation + MFA + payments |

---

## Key Paths

```
/Users/pktech_dev/Documents/MelaninTechnologies/
├── Kiro/Projects/kiro-agents/          # Agent system
│   ├── docker/docker-compose.yml       # All services
│   ├── agents/skills/                  # Skill definitions
│   ├── agents/template/spawn.py        # Dynamic agent spawning
│   ├── AI/darius/                      # Darius orchestration agent
│   ├── k8s/clients/                    # Client hosting platform
│   └── .env                            # Secrets
├── melanin-tech-website/               # Production website source
└── LinesOfBusiness/
    └── Orthodontic_Dental/orthoflow-ai/ # OrthoFlow AI project
```
