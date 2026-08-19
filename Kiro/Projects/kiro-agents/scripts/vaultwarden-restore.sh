#!/bin/bash
# Restore Vaultwarden after killswitch — only run after investigation complete
set -e
echo "Restoring Vaultwarden..."

# Restore nginx config from git
cd /Users/pktech_dev/Documents/MelaninTechnologies/Kiro/Projects/kiro-agents
git checkout -- docker/nginx/secrets.conf
docker exec docker-nginx-1 nginx -s reload 2>/dev/null

# Restart container
docker compose -f docker/docker-compose.yml up -d vaultwarden

echo "✅ Vaultwarden restored. Verify access at https://emerald.melanin-tech.com/"
echo "⚠️  Remember: rotate any potentially compromised secrets."
