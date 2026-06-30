# Incident Response Policy

## Severity Levels

| Level | Definition | Response Time | Example |
|-------|-----------|---------------|---------|
| P1 — Critical | Production down, data breach, security compromise | Immediate | Site unreachable, DB exposed |
| P2 — High | Degraded service, partial outage | < 1 hour | Agent system down, slow responses |
| P3 — Medium | Non-critical feature broken | < 4 hours | Single agent failing, HUD tab broken |
| P4 — Low | Cosmetic, minor bug | Next business day | UI glitch, log noise |

## Automated Detection

| Monitor | Detects | Action |
|---------|---------|--------|
| Watchdog (30s sweep) | Agent heartbeat timeout | Restart container + Slack alert |
| HUD health monitor (60s) | Container down/exited | Slack alert: 🚨 Container Down |
| cert-monitor (daily) | TLS cert < 30 days to expiry | Slack alert |
| fail2ban | Brute force attempts | Auto-ban IP + log |
| nginx rate limiting | DDoS/abuse | 429 response + fail2ban escalation |

## Response Procedure

### P1 — Critical
1. Slack alert fires automatically
2. CEO acknowledges within 5 minutes
3. Identify: check HUD Infrastructure tab, `docker ps`, nginx logs
4. Contain: isolate affected service (`docker stop` if compromised)
5. Fix: deploy patch or rollback (`git revert` + rebuild)
6. Verify: confirm service restored via HUD
7. Post-mortem: document in ticket system within 24 hours

### P2-P4
1. Watchdog auto-restarts (up to 9 attempts)
2. If auto-recovery fails → ticket created as `failed_urgent` or `failed_backlog`
3. CEO reviews in next Slack digest (every 5 hours)
4. Fix deployed through normal change management pipeline

## Communication

- Internal: Slack channel (all alerts, status updates)
- Client-facing (OrthoFlow): Status page update if P1 affects client service
- No external communication for internal-only incidents (agent system, HUD)

## Post-Incident

1. Root cause documented in ticket log
2. Fix committed and deployed
3. Guardrail/monitoring updated to prevent recurrence
4. If security-related: rotate affected credentials per secrets-policy.md
