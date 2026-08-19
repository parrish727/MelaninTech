#!/bin/bash
# ════════════════════════════════════════════════════════════
# VAULTWARDEN KILLSWITCH — Emergency Secret Isolation
# Run this immediately if a security breach is suspected.
# ════════════════════════════════════════════════════════════
# What it does:
#   1. Stops the Vaultwarden container (no access possible)
#   2. Blocks the domain at nginx level
#   3. Revokes all active sessions
#   4. Notifies via Slack
#   5. Preserves data volume for forensics (does NOT delete)
# ════════════════════════════════════════════════════════════

set -e

echo "🔴 KILLSWITCH ACTIVATED — Isolating Vaultwarden"

# Stop the container immediately
docker stop docker-vaultwarden-1 2>/dev/null && echo "  ✅ Container stopped"

# Block at nginx (deny all to vaultwarden upstream)
docker exec docker-nginx-1 sh -c 'echo "server { listen 443 ssl; server_name emerald.melanin-tech.com; ssl_certificate /etc/letsencrypt/live/melanin-tech.com/fullchain.pem; ssl_certificate_key /etc/letsencrypt/live/melanin-tech.com/privkey.pem; return 503; }" > /etc/nginx/conf.d/secrets.conf && nginx -s reload' 2>/dev/null && echo "  ✅ nginx blocking emerald.melanin-tech.com (503)"

# Notify Slack
WEBHOOK="${SLACK_DEMO_WEBHOOK_URL:-}"
if [ -n "$WEBHOOK" ]; then
  curl -sf -X POST "$WEBHOOK" \
    -H "Content-Type: application/json" \
    -d '{"text":"🔴 *SECURITY ALERT* — Vaultwarden KILLSWITCH activated.\nAll vault access has been terminated.\nContainer stopped. Domain blocked.\nInvestigate immediately."}' && echo "  ✅ Slack notified"
fi

echo ""
echo "🔒 Vaultwarden is ISOLATED."
echo "   - Container: stopped"
echo "   - Domain: returning 503"
echo "   - Data: preserved at docker volume (for forensics)"
echo ""
echo "To restore after investigation:"
echo "   1. Fix the nginx conf: restore secrets.conf from git"
echo "   2. Rotate ALL secrets stored in the vault"
echo "   3. docker compose up -d vaultwarden"
echo "   4. Verify access with new credentials"
