# Melanin Technologies — Infrastructure Standards

## Database Layer

### PostgreSQL (Required for all projects)
- **Image:** `pgvector/pgvector:pg16` (includes vector support by default)
- **max_connections:** 100 (default, increased only with justification)
- **Always enable:** `pg_stat_statements` extension for query diagnostics
- **Health check:** `pg_isready` every 5s
- **Restart policy:** `unless-stopped`
- **Volume:** Named volume for data persistence (never bind mount)

### PgBouncer (Required when >1 service connects to PostgreSQL)
- **Image:** `edoburu/pgbouncer:latest`
- **Pool mode:** `session` (supports asyncpg extended query protocol)
- **Config:** Custom `pgbouncer.ini` + `userlist.txt` mounted via volume
- **Client connections:** 1000 max
- **Server connections:** 80 max (leaves 20 for admin/migration)
- **Auth:** `trust` on internal Docker network (no external exposure)
- **Apps connect to PgBouncer**, never directly to PostgreSQL
- **Port mapping:** Expose 6432 to host for monitoring only (not to internet)

### Standard pgbouncer.ini Template
```ini
[databases]
<dbname> = host=postgres port=5432 dbname=<dbname> user=<user> password=<from_env>

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 5432
auth_type = trust
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = session
max_client_conn = 1000
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 3
max_db_connections = 80
server_reset_query = DISCARD ALL
ignore_startup_parameters = extra_float_digits,search_path
admin_users = <user>
stats_users = <user>
```

## Load Testing (Required before any production launch)
- **Tool:** k6 (open source, Grafana Labs)
- **Run:** `docker run --rm --network <project_network> grafana/k6 run /scripts/load-test.js`
- **Thresholds:** p95 < 2s, error rate < 5%
- **Schedule:** Weekly (Sunday night) + pre-launch + post-major-deploy
- **Results:** Stored in `load-test-results.json` per project

## SRE Cross-Agent Coordination (All Projects)
- SRE agent monitors ALL projects — not just kiro-agents
- DBA agent runs health checks on ALL PostgreSQL instances
- Every deploy triggers SRE post-deploy health verification
- Every project must have a `/health` endpoint (returns 200 if healthy)
- SRE correlates degradation with recent ticket activity across ALL projects

## Reliability Standards (Company-Wide)
- **Uptime target:** 99.9% per service (43 min/month downtime budget)
- **Restart policy:** `unless-stopped` on all containers
- **Health checks:** Every container must have a healthcheck defined
- **Watchtower:** All production containers labeled for auto-update
- **Self-healing:** PgBouncer reconnects, Redis reconnects, app-level circuit breakers
- **Monitoring thresholds:**
  - Container restart: alert after 3rd in 5min
  - PgBouncer utilization: alert at 70%
  - PostgreSQL connections: alert at 80%
  - Cache hit ratio: alert below 99%
  - Disk usage: alert at 80%
  - Response time p95: alert above 2s

## Network Security
- All database services on internal Docker bridge networks only
- No database ports exposed to 0.0.0.0 in production (bind to 127.0.0.1)
- PgBouncer port 6432 exposed to host for monitoring (not to internet)
- TLS 1.2+ on all public endpoints (nginx terminates)
- Inter-container communication is plain TCP (trusted network)
