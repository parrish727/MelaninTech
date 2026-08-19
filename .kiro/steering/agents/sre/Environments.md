---
inclusion: fileMatch
fileMatchPattern: "**/ai-sre/**,**/observability/**"
description: "SRE agent environment definitions for monitoring and observability."
---

# SRE Agent — Environments

## Environment Detection

Environments are identified by container name prefix and port assignment:

| Environment | Identifier | Access Level |
|-------------|-----------|-------------|
| Production | `production-server:3000`, `nginx:80/443` | Read-only (metrics, logs) |
| OrthoFlow Prod | `orthoflow-*:5173/8000` | Read-only (no PII queries) |
| HUD | `hud-*:4000/8080` | Read-only |
| Preview | `preview-server:3001` | Full diagnostics |
| Testing | `testing-server:3002` | Full diagnostics + writes |
| Staging | `staging-server:3003` | Full diagnostics + writes |
| K8s Dev | `kind-*` namespaces | Full access |

## Fail-Safe Rule

If environment cannot be determined from container name, port, or database name:
**Assume production. Apply maximum restrictions.**

## Per-Environment Diagnostic Scope

### Production
- `pg_stat_statements` — allowed (metadata only)
- `pg_stat_activity` — allowed (mask query params if PII possible)
- `EXPLAIN` — allowed (plan only, no ANALYZE)
- `EXPLAIN ANALYZE` — blocked (executes query)
- Container logs — allowed (last 100 lines)
- `docker exec` — blocked
- `docker stats` — allowed

### Non-Production (Preview, Testing, Staging)
- All PostgreSQL diagnostic views — allowed
- `EXPLAIN ANALYZE` — allowed
- `VACUUM ANALYZE` — allowed with approval
- Container logs — full access
- `docker exec` — allowed for diagnostics
- `docker stats` — allowed
- Database resets — allowed (testing only)

## Cross-Environment Comparisons

When diagnosing production issues, compare against staging/testing:
- Same query, different environment → isolate data volume vs. code issue
- Same load, different config → isolate configuration problem
- Same code, different data → isolate data-dependent bug
