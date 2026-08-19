---
inclusion: fileMatch
fileMatchPattern: "**/postgres*,**/pg_*,**/*database*,**/*sql*"
description: "DBA agent parameters for monitoring intervals, thresholds, and database connections."
---

# DBA Agent — Parameters

## Monitoring Intervals
- Connection check: every 5 min (via HUD watchdog)
- Bloat analysis: daily (in 12hr digest)
- Full health report: on-demand via Slack

## Thresholds
- Connection utilization > 70%: 🟡 Slack alert
- Connection utilization > 90%: 🔴 Slack alert + recommend connection pooling
- Dead tuple ratio > 20%: 🟡 recommend VACUUM ANALYZE
- Idle-in-transaction > 5 connections: 🔴 potential connection leak
- Query running > 30s: 🔴 kill candidate
- DB size growth > 20% month-over-month: 🟡 capacity planning needed
- Replication lag > 30s: 🔴 (when replica configured)

## Databases
| DB | Host | Port | User | Purpose |
|----|------|------|------|---------|
| kiro | postgres | 5432 | kiro | Agent system |
| orthoflow | host.docker.internal | 5433 | orthoflow | Client SaaS (HIPAA) |
