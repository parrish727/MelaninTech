#!/usr/bin/env bash
# scan-containers.sh — Scan all Melanin Tech Docker images for vulnerabilities
# Usage: ./scripts/scan-containers.sh [--fix]
# Requires: trivy (brew install aquasecurity/trivy/trivy)

set -euo pipefail

SEVERITY="HIGH,CRITICAL"
IMAGES=(
  "docker-hud"
  "docker-hud-frontend"
  "docker-orchestrator"
  "docker-deploy-agent"
  "docker-darius-agent"
  "docker-playwright-mcp"
  "docker-mcp-server"
)

echo "🔍 Melanin Tech Container Vulnerability Scan"
echo "   Severity: $SEVERITY"
echo "   Date: $(date)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_VULNS=0
for img in "${IMAGES[@]}"; do
  if docker image inspect "$img:latest" &>/dev/null; then
    echo ""
    echo "📦 Scanning: $img"
    COUNT=$(trivy image --severity "$SEVERITY" --no-progress --quiet "$img:latest" 2>/dev/null | grep -c "│" || true)
    TOTAL_VULNS=$((TOTAL_VULNS + COUNT))
    trivy image --severity "$SEVERITY" --no-progress "$img:latest" 2>/dev/null | grep -E "│|Library|Total:" || echo "   ✅ No HIGH/CRITICAL vulnerabilities"
  else
    echo "⏭️  Skipping $img (image not found locally)"
  fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Summary: $TOTAL_VULNS HIGH/CRITICAL findings across ${#IMAGES[@]} images"

if [[ "$TOTAL_VULNS" -gt 0 ]]; then
  echo "⚠️  Action required — review and patch vulnerable dependencies"
  exit 1
else
  echo "✅ All clear"
  exit 0
fi
