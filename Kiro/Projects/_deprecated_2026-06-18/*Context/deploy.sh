#!/bin/bash
set -e

#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Melanin Technologies Website — Build & Deploy Script
# ============================================================
# This script builds and deploys the Next.js website via Docker Compose.
# It does NOT use git or npm run dev.
# ============================================================

PROJECT_ROOT="/Users/pktech_dev/Documents/MelaninTechnologies/melanin-tech-website"
DOCKER_DIR="/Users/pktech_dev/Documents/MelaninTechnologies/Kiro/Projects/kiro-agents/docker"
SITE_URL="http://localhost:3001"
SCREENSHOT_API="http://localhost:9001/screenshot"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="${PROJECT_ROOT}/deploy_${TIMESTAMP}.log"

# ---- Helpers ----
log() {
  echo "[$(date +'%H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

fail() {
  log "ERROR: $*"
  exit 1
}

# ---- Pre-flight checks ----
log "=== Melanin Technologies Website Deploy ==="
log "Timestamp : ${TIMESTAMP}"
log "Project   : ${PROJECT_ROOT}"
log "Docker Dir: ${DOCKER_DIR}"

# Verify source exists
[[ -f "${PROJECT_ROOT}/app/page.tsx" ]] || fail "page.tsx not found at ${PROJECT_ROOT}/app/page.tsx"
[[ -f "${DOCKER_DIR}/docker-compose.yml" ]] || fail "docker-compose.yml not found at ${DOCKER_DIR}/docker-compose.yml"

# Verify Docker is running
docker info > /dev/null 2>&1 || fail "Docker daemon is not running"

log "Pre-flight checks passed."

# ---- Step 1: Install dependencies (production) ----
log "Installing production dependencies..."
cd "${PROJECT_ROOT}"

if [[ -f "package-lock.json" ]]; then
  npm ci --production=false --loglevel=warn >> "$LOG_FILE" 2>&1 || fail "npm ci failed"
elif [[ -f "yarn.lock" ]]; then
  yarn install --frozen-lockfile >> "$LOG_FILE" 2>&1 || fail "yarn install failed"
elif [[ -f "pnpm-lock.yaml" ]]; then
  pnpm install --frozen-lockfile >> "$LOG_FILE" 2>&1 || fail "pnpm install failed"
else
  npm install --loglevel=warn >> "$LOG_FILE" 2>&1 || fail "npm install failed"
fi

log "Dependencies installed."

# ---- Step 2: Build the Next.js project ----
log "Building Next.js production bundle..."
cd "${PROJECT_ROOT}"
npx next build >> "$LOG_FILE" 2>&1 || fail "Next.js build failed"
log "Next.js build succeeded."

# ---- Step 3: Docker Compose — rebuild and deploy preview-server ----
log "Rebuilding and deploying preview-server via Docker Compose..."
cd "${DOCKER_DIR}"

# Stop existing preview-server container gracefully
docker compose stop preview-server >> "$LOG_FILE" 2>&1 || true

# Rebuild and start in detached mode
docker compose up -d --build preview-server >> "$LOG_FILE" 2>&1 || fail "Docker Compose up failed"

log "Docker container rebuilt and started."

# ---- Step 4: Wait for the site to become healthy ----
log "Waiting for site to become available at ${SITE_URL}..."
MAX_RETRIES=30
RETRY_INTERVAL=2
HEALTHY=false

for i in $(seq 1 $MAX_RETRIES); do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${SITE_URL}" 2>/dev/null || echo "000")
  if [[ "$HTTP_CODE" == "200" ]]; then
    HEALTHY=true
    log "Site is live! (HTTP ${HTTP_CODE}) — attempt ${i}/${MAX_RETRIES}"
    break
  fi
  log "Attempt ${i}/${MAX_RETRIES}: HTTP ${HTTP_CODE} — retrying in ${RETRY_INTERVAL}s..."
  sleep $RETRY_INTERVAL
done

if [[ "$HEALTHY" != "true" ]]; then
  log "WARNING: Site did not return HTTP 200 after ${MAX_RETRIES} attempts."
  log "Dumping container logs for debugging..."
  docker compose -f "${DOCKER_DIR}/docker-compose.yml" logs --tail=50 preview-server >> "$LOG_FILE" 2>&1
  fail "Site health check failed at ${SITE_URL}"
fi

# ---- Step 5: Capture verification screenshot via Playwright MCP ----
log "Capturing post-deploy screenshot via Playwright MCP at ${SCREENSHOT_API}..."
SCREENSHOT_PATH="${PROJECT_ROOT}/deploy_verification_${TIMESTAMP}.png"

SCREENSHOT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${SCREENSHOT_API}" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"http://preview-server:3001\",\"path\":\"/tmp/deploy_check_${TIMESTAMP}.png\"}" 2>/dev/null || echo "")

SCREENSHOT_HTTP=$(echo "$SCREENSHOT_RESPONSE" | tail -1)
SCREENSHOT_BODY=$(echo "$SCREENSHOT_RESPONSE" | sed '$d')

if [[ "$SCREENSHOT_HTTP" == "200" ]]; then
  log "Screenshot captured successfully."
  log "Screenshot API response: ${SCREENSHOT_BODY}"
else
  log "WARNING: Screenshot API returned HTTP ${SCREENSHOT_HTTP} (non-fatal)."
  log "Response: ${SCREENSHOT_BODY}"
  log "The Playwright MCP server may not be running on port 9001."
fi

# ---- Step 6: Capture full-page screenshot (multiple viewports) ----
log "Capturing additional viewport screenshots..."
for VIEWPORT in "fullPage" "mobile"; do
  if [[ "$VIEWPORT" == "mobile" ]]; then
    PAYLOAD="{\"url\":\"http://preview-server:3001\",\"path\":\"/tmp/deploy_${VIEWPORT}_${TIMESTAMP}.png\",\"width\":375,\"height\":812}"
  else
    PAYLOAD="{\"url\":\"http://preview-server:3001\",\"path\":\"/tmp/deploy_${VIEWPORT}_${TIMESTAMP}.png\",\"fullPage\":true}"
  fi

  RESP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${SCREENSHOT_API}" \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}" 2>/dev/null || echo "000")

  if [[ "$RESP" == "200" ]]; then
    log "  ${VIEWPORT} screenshot: OK"
  else
    log "  ${VIEWPORT} screenshot: HTTP ${RESP} (skipped)"
  fi
done

# ---- Step 7: Print container status ----
log ""
log "=== Container Status ==="
docker compose -f "${DOCKER_DIR}/docker-compose.yml" ps preview-server 2>/dev/null | tee -a "$LOG_FILE"

# ---- Step 8: Summary ----
log ""
log "=============================================="
log "  DEPLOYMENT COMPLETE"
log "=============================================="
log "  Live site    : ${SITE_URL}"
log "  Source       : ${PROJECT_ROOT}/app/page.tsx"
log "  Build log    : ${LOG_FILE}"
log "  Container    : docker-preview-server-1"
log ""
log "  Design refs  :"
log "    Hero       : website/Screenshot 2026-04-14 at 7.19.32 AM.png"
log "    Services   : website/Screenshot 2026-04-14 at 7.20.01 AM.png"
log "    Who We Are : website/Screenshot 2026-04-14 at 7.20.40 AM.png"
log "    Contact    : website/Screenshot 2026-04-14 at 7.21.05 AM.png"
log ""
log "  Figma ref    : https://funny-chain-82390459.figma.site/"
log "  Screenshot   : POST ${SCREENSHOT_API}"
log "=============================================="

exit 0
