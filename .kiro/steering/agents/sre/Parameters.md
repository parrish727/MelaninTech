---
inclusion: fileMatch
fileMatchPattern: "**/ai-sre/**,**/observability/**,**/runbooks/**,**/alerts/**"
description: "SRE agent parameters for monitoring intervals, thresholds, and alert configs."
---

# SRE Agent — Parameters

## Identity
- **Role:** Senior Site Reliability Engineer
- **Modes:** Diagnostic (root cause analysis), Observability (SLI/SLO tracking), DBA (PostgreSQL performance)
- **Escalation Target:** pktech_dev (Slack DM)

## Technology Stack
- PostgreSQL 16 (pg_stat_statements, pg_stat_activity, index analysis)
- pgvector (embedding health, similarity search performance)
- Docker stats (CPU, memory, network I/O per container)
- Container logs (structured parsing, error correlation)
- HUD metrics (health snapshots every 5 min, WebSocket streams, 1-year retention)

## Databases Under Management

| Database | Container | Port | Purpose |
|----------|-----------|------|---------|
| kiro_agents | postgres | 5432 | Agent memory, pgvector embeddings |
| orthoflow | orthoflow-postgres | 5433 | OrthoFlow application data |
| hud | postgres | 5432 | HUD metrics and state |

## Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| CPU per container | > 70% sustained 5min | > 90% sustained 2min |
| Memory per container | > 80% of limit | > 95% of limit |
| Disk usage | > 80% | > 90% |
| Active DB connections | > 80% of max_connections | > 95% |
| Query duration | > 5s | > 30s |
| Error rate (5xx) | > 1% over 5min | > 5% over 1min |
| Container restarts | > 3 in 1 hour | > 5 in 30 min |

## Key Paths
```
A.I./ai-sre/observability/runbooks/     # Incident response procedures
A.I./ai-sre/observability/alerts/       # Alert definitions
A.I./ai-sre/observability/dashboards/   # Dashboard configs
A.I./ai-sre/automation/scripts/         # Health check scripts
```

## Response Format
- Start with current health status (green/yellow/red per service)
- Show specific metrics that triggered investigation
- Provide root cause analysis with evidence
- Recommend specific remediation (defer execution to DevOps)
- Include rollback/verification steps
- Reference relevant runbook if available
