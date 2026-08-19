---
inclusion: fileMatch
fileMatchPattern: "**/docker-compose*,**/Dockerfile*,**/k8s/**,**/nginx*,**/certbot*,**/fail2ban*,**/cloudflare*,**/deploy*"
description: "DevOps agent guardrails for safe infrastructure changes and deployment."
---

# DevOps Agent — Guardrails

## Hard Constraints (Never Bypass)

### Infrastructure Protection
- **Production is read-only** — no direct modification to production-server (port 3000) or nginx TLS
- **No direct container deployments** — all changes go through Docker Compose manifests committed to git
- **No port forwarding changes** — 80/443 routing is static, managed at the router level
- **No Cloudflare DNS manual edits** — DDNS updater container is the sole DNS writer
- **No certbot manual operations** — certificate lifecycle is fully automated

### Deployment Safety
- **No force push** — ever, on any branch
- **No git rebase on shared branches** — use merge commits
- **No `docker system prune`** — could remove volumes with persistent data
- **No `docker rm -f` on production containers** — use `docker compose down` for controlled shutdown
- **No K8s namespace deletion without backup verification** — client data could be lost

### Secrets
- **No credentials in Dockerfiles** — use build args or runtime env only
- **No secrets in container labels or compose comments**
- **No `.env` files committed** — always gitignored
- **No hardcoded ports** — use environment variable interpolation

## Soft Constraints (Require Approval)

### Single Approval
- Restarting non-production containers (preview, testing, staging)
- Adding new services to docker-compose.yml (dev/staging only)
- Modifying K8s manifests for melanin-tech or melanin-website namespaces
- Updating Drone CI pipeline definitions
- Changing container resource limits

### Double Approval + Escalation
- Any operation touching production-server or nginx
- Docker Compose changes affecting TLS or authentication
- K8s client namespace creation or deletion (onboard-client.sh)
- Bulk container restarts (3+ services)
- fail2ban rule modifications
- Network policy changes on docker_agent-net

## Environment Rules

| Environment | Container Pattern | Allowed Operations |
|-------------|-------------------|-------------------|
| Production | production-server, nginx, certbot | Read-only (logs, health, inspect) |
| Preview | preview-server | Full lifecycle (restart, rebuild, logs) |
| Testing | testing-server | Full lifecycle, database reset allowed |
| Staging | staging-server | Full lifecycle, config experiments allowed |
| K8s (Kind) | kind-* | Full access, namespace CRUD |

## Fail-Safe
If environment cannot be determined from container name or port, **assume production** and apply maximum restrictions.
