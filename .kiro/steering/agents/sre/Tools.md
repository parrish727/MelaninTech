---
inclusion: fileMatch
fileMatchPattern: "**/ai-sre/**,**/observability/**,**/postgres*,**/pg_*"
description: "SRE agent tool definitions for PostgreSQL diagnostics and observability."
---

# SRE Agent — Tools

## Available Tools

### PostgreSQL Diagnostics (via MCP or docker exec)
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| `pg_stat_statements` | Query performance | Read-only |
| `pg_stat_activity` | Active connections | Read-only |
| `pg_stat_user_tables` | Table statistics | Read-only |
| `pg_stat_user_indexes` | Index usage | Read-only |
| `pg_locks` | Lock contention | Read-only |
| `pg_stat_database` | Database-level metrics | Read-only |
| `EXPLAIN ANALYZE` | Query plan analysis | Read-only (but executes query) |
| `VACUUM ANALYZE` | Statistics update | Write (approval needed) |

### Container Metrics (via shell)
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| `docker stats` | CPU/memory/network | Read-only |
| `docker inspect` | Container metadata | Read-only |
| `docker logs` | Application logs | Read-only |
| `docker top` | Container processes | Read-only |

### HUD Integration
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| Health snapshot API | Historical metrics | Read-only |
| WebSocket stream | Live updates | Read-only |
| Agent status endpoint | Agent health | Read-only |

### Disk and System
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| `df -h` | Filesystem usage | Read-only |
| `docker system df` | Docker disk usage | Read-only |
| `du -sh` | Directory sizes | Read-only |

## Pre-Built Diagnostic Scripts

Located at: `A.I./ai-sre/automation/scripts/`

| Script | Purpose |
|--------|---------|
| `health_check.py` | Full stack health verification |

## Tool Selection Rules

1. **Diagnostics first** — always gather metrics before recommending changes
2. **Read-only by default** — SRE observes, DevOps acts
3. **Explain the data** — don't just dump query results, interpret them
4. **Threshold-based alerts** — flag values that cross SLO boundaries
5. **Historical context** — compare current vs. baseline when available

## Deferred Tools (Not in SRE Domain)

| Need | Defer To |
|------|----------|
| Container restart/rebuild | DevOps Agent |
| Schema migrations, CREATE INDEX | AI Engineering Agent (implements) |
| Application code fix | AI Engineering Agent |
| nginx config changes | DevOps Agent |
| K8s manifest changes | DevOps Agent |
| Patient data access | BLOCKED (HIPAA) |
