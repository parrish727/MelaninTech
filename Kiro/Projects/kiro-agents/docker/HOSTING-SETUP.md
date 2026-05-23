# melanin-tech.com — Production Hosting Setup

## Architecture

```
Internet
  │
  ▼
Google Fiber Router  (ports 80/443 forwarded)
  │
  ▼
nginx container  (TLS termination, security headers, rate limiting)
  │
  ▼
production-server container  (Next.js, port 3000)

Cloudflare DDNS container  → updates melanin-tech.com A record every 5 min
fail2ban container          → bans malicious IPs via iptables
certbot container           → auto-renews Let's Encrypt cert every 12h
```

---

## Step 1 — Cloudflare DNS Setup

1. Sign up at cloudflare.com (free)
2. Add site: `melanin-tech.com`
3. Cloudflare will scan existing DNS records
4. Change nameservers at your registrar to Cloudflare's (shown in dashboard)
5. Create API token:
   - dash.cloudflare.com → My Profile → API Tokens → Create Token
   - Use template: **Edit zone DNS**
   - Scope to zone: `melanin-tech.com`
   - Copy token → paste into `.env` as `CF_API_TOKEN`
6. Copy Zone ID from melanin-tech.com Overview page → paste into `.env` as `CF_ZONE_ID`
7. Set SSL/TLS mode to **Full** (not Full Strict — cert is self-managed)
8. Enable **Always Use HTTPS** in SSL/TLS → Edge Certificates

---

## Step 2 — Router Port Forwarding (Google Fiber)

1. Open Google Fiber app or go to `http://192.168.1.1`
2. Navigate to: **Network** → **Advanced** → **Port Forwarding**
3. Add two rules:

| Name        | External Port | Internal IP     | Internal Port | Protocol |
|-------------|--------------|-----------------|---------------|----------|
| HTTP        | 80           | 192.168.1.197   | 80            | TCP      |
| HTTPS       | 443          | 192.168.1.197   | 443           | TCP      |

4. Save and apply

---

## Step 3 — Get TLS Certificate (first time only)

nginx must be running with HTTP only first so certbot can complete the ACME challenge:

```bash
# 1. Temporarily comment out the SSL server blocks in melanintech.conf
#    (leave only the HTTP server block with /.well-known/acme-challenge/)

# 2. Start nginx
cd docker && docker compose up -d nginx

# 3. Get the cert
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d melanin-tech.com -d www.melanin-tech.com \
  --email hello@melanin-tech.com \
  --agree-tos --no-eff-email

# 4. Re-enable the SSL server blocks in melanintech.conf

# 5. Reload nginx
docker compose exec nginx nginx -s reload
```

---

## Step 4 — Start All Services

```bash
cd /Users/pktech_dev/Documents/MelaninTechnologies/Kiro/Projects/kiro-agents/docker

docker compose up -d \
  cloudflare-ddns \
  nginx \
  certbot \
  fail2ban \
  production-server
```

---

## Step 5 — Verify

```bash
# Check DDNS updated
docker compose logs cloudflare-ddns

# Check nginx is healthy
curl -I https://www.melanin-tech.com

# Check cert
echo | openssl s_client -connect www.melanin-tech.com:443 2>/dev/null | openssl x509 -noout -dates

# Check fail2ban is watching
docker compose logs fail2ban
```

---

## Security Summary

| Layer | Protection |
|-------|-----------|
| Cloudflare DNS | DDoS mitigation, hides origin IP |
| nginx TLS | TLSv1.2/1.3 only, HSTS, OCSP stapling |
| Security headers | CSP, X-Frame-Options, nosniff, Permissions-Policy |
| Rate limiting | 30 req/min general, 5 req/min contact form |
| fail2ban | Auto-bans IPs after 10 bad requests (1hr ban) |
| certbot | Auto-renewing Let's Encrypt cert |
| Container isolation | nginx only exposes 80/443; app never directly public |

---

## Ongoing Maintenance

```bash
# View banned IPs
docker compose exec fail2ban fail2ban-client status nginx-limit-req

# Manually unban an IP
docker compose exec fail2ban fail2ban-client set nginx-limit-req unbanip <IP>

# Force cert renewal
docker compose exec certbot certbot renew --force-renewal

# Update DDNS immediately
docker compose restart cloudflare-ddns
```
