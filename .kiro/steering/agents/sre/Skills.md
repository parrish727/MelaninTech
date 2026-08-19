---
inclusion: fileMatch
fileMatchPattern: "**/ai-sre/**,**/observability/**,**/runbooks/**,**/alerts/**,**/dashboards/**,**/health_check*"
description: "SRE agent skill definitions for incident response, diagnostics, and health checks."
---

# SRE Agent — Skills

## Database Diagnostics (PostgreSQL)

### Query Performance Analysis
```sql
-- Top queries by total execution time
SELECT query, calls, total_exec_time, mean_exec_time, rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Active queries and their state
SELECT pid, state, query_start, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY duration DESC;

-- Lock contention (blocking chains)
SELECT blocked.pid AS blocked_pid,
       blocked.query AS blocked_query,
       blocking.pid AS blocking_pid,
       blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_locks blocked_locks ON blocked.pid = blocked_locks.pid
JOIN pg_locks blocking_locks ON blocked_locks.locktype = blocking_locks.locktype
  AND blocked_locks.relation = blocking_locks.relation
  AND blocked_locks.pid != blocking_locks.pid
JOIN pg_stat_activity blocking ON blocking_locks.pid = blocking.pid
WHERE NOT blocked_locks.granted;
```

### Index Health Assessment
```sql
-- Unused indexes (candidates for removal)
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelid) DESC;

-- Sequential scans on large tables (missing indexes)
SELECT relname, seq_scan, seq_tup_read, idx_scan,
       seq_tup_read / GREATEST(seq_scan, 1) AS avg_rows_per_scan
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY seq_tup_read DESC;

-- Index bloat estimation
SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename::regclass)) AS total_size,
       pg_size_pretty(pg_relation_size(tablename::regclass)) AS table_size
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(tablename::regclass) DESC;
```

### Connection Pool Monitoring
```sql
-- Connection utilization
SELECT datname, count(*) AS connections,
       count(*) FILTER (WHERE state = 'active') AS active,
       count(*) FILTER (WHERE state = 'idle') AS idle,
       count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_txn
FROM pg_stat_activity
GROUP BY datname;

-- Connection limit vs usage
SELECT datname, numbackends,
       (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_conn
FROM pg_stat_database
WHERE datname NOT LIKE 'template%';
```

## Container Resource Diagnostics

### Per-Service Metrics
```bash
# CPU and memory per container
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"

# Container uptime and restart count
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}"

# Check for OOM kills
docker inspect $(docker ps -q) --format '{{.Name}} OOMKilled={{.State.OOMKilled}} Restarts={{.RestartCount}}' | grep -E "true|Restarts=[1-9]"
```

## Incident Investigation

### Diagnostic Workflow
1. **Identify** — Which service, when did symptoms start
2. **Correlate** — Check dependent services, recent deployments, resource usage
3. **Isolate** — Is it container-level, app-level, or infra-level
4. **Analyze** — Root cause (OOM, deadlock, config error, dependency failure)
5. **Recommend** — Specific fix with rollback plan (SRE recommends, DevOps executes)

### Log Correlation
```bash
# Gather logs around an incident timestamp
docker compose logs --since "2026-06-30T10:00:00" --until "2026-06-30T10:30:00" <service>

# Error pattern search across services
docker compose logs --tail 500 | grep -i "error\|exception\|fatal\|timeout"
```

## Capacity Planning

### Disk Usage
```bash
# Docker disk usage breakdown
docker system df -v

# Volume sizes
docker volume ls -q | xargs -I {} docker volume inspect {} --format '{{.Name}}: {{.Mountpoint}}'
du -sh /var/lib/docker/volumes/*/
```

### Growth Projections
- Track database size weekly
- Monitor Docker image storage growth
- Alert at 80% disk utilization
- Recommend cleanup (dangling images, old logs) before 90%

## SLI/SLO Tracking

### Website (www.melanin-tech.com)
| SLI | Target | Measurement |
|-----|--------|-------------|
| Availability | 99.5% monthly | GET /api/health → 200 |
| Latency P95 | < 500ms | nginx access log |
| Error rate | < 1% | 5xx / total requests |

### OrthoFlow API (api.orthoflowsolutions.com)
| SLI | Target | Measurement |
|-----|--------|-------------|
| Availability | 99.9% monthly | GET /health → 200 |
| Latency P95 | < 2000ms | FastAPI middleware timing |
| Error rate | < 0.5% | 5xx / total requests |
| Invoice processing | < 30s P95 | OCR + classification pipeline |

### HUD (hud.melanin-tech.com)
| SLI | Target | Measurement |
|-----|--------|-------------|
| Availability | 99% monthly | GET /health → 200 |
| WebSocket uptime | 99% business hours | Connection success rate |

## Post-Mortem Generation

Use template at: `A.I./ai-sre/observability/runbooks/incident_response.md`

Required sections:
- Timeline (UTC timestamps)
- Root cause (factual, no blame)
- Resolution steps taken
- Action items with owners and due dates
- Prevention measures


## Post-Deployment Health Verification

### Deployment Integrity Monitoring
After every GHCR image push, verify the live application reflects the deployed code:

```bash
# 1. API route count check — compare against expected
curl -s http://localhost:8000/openapi.json | python3 -c "
import json, sys
paths = json.load(sys.stdin)['paths']
print(f'Routes registered: {len(paths)}')
# Alert if count drops (indicates failed import / missing module)
"

# 2. Frontend bundle feature check — verify latest features are present
JSFILE=$(curl -s http://localhost:5173/ | grep -o 'assets/index-[^"]*\.js' | head -1)
MARKERS=("expected_feature_1" "expected_feature_2")
for marker in "${MARKERS[@]}"; do
  COUNT=$(curl -s "http://localhost:5173/$JSFILE" | grep -c "$marker")
  if [ "$COUNT" -eq "0" ]; then
    echo "ALERT: $marker missing from deployed frontend bundle"
  fi
done

# 3. Container age check — containers should be newer than last pipeline
PIPELINE_TIME=$(gh run list --limit 1 --json createdAt -q '.[0].createdAt')
CONTAINER_TIME=$(docker inspect orthoflow-frontend-1 --format '{{.Created}}')
# If container is OLDER than pipeline → Watchtower failed to update

# 4. Migration version check — DB should match latest migration
docker compose exec postgres psql -U orthoflow -tAc "SELECT version_num FROM alembic_version;"
# Compare against expected migration number from the codebase
```

### Alerts to Trigger
| Condition | Severity | Action |
|-----------|----------|--------|
| Container not running after deploy | 🔴 Critical | Auto-restart via `docker compose up -d` |
| Frontend bundle missing expected features | 🟡 High | Notify Slack, investigate image build |
| API route count decreased | 🔴 Critical | Rollback image, notify DevOps |
| Migration version mismatch | 🟡 High | Run `alembic upgrade head` |
| Container older than last pipeline | 🟡 High | Force pull + recreate |
| Health endpoint returns non-200 | 🔴 Critical | Check logs, restart if transient |

### Watchtower Gap Detection
Watchtower has known blind spots. SRE must verify:
1. Containers that were `docker rm`'d are NOT tracked by Watchtower
2. If a service was removed and not restarted, Watchtower won't bring it back
3. After any manual container operation, verify all expected services are running:
```bash
EXPECTED="orthoflow-backend-1 orthoflow-frontend-1 orthoflow-worker-1"
for svc in $EXPECTED; do
  if ! docker ps --format '{{.Names}}' | grep -q "$svc"; then
    echo "MISSING: $svc — restarting"
    docker compose up -d ${svc%-1}
  fi
done
```
