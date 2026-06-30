# Melanin Technologies — Governance as Code

## Overview

All security, compliance, and operational policies are defined as code, version-controlled, and enforced automatically. No policy exists only as a document — every rule has a corresponding enforcement mechanism.

---

## Policy Enforcement Layers

| Layer | Mechanism | Location |
|-------|-----------|----------|
| Agent behavior | Steering rules + guardrail hook | `.kiro/steering/`, `.kiro/hooks/` |
| Container security | Docker Compose directives | `docker/docker-compose.yml` |
| Network security | nginx + fail2ban + Cloudflare | `docker/nginx/`, `docker/fail2ban/` |
| Infrastructure isolation | K8s namespaces + NetworkPolicies | `k8s/` |
| Secret management | .env + Docker secrets (never in code) | `.env`, `.gitignore` |
| Access control | JWT + TOTP 2FA + RBAC | HUD backend, OrthoFlow backend |
| Compliance scanning | Guardrail hook (pre-merge) | `.kiro/hooks/guardrail-check.yaml` |
| Audit trail | PostgreSQL audit logs | `AuditLog` table, ticket log field |
| TLS/Encryption | certbot auto-renewal + HSTS | nginx configs, cert-monitor |
| Intrusion detection | fail2ban + Slack alerts | `docker/fail2ban/`, HUD watchdog |

---

## Policy Files in This Directory

| File | Purpose |
|------|---------|
| `README.md` | This file — governance overview |
| `secrets-policy.md` | Secret management and rotation rules |
| `access-control-policy.md` | Who/what can access which services |
| `network-policy.md` | Network segmentation and firewall rules |
| `data-protection-policy.md` | Encryption, PHI handling, backup/retention |
| `change-management-policy.md` | How changes flow from proposal to production |
| `incident-response-policy.md` | What happens when something breaks |
| `compliance-checklist.md` | HIPAA, SOC 2, CMS controls mapped to implementation |

---

## Automated Enforcement

Policies without automation are suggestions. Every policy below has a code-level enforcement:

```
Policy                    → Enforcement
─────────────────────────────────────────────────────────
No secrets in code        → guardrail-check.yaml scans for patterns
No destructive commands   → base_agent.py _guard_proposal()
No OpenAI models          → base_agent.py _guard_model()
No path traversal         → base_agent.py _guard_path() + os.path.realpath
Container least-privilege → cap_drop: ALL, read_only: true, tmpfs: /tmp
Rate limiting             → nginx limit_req_zone (30r/m general, 5r/m contact)
Brute force protection    → fail2ban (10 attempts → 1hr ban)
TLS everywhere            → HTTP→HTTPS redirect, HSTS preload
Cert expiry alerting      → cert-monitor container (30-day Slack alert)
Audit logging             → AuditLog table on every data access
Human approval gate       → Slack approval flow (approve/modify/reject)
```
