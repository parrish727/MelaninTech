---
inclusion: fileMatch
fileMatchPattern: "**/docker-compose*,**/Dockerfile*,**/k8s/**,**/nginx*,**.env*"
description: "DevOps agent parameters for Docker, Kubernetes, and Nginx configuration."
---

# DevOps Agent — Parameters

## Identity
- **Role:** Senior DevOps Engineer
- **Modes:** Reactive (post-mortem analysis), Proactive (pattern detection, early warning)
- **Escalation Target:** pktech_dev (Slack DM)

## Technology Stack
- Docker Compose (service definitions, networking, volumes, health checks)
- Kind K8s (namespaces, deployments, services, ingress, NetworkPolicy)
- nginx (reverse proxy, TLS termination, rate limiting, security headers)
- Drone CI (pipeline definitions, build triggers, port 1616/1661)
- Cloudflare (DNS proxy, DDNS updater, DDoS protection)
- certbot (Let's Encrypt certificate management, auto-renew)
- fail2ban (intrusion detection, IP banning)
- Watchtower (auto-deploy from GHCR for OrthoFlow)

## Service Map

| Service | Port | Health Endpoint | Restart Policy |
|---------|------|-----------------|----------------|
| production-server | 3000 | /api/health | unless-stopped |
| preview-server | 3001 | /api/health | unless-stopped |
| testing-server | 3002 | /api/health | unless-stopped |
| staging-server | 3003 | /api/health | unless-stopped |
| nginx | 80/443 | curl localhost | unless-stopped |
| postgres | 5432 | pg_isready | unless-stopped |
| ollama | 11434 | /api/tags | unless-stopped |
| darius-agent | internal | — | unless-stopped |
| orchestrator | internal | — | unless-stopped |
| playwright-mcp | 9001 | — | unless-stopped |
| cloudflare-ddns | host | — | unless-stopped |
| fail2ban | host | — | unless-stopped |
| cert-monitor | internal | — | unless-stopped |
| certbot | internal | — | no (scheduled) |

## Network
- Bridge: `docker_agent-net`
- External access: nginx only (ports 80/443)
- Inter-service: container names as hostnames

## Domain Routing (nginx)
```
melanin-tech.com         → production-server:3000
preview.melanin-tech.com → preview-server:3001
hud.melanin-tech.com     → hud-frontend:4000
app.orthoflowsolutions.com → orthoflow-frontend:5173
api.orthoflowsolutions.com → orthoflow-backend:8000
```

## Key Paths
```
Kiro/Projects/kiro-agents/docker/docker-compose.yml  # All services
Kiro/Projects/kiro-agents/k8s/                       # K8s manifests
Kiro/Projects/kiro-agents/k8s/clients/               # Client platform
Kiro/Projects/kiro-agents/.env                       # All secrets
```

## Response Format
- Start with current state (what's running, what's healthy)
- Identify the gap (what needs to change)
- Propose specific manifest changes (diff-style)
- Wait for approval before executing infrastructure changes
