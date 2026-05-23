#!/usr/bin/env bash
# onboard-client.sh — provision a new client site on the K8s cluster
#
# Usage:
#   ./onboard-client.sh --slug acme --domain acme.com --image ghcr.io/melanin-tech/acme:latest --type nextjs
#   ./onboard-client.sh --slug bob-shop --domain bobshop.com --image ghcr.io/melanin-tech/bob-shop:latest --type static
#
# Prerequisites:
#   - kubectl configured against target cluster
#   - 00-bootstrap.yaml already applied (nginx-ingress + cert-manager)
#   - Client DNS A record pointing to cluster's LoadBalancer IP

set -euo pipefail

# ── Parse args ────────────────────────────────────────────────────────────────
SLUG="" DOMAIN="" IMAGE="" SITE_TYPE="nextjs"

while [[ $# -gt 0 ]]; do
  case $1 in
    --slug)    SLUG="$2";      shift 2 ;;
    --domain)  DOMAIN="$2";    shift 2 ;;
    --image)   IMAGE="$2";     shift 2 ;;
    --type)    SITE_TYPE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

[[ -z "$SLUG" || -z "$DOMAIN" || -z "$IMAGE" ]] && {
  echo "Error: --slug, --domain, and --image are required."
  exit 1
}

TEMPLATE_DIR="$(dirname "$0")/template"
MANIFEST="$(mktemp /tmp/client-XXXXXX.yaml)"

# ── Substitute placeholders ───────────────────────────────────────────────────
sed \
  -e "s|{{SLUG}}|${SLUG}|g" \
  -e "s|{{DOMAIN}}|${DOMAIN}|g" \
  -e "s|{{IMAGE}}|${IMAGE}|g" \
  -e "s|{{SITE_TYPE}}|${SITE_TYPE}|g" \
  "${TEMPLATE_DIR}/client-site.yaml" > "$MANIFEST"

echo "▶ Applying manifests for client: ${SLUG} (${DOMAIN})"
kubectl apply -f "$MANIFEST"
rm "$MANIFEST"

# ── Wait for rollout ──────────────────────────────────────────────────────────
echo "▶ Waiting for deployment rollout..."
kubectl rollout status deployment/website -n "client-${SLUG}" --timeout=120s

echo ""
echo "✅ Client '${SLUG}' is live."
echo "   Domain : https://${DOMAIN}"
echo "   NS     : client-${SLUG}"
echo ""
echo "   DNS instructions for client:"
echo "   Add an A record:  ${DOMAIN}  →  $(kubectl get svc -n ingress-nginx ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo '<LoadBalancer IP>')"
echo "   Add a CNAME:      www.${DOMAIN}  →  ${DOMAIN}"
echo ""
echo "   TLS cert will auto-provision via cert-manager (1-2 min after DNS propagates)."
