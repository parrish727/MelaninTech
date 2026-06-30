# Access Control Policy

## Principle
Least privilege. Every service, agent, and user gets only the access required for its function.

## Service Access Matrix

| Service | Who Can Access | Auth Method | Network |
|---------|---------------|-------------|---------|
| HUD (hud.melanin-tech.com) | CEO only | Password + TOTP 2FA | Public (TLS) |
| Orchestrator (Slack) | CEO via Slack | Slack OAuth + signing secret | Slack Socket Mode |
| Agent APIs (:8000) | Orchestrator only | Internal network | agent-net (no port exposure) |
| PostgreSQL (:5432) | Orchestrator, HUD, agents | DSN credential | agent-net only |
| Ollama (:11434) | Agents, workers | No auth (internal) | agent-net only |
| OrthoFlow app | Practice users | JWT + SMS OTP MFA | Public (TLS) |
| OrthoFlow API | Frontend only | JWT Bearer | Public (TLS) |
| Docker socket | Orchestrator, HUD, deploy-agent | Unix socket mount | Host only |
| nginx (80/443) | Public | N/A (reverse proxy) | Public |
| MCP server (:9000) | Agents only | No auth (internal) | agent-net only |

## Docker Volume Permissions

| Agent | Projects | Website | OrthoFlow | Docker Socket |
|-------|----------|---------|-----------|---------------|
| orchestrator | rw | rw | rw | ✅ |
| frontend-agent | rw | rw | rw (frontend) | ❌ |
| backend-agent | rw | ❌ | rw (backend) | ❌ |
| deploy-agent | ro | ro | ❌ | ✅ |
| support-agent | ro | ❌ | ❌ | ❌ |
| code-agent | ro | ❌ | ❌ | ❌ |
| file-agent | rw | ❌ | ❌ | ❌ |
| scaffold-agent | rw | ❌ | ❌ | ❌ |
| qa-agent | ro | ro | ro | ❌ |
| hud | ❌ | ❌ | ❌ | ✅ (read) |

## Container Security Directives

All standard agents enforce:
```yaml
cap_drop: [ALL]        # Drop all Linux capabilities
read_only: true        # Read-only root filesystem
tmpfs: [/tmp]          # Writable temp only in tmpfs (not persisted)
```

## User Roles (OrthoFlow)

| Role | Permissions |
|------|-------------|
| owner | Full access, billing, user management |
| manager | Approve invoices, view reports, manage staff |
| bookkeeper | Upload invoices, view own submissions |

## Enforcement
- Network isolation via Docker bridge network (no port exposure for internal services)
- K8s NetworkPolicies (when migrated) — deny-all default, explicit allow per namespace
- JWT expiry: 24hr (HUD), 1hr (OrthoFlow)
- Failed login lockout: fail2ban (10 attempts → 1hr ban)
