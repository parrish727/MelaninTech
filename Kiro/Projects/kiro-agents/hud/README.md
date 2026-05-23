# Melanin Tech HUD — Internal Monitoring Dashboard

**URL:** hud.melanin-tech.com (internal only)
**Access:** Password-protected, team members only

---

## Overview

Real-time monitoring dashboard for all Melanin Technologies infrastructure, agents, and client projects. Provides executive visibility into system health, agent performance, and operational status.

---

## Tabs

### Executive Dashboard
- Containers running (total count)
- Memory entries (pgvector semantic memory)
- Ticket status (open, in progress, done)
- Recent tickets with agent assignment

### Agents
- All 11 agents with live status (running/stopped)
- Uptime since last restart
- Container image version

### Infrastructure
- Full container list with status
- Port mappings
- Start times
- Covers: nginx, postgres, redis, ollama, certbot, fail2ban, DDNS, all servers

---

## Architecture

```
Browser → hud.melanin-tech.com
    │
    ├── Frontend (React + Vite, port 4000)
    │   └── Polls /api/* every 30 seconds
    │
    └── Backend (FastAPI, port 8080)
        ├── Docker API → container status
        ├── PostgreSQL → tickets, memory
        └── Agent health endpoints
```

---

## Running Locally

```bash
# Backend
cd hud/backend && docker compose up -d hud

# Frontend
cd hud/frontend && npm install && npx vite --host 0.0.0.0 --port 4000
```

Access at http://localhost:4000
Default password: set in `.env` as `HUD_PASSWORD`

---

## DNS Setup (Cloudflare)

Add A record: `hud` → same IP as melanin-tech.com (DDNS handles this automatically)

---

## Security

- Password-protected login (JWT token, 24hr expiry)
- Internal use only — not linked from public site
- X-Frame-Options: DENY (prevents embedding)
- HSTS enforced
- Docker socket access (read-only for container status)

---

## Future Tabs (Roadmap)

- [ ] Costs — LLM token usage by agent/model/project
- [ ] Memory — pgvector entries, recent recalls
- [ ] Darius — sessions, chains, tool calls
- [ ] Projects — deploy status per project
- [ ] Security — fail2ban bans, cert expiry, audit log
- [ ] Clients — OrthoFlow accounts, tier, usage

## Kubernetes Migration

The HUD supports both Docker and Kubernetes infrastructure modes. Set via environment variable:

```bash
# Current (Docker)
INFRA_MODE=docker

# After K8s migration
INFRA_MODE=kubernetes
```

When in K8s mode:
- Infrastructure tab queries the Kubernetes API instead of Docker socket
- Shows pods across all managed namespaces (melanin-tech, melanin-website, orthoflow)
- Agents tab maps to K8s deployments
- No code changes needed — just flip the env var

The HUD itself can run as a K8s deployment:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hud
  namespace: melanin-tech
spec:
  replicas: 1
  selector:
    matchLabels:
      app: hud
  template:
    spec:
      serviceAccountName: hud-reader  # needs pod/service list permissions
      containers:
        - name: hud
          image: melanin-tech-hud:latest
          env:
            - name: INFRA_MODE
              value: kubernetes
```

---

*Last Updated: May 15, 2026*
