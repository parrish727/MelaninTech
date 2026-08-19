# E2E Testing Standards — Melanin Technologies Inc.

> **Version:** 1.0  
> **Effective:** 2026-08-02  
> **Applies to:** All projects (OrthoFlow, HTC, ParcelPro, ArtistOS, etc.)  
> **Lesson source:** OrthoFlow deployment issues 2026-07-30 to 2026-08-02

## Core Principle

**E2E testing means verifying what the USER sees, not what the API returns.**

API-level tests passing does NOT mean the feature is working. A feature is only "deployed" when:
1. The code is in the correct file (not a similar-named one)
2. The correct file is imported/mounted in the app entrypoint
3. The built artifact contains the feature
4. The container is running the built artifact
5. The user can see and interact with the feature through the UI

---

## The 5-Layer Verification Checklist

After ANY deployment, verify ALL layers in order:

### Layer 1: Source Code ✓
```bash
# Verify the change is in the correct file
grep "feature_name" path/to/file.py

# Verify the file is imported in the entrypoint
grep "import.*module_name" app/main.py
grep "include_router.*module_name" app/main.py
```

**OrthoFlow lesson:** `claims.py` had the fix but `claims_workflow.py` was the file actually mounted in `main.py`. Always verify which file is imported.

### Layer 2: Build Artifact ✓
```bash
# Frontend: verify feature strings in the built bundle
grep "FeatureName\|feature-route" dist/assets/index-*.js

# Backend: verify the module loads correctly
docker exec container python -c "from app.module import function; print('OK')"
```

**OrthoFlow lesson:** The bundle had the right hash but the feature wasn't accessible because the nav item was never added to the sidebar.

### Layer 3: Container State ✓
```bash
# Verify the container has the latest code
docker exec container cat /app/path/to/file.py | grep "feature"

# Verify no stale bytecache
docker exec container find /app -name "*.pyc" -delete

# Verify the container was actually recreated (not just restarted)
docker inspect container --format='{{.Created}}'
```

**OrthoFlow lesson:** `docker restart` does NOT reload env vars or replace files from image layers. `docker compose up -d --force-recreate` or `docker rm -f && docker compose up -d` is required.

### Layer 4: API Response ✓
```bash
# Hit the actual endpoint the frontend calls (not a similar one)
# Check the frontend code to find the EXACT path
grep "getClaims\|/claims" frontend/src/lib/api.ts

# Then test that exact path
curl -s http://localhost:8000/api/v1/claims/ -H "Authorization: Bearer $TOKEN"
```

**OrthoFlow lesson:** The frontend called `/api/v1/claims/` via `claims_workflow` router, but we were fixing `/api/v1/claims/` in a different `claims.py` that was never mounted.

### Layer 5: User-Visible UI ✓
```bash
# Verify the feature is accessible from the UI (nav items, buttons, routes)
grep "tc-proposals" frontend/src/components/AppLayout.tsx  # Is it in the sidebar?
grep "tc-proposals" frontend/src/main.tsx                   # Is the route registered?
grep "TCProposal" frontend/src/main.tsx                     # Is the import there?
```

**OrthoFlow lesson:** TC Proposals page existed at `/tc-proposals` and the route was registered, but it was never added to the sidebar nav. Users couldn't find it.

---

## Deployment Verification Script Template

Run this after EVERY deployment:

```bash
#!/bin/bash
# deploy-verify.sh — Run after every deployment

echo "═══ DEPLOYMENT VERIFICATION ═══"

# 1. Container health
echo "[1] Container Health"
docker ps --filter name=PROJECT --format "{{.Names}} {{.Status}}" | grep -v "healthy" && echo "⚠️ UNHEALTHY" || echo "✅ All healthy"

# 2. Backend can serve requests
echo "[2] Backend Ready"
curl -sf http://localhost:8000/ready && echo " ✅" || echo " ❌ NOT READY"

# 3. Frontend bundle exists and is accessible
echo "[3] Frontend Bundle"
HASH=$(docker exec frontend-container ls /usr/share/nginx/html/assets/ | grep "index-.*\.js")
curl -sf "http://localhost:PORT/assets/$HASH" > /dev/null && echo "✅ $HASH accessible" || echo "❌ Bundle not serving"

# 4. Feature-specific checks (customize per deployment)
echo "[4] Feature Checks"
TOKEN=$(curl -s localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"...","password":"..."}' | jq -r .access_token)

# Check each new feature endpoint
curl -sf "localhost:8000/api/v1/NEW_ENDPOINT" -H "Authorization: Bearer $TOKEN" > /dev/null && echo "✅ New endpoint responds" || echo "❌ Endpoint broken"

# Check feature is in the JS bundle
grep -c "feature_identifier" /path/to/dist/assets/index-*.js > /dev/null && echo "✅ Feature in bundle" || echo "❌ Feature NOT in bundle"

# Check nav items / UI accessibility
grep "feature-route" /path/to/AppLayout.tsx > /dev/null && echo "✅ In sidebar nav" || echo "⚠️ NOT in sidebar"
```

---

## Common Deployment Failures & Fixes

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| "Loading..." forever | API returns 500 (serialization error) or wrong format | Check backend logs, verify response schema |
| Feature not visible | Route exists but not in sidebar/nav | Add to AppLayout NAV_ITEMS |
| API returns old data | Container running old image, hot-patch didn't persist | `docker rm -f && docker compose up -d` |
| Browser shows old UI | Cloudflare cache or browser cache | Verify bundle hash changed; hard refresh |
| Env vars missing | `docker restart` doesn't reload env_file | `docker compose up -d --force-recreate` |
| Wrong file edited | Multiple files with similar names/routes | Check `main.py` imports to find the MOUNTED file |
| Tests pass but UI broken | Tests hit API directly, don't verify UI accessibility | Add Layer 5 checks (nav items, routes, imports) |
| Seed data not showing | Seed ran on wrong date (UTC vs local) | Use practice timezone for date-dependent data |
| Form returns 422 | Request body format doesn't match Pydantic schema | Check exact schema: `{"responses": {...}}` vs flat object |

---

## Pre-Deployment Checklist (Before Pushing to Main)

- [ ] Feature code is in the correct file (check main.py imports)
- [ ] Route is registered in main.py/router
- [ ] Frontend route is in main.tsx
- [ ] Feature is accessible from UI (sidebar, button, link)
- [ ] `npx vite build` succeeds with 0 errors
- [ ] New backend models have DB tables created (migration or manual)
- [ ] Demo/seed data exists for the feature
- [ ] Env vars are in `.env` AND docker-compose passes them

## Post-Deployment Checklist (After Container Restart)

- [ ] `curl /ready` returns 200
- [ ] Login works for all demo accounts
- [ ] New feature endpoint returns expected data
- [ ] Frontend JS bundle contains feature strings
- [ ] Feature is clickable/visible in the UI (not just API-accessible)
- [ ] Demo data loads for the feature (not "Loading..." forever)
- [ ] Cross-system flows work (staff action → patient sees result)

---

## Key Learnings (OrthoFlow Aug 2026)

1. **Always check which file is mounted** — Don't assume `claims.py` is the one serving `/claims/`. Check `main.py` imports.

2. **`docker restart` ≠ `docker compose up`** — Restart keeps old env vars and image layers. Recreate to reload.

3. **API tests ≠ UI tests** — A route can exist and return 200, but if it's not in the sidebar, users can't find it.

4. **Build hash doesn't prove deployment** — Same hash = same code. But Cloudflare can cache old HTML that references old hashes.

5. **Seed data is date-dependent** — UTC vs Eastern time causes "today's" data to appear on the wrong day.

6. **Serialization bugs hide behind "Loading..."** — When `__dict__` includes SQLAlchemy internals (UUID, Decimal, _sa_instance_state), the endpoint returns 500 but the frontend just shows "Loading..."

7. **Hot-patching is fragile** — `docker cp` works once but any restart reverts to image. Rebuild the image for persistent fixes.
