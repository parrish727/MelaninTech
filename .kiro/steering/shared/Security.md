---
inclusion: auto
description: "Shared security standards for all agents covering secrets management and access controls."
---

# Shared — Security Standards

## Universal Security Rules (All Agents)

### Secrets Management
- **Location:** `Kiro/Projects/kiro-agents/.env` (gitignored)
- **K8s Secrets:** Created from .env via `kubectl create secret generic`
- **Never in code:** No credentials in source files, Dockerfiles, compose files, or agent context
- **Reference by name:** When discussing secrets, use variable name (e.g., `ANTHROPIC_API_KEY`), never the value
- **Rotation:** If a secret may be exposed, rotate immediately and notify pktech_dev

### Authentication
| Service | Auth Method | Details |
|---------|-------------|---------|
| HUD | Password + TOTP 2FA | hud.melanin-tech.com |
| OrthoFlow | JWT + Practice Scoping | SMS OTP MFA for admin |
| Slack Bot | Bot Token + Signing Secret | Webhook verification |
| GitHub | Personal Access Token | GHCR pulls, MCP server |
| Cloudflare | API Token | DDNS updates only |

### Network Security
- **External access:** nginx only (ports 80/443)
- **Internal communication:** Docker bridge network (container names as hostnames)
- **Rate limiting:** 10 req/s per IP (burst 20) at nginx
- **Security headers:** HSTS, CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff
- **DDoS protection:** Cloudflare proxy (orange cloud enabled)
- **Intrusion detection:** fail2ban monitoring nginx and SSH

### Container Security
- Non-root execution where possible
- Read-only filesystems where applicable
- No privileged mode
- Minimal base images (alpine preferred)
- No package managers in production images (multi-stage builds)
- Health checks on all services

### HIPAA Compliance (OrthoFlow)
- Audit logging on all patient data access (never disable)
- ClamAV virus scanning on file uploads (never disable)
- Encrypted connections (TLS in transit)
- Practice-scoped data isolation (JWT claims)
- No patient data in logs, agent context, or error messages

## Governance Policy References

| Policy | Path | Governs |
|--------|------|---------|
| Access Control | `governance/access-control-policy.md` | Who can access what |
| Data Protection | `governance/data-protection-policy.md` | Data handling rules |
| Secrets | `governance/secrets-policy.md` | Credential management |
| Incident Response | `governance/incident-response-policy.md` | Breach procedures |
| Change Management | `governance/change-management-policy.md` | Change approval flow |
| Network | `governance/network-policy.md` | Network access rules |
| BAA | `governance/baa-policy.md` | Business associate agreements |
| DR | `governance/dr-test-procedure.md` | Disaster recovery |
| Pentest | `governance/pentest-procedure.md` | Penetration testing |

## Incident Response (Security)

If a security incident is suspected:
1. **Contain** — Isolate affected container(s) without destroying evidence
2. **Preserve** — Capture logs before rotation
3. **Notify** — Alert pktech_dev immediately via Slack
4. **Investigate** — Determine scope and data impact
5. **Remediate** — Fix vulnerability, rotate credentials
6. **Document** — Post-mortem with prevention measures
