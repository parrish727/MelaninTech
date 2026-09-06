# Infrastructure Session — Post-Migration Bring-Up & Hardening

## Date: 2026-09-05 (migration complete 2026-08-23)

---

## What Happened This Session

### 1. Post-Migration Infrastructure Bring-Up (2026-08-23)

All containers came back online cleanly after migration. One issue found and fixed during E2E validation:

**ArtistOS frontend (unhealthy)**
- `artistos-frontend` container showed `(unhealthy)` — 9 consecutive failing health checks
- Root cause: `Dockerfile` healthcheck used `wget http://localhost/` — on `nginx:alpine`, `localhost` resolves to IPv6 (`::1`) but nginx only binds IPv4
- Fix: changed healthcheck to `wget http://127.0.0.1/`
- File: `LinesOfBusiness/ArtistOS/artistos-app/frontend/Dockerfile`
- Container rebuilt, healthcheck now passes

**Full E2E results (all LOBs):**

| LOB | Services Verified | Status |
|-----|-------------------|--------|
| ArtistOS | API (8200), Frontend (5175), Postgres (5434), Redis (6381), MinIO (9200), Brochure (3030/8030) | ✅ All healthy |
| OrthoFlow | Backend (8000), Frontend (5173), Postgres (5433), PgBouncer (6432), Redis (6380), MinIO (9100), Brochure (3020/8020), Marketing (3010), Ollama (11435), LiveKit (7880) | ✅ All healthy |
| Parcel Pro | Martin (3001), Postgres (5435), Redis (6382) | ✅ All healthy |
| HTC | Frontend (5174), Backend (8001) | ✅ All healthy |
| Main Infra | Nginx (80/443), PgBouncer (6433), Vaultwarden, Ollama, Cloudflare DDNS, Certbot, Fail2ban | ✅ All healthy |

---

### 2. melanin-tech.com 503 Investigation (2026-08-31 ~23:00)

**Reported:** Brief 503 on www.melanin-tech.com

**Finding:** melanin-tech.com itself was fine — upstream `production-server:3000` had 0 restarts, never OOM-killed. The 503 was a momentary blip during broader network churn.

**Actual problem discovered in nginx logs:** OrthoFlow app/api subdomains were intermittently failing with:
```
connect() to [fdc4:f303:9324::254]:8000 failed (101: Network unreachable)
server: api.orthoflowsolutions.com
```

**Root cause:** `host.docker.internal` resolves to both `192.168.65.254` (IPv4 ✓) and `fdc4:f303:9324::254` (IPv6 ✗) inside the nginx container. Nginx was selecting IPv6, which is unreachable on the Docker bridge, causing upstream disabled → 503. Same IPv4/IPv6 class of bug as the ArtistOS healthcheck.

---

### 3. OrthoFlow Nginx Hardening (2026-09-05)

**Fix applied:** Replaced `host.docker.internal` proxy path with direct container-to-container routing.

**docker-compose.yml change (OrthoFlow repo):**
- Added `docker_agent-net` as external network
- `backend` and `frontend` now attached to both `orthoflow` (internal data layer) and `agent-net` (nginx-facing)
- Data layer (postgres, redis, minio, ollama, pgbouncer, livekit, worker) stays isolated on `orthoflow` only
- Host ports 8000/5173 no longer used by nginx — bypass path closed

**orthoflow.conf change (MelaninTech repo):**
- `proxy_pass http://host.docker.internal:8000/5173` → named `upstream` blocks with container DNS
- Added `keepalive 32` (API) / `keepalive 16` (app) for connection reuse under load
- Added `proxy_set_header Connection ""` + `proxy_http_version 1.1` to activate keepalive correctly
- Added rate limiting: 60r/m general, 10r/m auth endpoints with burst limits
- Added `limit_conn` per-IP (30 concurrent) on both servers
- Full TLS cipher suite, `ssl_session_cache shared:OF_SSL:10m`, `ssl_session_tickets off`
- Added missing security headers to all blocks: `Referrer-Policy`, `Permissions-Policy`, HSTS `preload`
- Separate auth location block (`/api/v1/auth|login|register|token`) with tight rate limit
- Static asset cache headers on app frontend

**Both changes are live** — nginx reloaded with zero downtime, confirmed via container-to-container ping and public route checks.

---

### 4. OrthoFlow CI Pipeline Fix (2026-09-05)

**Failing run:** `32614203399` on `main` (2026-08-23) — build job failed at Trivy Scan (Backend)

**Finding:** Trivy flagged 4 OS-level CVEs in `python:3.12-slim` base image:
- `CVE-2026-14456` — openssl DoS via QUIC (not applicable, we don't run QUIC)
- `CVE-2026-53612/53613/53614` — util-linux TOCTOU in SUID mount (not applicable, containers don't use SUID mount)

These were NOT in `.trivyignore` yet. The `msgpack` and `setuptools` entries were already covered.

**Fix applied:**
1. Added `apt-get update && apt-get upgrade -y` to `backend/Dockerfile` — pulls OS patches when Debian backport is available
2. Added all 4 CVEs to `backend/.trivyignore` with documented reasoning and review dates as fallback

---

### 5. Branch / PR Cleanup (2026-09-05)

**MelaninTech repo** — now clean:
- PR #6 `fix/orthoflow-nginx-direct-upstream` → merged to main, branch deleted
- `feat/ci-failure-autofix-pipeline` → deleted (0 commits ahead of main, stale)
- Only `main` remains

**OrthoFlow repo** — cleaned up:
- PR #8 `fix/nginx-upstream-direct-network` → merged to main, branch deleted
- 10 fully-merged stale branches deleted
- 2 branches retained (unmerged work, not yet PRed):
  - `feature/multi-specialty-sprint-a` — 1 commit: frontend specialty picker, patient badges, restorative chart tab
  - `feature/phase1-clinical` — 1 commit: clinical seed data script for QA testing

---

## Current Repo Branch State

### parrish727/MelaninTech
| Branch | Status |
|--------|--------|
| `main` | Active |

### parrish727/OrthoFlow
| Branch | Status | Notes |
|--------|--------|-------|
| `main` | Active | |
| `production` | Active | Tracks production deploys |
| `feature/multi-specialty-sprint-a` | Unmerged | Frontend: specialty picker, patient badges, restorative chart tab |
| `feature/phase1-clinical` | Unmerged | Clinical seed data script |

---

## Current Infrastructure State (as of 2026-09-05)

### Network Architecture (post-fix)
```
nginx (docker_agent-net)
  ├── production-server:3000        (melanin-tech.com)
  ├── orthoflow-backend-1:8000      (api.orthoflowsolutions.com) ← NOW DIRECT
  ├── orthoflow-frontend-1:3000     (app.orthoflowsolutions.com) ← NOW DIRECT
  ├── orthoflow-marketing:3000      (orthoflowsolutions.com)
  ├── artistos-api:8000             (future: api.calistrocreative.com)
  ├── artistos-frontend:80          (future: os.calistrocreative.com)
  ├── artistos-brochure-api/frontend (brochure.calistrocreative.com)
  └── orthoflow-brochure-*          (brochure.orthoflowsolutions.com)
```

### Pending Items Carried Forward

1. **OrthoFlow `feature/multi-specialty-sprint-a`** — frontend work needs PR + review before merge
2. **OrthoFlow `feature/phase1-clinical`** — seed script needs PR + review before merge
3. **Trivy pipeline green state** — next push to main will confirm the apt-get upgrade + trivyignore fix resolves the scan failure
4. **ArtistOS production deploy** — domain decision pending (os.calistrocreative.com not yet deployed), Phase 2 work queued
5. **OrthoFlow brochure duplicate server name warning** — `brochure.orthoflowsolutions.com` defined in both `orthoflow.conf` and a separate brochure config; nginx warns but handles it. Should consolidate into one file.

---

## Key File Locations (this session)

| What | Where |
|------|-------|
| ArtistOS frontend Dockerfile (healthcheck fix) | `LinesOfBusiness/ArtistOS/artistos-app/frontend/Dockerfile` |
| OrthoFlow nginx config (hardened) | `Kiro/Projects/kiro-agents/docker/nginx/orthoflow.conf` |
| OrthoFlow docker-compose (network fix) | `LinesOfBusiness/Orthodontic_Dental/orthoflow-ai/OrthoFlow/docker-compose.yml` |
| OrthoFlow backend Dockerfile (apt-get upgrade) | `LinesOfBusiness/Orthodontic_Dental/orthoflow-ai/OrthoFlow/backend/Dockerfile` |
| OrthoFlow Trivy ignore (OS CVEs added) | `LinesOfBusiness/Orthodontic_Dental/orthoflow-ai/OrthoFlow/backend/.trivyignore` |
