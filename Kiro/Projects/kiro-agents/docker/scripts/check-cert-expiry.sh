#!/bin/sh
# check-cert-expiry.sh — alerts Slack 30 days before TLS cert expires
CERT_PATH="/etc/letsencrypt/live/melanin-tech.com/fullchain.pem"
WARN_DAYS=30

if [ ! -f "$CERT_PATH" ]; then
  echo "Cert not found: $CERT_PATH"
  exit 1
fi

EXPIRY=$(openssl x509 -enddate -noout -in "$CERT_PATH" | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || date -jf "%b %d %T %Y %Z" "$EXPIRY" +%s)
NOW_EPOCH=$(date +%s)
DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

if [ "$DAYS_LEFT" -le "$WARN_DAYS" ]; then
  curl -s -X POST "https://slack.com/api/chat.postMessage" \
    -H "Authorization: Bearer ${SLACK_BOT_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"channel\":\"${SLACK_CHANNEL_ID}\",\"text\":\"⚠️ *TLS Certificate Expiry Warning*\nmelanin-tech.com cert expires in *${DAYS_LEFT} days* (${EXPIRY}).\nRun: \`docker compose exec certbot certbot renew\`\"}"
fi
