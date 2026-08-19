---
inclusion: fileMatch
fileMatchPattern: "**/docker-compose*,**/Dockerfile*,**/k8s/**,**/nginx*,**/deploy*,**/ci*,**.drone*"
description: "DevOps agent skill definitions for container orchestration and CI/CD."
---

# DevOps Agent — Skills

## Container Lifecycle Management

### Health Assessment
```bash
# Full stack status
docker compose -f Kiro/Projects/kiro-agents/docker/docker-compose.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# Individual container inspection
docker inspect <container> --format '{{.State.Status}} | Exit: {{.State.ExitCode}} | OOMKilled: {{.State.OOMKilled}} | Restarts: {{.RestartCount}}'

# Resource usage
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"
```

### Service Recovery
1. Check container state and exit code
2. Review last 100 log lines with timestamps
3. Check disk space (`df -h /var/lib/docker`)
4. Check dependent services (postgres, ollama, redis)
5. If transient (exit 137 OOM or exit 0 clean), restart via compose
6. If persistent (exit 1 with app error), escalate to Code Agent

### Deployment
```bash
# Non-production rebuild and deploy
docker compose -f docker/docker-compose.yml up -d --build <service>

# Production (requires approval)
docker compose -f docker/docker-compose.yml pull production-server
docker compose -f docker/docker-compose.yml up -d production-server
```

## Kubernetes Operations

### Namespace Management
```bash
# List namespaces and resources
kubectl get ns
kubectl get all -n <namespace>

# Client onboarding (HIGH-IMPACT — double approval)
./k8s/clients/onboard-client.sh --slug <name> --domain <domain> --image <image>
```

### Manifest Validation
```bash
# Dry-run validation before applying
kubectl apply --dry-run=client -f <manifest.yaml>

# Diff against running state
kubectl diff -f <manifest.yaml>
```

## nginx Operations

### Configuration Validation
```bash
# Test config syntax
docker exec nginx nginx -t

# Reload without downtime (after validation passes)
docker exec nginx nginx -s reload
```

### TLS Certificate Status
```bash
# Check certificate expiry
docker exec nginx openssl x509 -in /etc/letsencrypt/live/melanin-tech.com/fullchain.pem -noout -enddate

# Force renewal (rarely needed — certbot auto-renews)
docker compose run certbot renew --force-renewal
```

## Infrastructure Drift Detection

Compare running state against declared state:
1. `docker compose config` → expected state
2. `docker ps` → actual running state
3. Diff container images, ports, env vars, volumes
4. Report any drift with remediation steps

## CI/CD (Drone CI)

### Pipeline Monitoring
- Drone UI: localhost:1616
- Pipeline logs: `drone log <repo> <build> <stage> <step>`
- Trigger rebuild: `drone build create <repo>`

## Cloudflare / DNS

### DDNS Verification
```bash
# Check current public IP vs Cloudflare record
curl -s ifconfig.me
# Compare with Cloudflare API response in DDNS container logs
docker logs cloudflare-ddns --tail 5
```

## Self-Healing Mechanisms (Passive — Already Running)

| Mechanism | What It Does | Agent Action |
|-----------|-------------|--------------|
| `restart: unless-stopped` | Auto-restarts crashed containers | Monitor, don't duplicate |
| Watchtower | Auto-deploys OrthoFlow from GHCR | Verify after pull |
| certbot | Auto-renews TLS 30 days before expiry | Monitor cert-monitor alerts |
| Cloudflare DDNS | Updates A record every 5 min | Verify IP matches |
| fail2ban | Bans brute-force IPs | Review ban list periodically |


## Post-Deployment Verification (MANDATORY after every merge to main)

### Image Integrity Check
After every CI pipeline completion + Watchtower pull, verify the deployed image contains the expected code:
```bash
# 1. Verify the running image SHA matches what CI built
docker inspect <container> --format '{{.Image}}' | head -c 12
# Compare against the SHA reported in the GitHub Actions build log

# 2. Verify frontend bundle contains expected features (string check)
JSFILE=$(curl -s http://localhost:<port>/ | grep -o 'assets/index-[^"]*\.js' | head -1)
curl -s "http://localhost:<port>/$JSFILE" | grep -c "<expected_feature_marker>"
# If 0 → the deploy did NOT include the latest code. Investigate.

# 3. Verify backend routes are registered
curl -s http://localhost:<port>/openapi.json | python3 -c "import json,sys; paths=json.load(sys.stdin)['paths']; print(f'{len(paths)} routes registered')"

# 4. Verify container was recreated AFTER the image was pulled
docker inspect <container> --format '{{.Created}}' 
# Must be AFTER the pipeline completion timestamp
```

### Merge Completeness Check
Before marking a PR as "deployed", verify ALL commits in the PR branch are included in the merge:
```bash
# List commits on the feature branch that are NOT on main
git log main..<branch> --oneline
# If any commits exist → they were pushed AFTER the merge. Cherry-pick or open new PR.
```

### Container Liveness After Deploy
```bash
# Verify all expected containers are running (not just built)
docker compose ps --format "{{.Name}}: {{.Status}}" | grep -v "Up"
# Any line that appears → container is NOT running. Restart it.

# Watchtower doesn't restart removed containers — only updates running ones.
# If a container was manually removed, Watchtower will NOT bring it back.
# Fix: docker compose up -d <service>
```

### Rollback Procedure
If post-deploy verification fails:
1. `docker compose pull <service>` with previous tag
2. `docker rm -f <container> && docker compose up -d <service>`
3. Notify via Slack: deployment rolled back
4. Escalate to AI Engineering agent for code fix

### Known Pitfalls
- **Watchtower only updates running containers** — if a container was `docker rm`'d, Watchtower ignores it
- **PR auto-merge timing** — if commits are pushed after CI passes but before merge completes, those commits are excluded
- **Docker name conflicts** — always `docker rm -f` before `docker compose up -d` if container name is stuck
- **Image caching** — `docker compose pull` before `up -d` to ensure latest GHCR image
