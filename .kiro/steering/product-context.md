# Melanin Technologies Inc. — Product Context

## Company

Black-owned technology consulting & development firm, incorporated in Wisconsin, operating from Charlotte, NC.

**Revenue Streams:**
1. SaaS — OrthoFlow AI
2. Software-in-a-Service — Custom builds + managed hosting
3. Infrastructure-as-a-Service — Managed hosting for SMBs
4. Consulting — Strategy, architecture, contract development

## Project Map

### Active Products

| Project | Path | Stack | Status |
|---------|------|-------|--------|
| melanin-tech-website | `melanin-tech-website/` | Next.js 16, Tailwind, Framer Motion | Live (www.melanin-tech.com) |
| Kiro Agents | `Kiro/Projects/kiro-agents/` | Python, FastAPI, Docker, Slack | Live (internal) |
| OrthoFlow AI | `LinesOfBusiness/Orthodontic_Dental/orthoflow-ai/OrthoFlow/` | FastAPI, React+Vite, PostgreSQL, Redis, MinIO, Ollama | Live (app.orthoflowsolutions.com) |
| HTC App | `LinesOfBusiness/Held_Together_Caregiving/htc-app/` | FastAPI, React+Vite, Tailwind | In Development |
| Music Catalogue | `music-catalogue-system/` | FastAPI, React+Vite, Tailwind, PostgreSQL | Prototype |

### Infrastructure

| Component | Path | Purpose |
|-----------|------|---------|
| Docker Compose | `Kiro/Projects/kiro-agents/docker/docker-compose.yml` | All production services |
| K8s Manifests | `Kiro/Projects/kiro-agents/k8s/` | Client hosting platform |
| AI/SRE Runbooks | `A.I./ai-sre/` | Observability, automation, incident response |
| Governance | `Kiro/Projects/kiro-agents/governance/` | Compliance, security policies |

### Documentation

| Doc | Path | Audience |
|-----|------|----------|
| Internal Onboarding | `MelaninDocs/Onboarding/` | Team |
| Client Proposals | `MelaninDocs/ClientProposal/` | Sales |
| Finance | `MelaninDocs/Finance/` | Internal (read-only) |
| Business Docs | `BusinessDocs/` | Corporate records |

## Hosting

- Self-hosted Mac Pro, Google Fiber, Cloudflare proxy
- Docker Compose (30+ containers) on docker_agent-net bridge
- TLS via Let's Encrypt (certbot auto-renew)
- Kind K8s cluster for client isolation

## Conventions

- Python: type hints on all signatures, FastAPI + Pydantic validation
- TypeScript: strict mode, no `any`
- Frontend: Tailwind CSS, Lucide icons, Framer Motion animations
- Containers: Docker Compose for dev/prod, K8s for multi-tenant
- Secrets: never in code, always via .env (gitignored)
- LLM provider: Anthropic Claude only (no OpenAI)
