# Disaster Recovery Test Procedure

**Frequency:** Quarterly
**Owner:** CEO
**Last Conducted:** Not yet (first test scheduled Q3 2026)

---

## Recovery Targets

| Metric | Target | Current Capability |
|--------|--------|-------------------|
| RTO (Recovery Time Objective) | < 4 hours | ~2 hours (container rebuild from git) |
| RPO (Recovery Point Objective) | < 24 hours | Daily PostgreSQL backups |
| Data Loss Tolerance | 0 for tickets/memory, 24hr for analytics | Daily backup covers this |

---

## Disaster Scenarios

### Scenario 1: Hardware Failure (Mac Pro dies)
**Recovery:**
1. Provision new machine (or AWS EKS via `aws-migration.yaml`)
2. Clone repos from GitHub (MelaninTech + OrthoFlow)
3. Restore `.env` from secure backup
4. Restore PostgreSQL from latest backup
5. `docker compose up -d` — all services rebuild from Dockerfiles
6. Update Cloudflare DNS to new IP
7. Verify via HUD

**Test procedure:**
- [ ] Verify git repos are current on GitHub
- [ ] Verify `.env` backup exists and is accessible
- [ ] Verify PostgreSQL backup is restorable (test restore to temp DB)
- [ ] Time a full `docker compose build` from scratch
- [ ] Verify DNS update propagates within 5 minutes

### Scenario 2: Database Corruption
**Recovery:**
1. Stop affected services
2. Restore PostgreSQL from latest daily backup
3. Restart services
4. Verify data integrity (ticket count, memory entries, client data)

**Test procedure:**
```bash
# Create test backup
docker exec docker-postgres-1 pg_dump -U kiro kiro > /tmp/kiro_backup_test.sql

# Verify backup is valid (restore to temp database)
docker exec docker-postgres-1 psql -U kiro -c "CREATE DATABASE kiro_test;"
docker exec -i docker-postgres-1 psql -U kiro kiro_test < /tmp/kiro_backup_test.sql

# Verify row counts match
docker exec docker-postgres-1 psql -U kiro -c "SELECT 'tickets', COUNT(*) FROM tickets UNION ALL SELECT 'task_memory', COUNT(*) FROM task_memory UNION ALL SELECT 'contracts', COUNT(*) FROM contracts;" kiro_test

# Cleanup
docker exec docker-postgres-1 psql -U kiro -c "DROP DATABASE kiro_test;"
```

### Scenario 3: ISP Outage (Google Fiber down)
**Recovery:**
1. Cloudflare DNS shows stale IP (no auto-update during outage)
2. If extended (>1hr): failover to mobile hotspot or AWS
3. Services remain running locally — only external access affected

**Test procedure:**
- [ ] Verify all services function on localhost during simulated DNS failure
- [ ] Verify HUD accessible at localhost:4000
- [ ] Document mobile hotspot failover steps

### Scenario 4: Container Image Corruption
**Recovery:**
1. `docker compose build --no-cache <service>` — rebuild from Dockerfile
2. All source is in git — no state in images
3. Restart: `docker compose up -d <service>`

**Test procedure:**
- [ ] Delete a non-critical image: `docker rmi docker-code-agent`
- [ ] Rebuild: `docker compose build code-agent`
- [ ] Verify agent responds to health check

### Scenario 5: Security Breach (compromised credentials)
**Recovery:**
1. Rotate ALL secrets immediately (see `governance/secrets-policy.md`)
2. Revoke old tokens at each provider
3. Review audit logs for unauthorized access
4. Rebuild containers (ensure no persistence of compromised state)
5. Notify affected clients if PHI was accessed (per BAA, within 30 days)

**Test procedure:**
- [ ] Practice rotating one non-critical secret (e.g., HUD_JWT_SECRET)
- [ ] Verify services restart cleanly with new secret
- [ ] Verify old JWT tokens are rejected

---

## Backup Verification Checklist (Run Quarterly)

- [ ] PostgreSQL (kiro): backup exists, restorable, row counts match
- [ ] PostgreSQL (orthoflow): backup exists, restorable, practice data intact
- [ ] Git repos: all pushed to GitHub, no uncommitted critical changes
- [ ] `.env` file: secure backup accessible, matches running config
- [ ] Docker images: all rebuildable from Dockerfiles (no manual state)
- [ ] DNS: Cloudflare records correct, DDNS container running
- [ ] TLS certs: auto-renewal working, >30 days until expiry

---

## Automated Backup Script

```bash
#!/usr/bin/env bash
# Run daily via cron or container scheduler
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/backups/$DATE"
mkdir -p "$BACKUP_DIR"

# PostgreSQL dumps
docker exec docker-postgres-1 pg_dump -U kiro kiro > "$BACKUP_DIR/kiro.sql"
docker exec orthoflow-postgres-1 pg_dump -U orthoflow orthoflow > "$BACKUP_DIR/orthoflow.sql"

# Compress
gzip "$BACKUP_DIR"/*.sql

echo "Backup complete: $BACKUP_DIR"
```

---

## Results Log

| Date | Scenario Tested | Result | Issues Found | Resolved |
|------|----------------|--------|--------------|----------|
| — | — | — | — | — |

---

*Next scheduled: Q3 2026*
