# Network Policy

## Architecture

```
Internet → Cloudflare (DDNS, no proxy) → Router (port 80/443 forwarded) → nginx
    │
    ├── melanin-tech.com      → production-server:3000
    ├── hud.melanin-tech.com  → hud-frontend:4000 / hud:8080
    ├── app.orthoflowsolutions.com → orthoflow-frontend:5173
    └── api.orthoflowsolutions.com → orthoflow-backend:8000
```

## Exposed Ports (to internet)

| Port | Service | Protection |
|------|---------|------------|
| 80 | nginx (HTTP→HTTPS redirect) | Rate limiting, fail2ban |
| 443 | nginx (TLS termination) | TLS 1.2+, HSTS, rate limiting, fail2ban |

## Internal Only (agent-net bridge, no port binding)

- All agent APIs (:8000)
- PostgreSQL (:5432)
- Ollama (:11434)
- MCP server (:9000)
- HUD backend (:8080)
- Redis (:6379)

## Rate Limiting (nginx)

| Zone | Rate | Applies To |
|------|------|------------|
| general | 30 req/min | All routes |
| contact | 5 req/min | Contact form submissions |

## fail2ban Jails

| Jail | Trigger | Ban Duration |
|------|---------|-------------|
| nginx-http-auth | 10 failed auths in 10min | 1 hour |
| nginx-limit-req | 10 rate limit hits | 1 hour |
| nginx-botsearch | 2 bot probe attempts | 1 hour |

## TLS Configuration

- Protocols: TLSv1.2, TLSv1.3 only
- Ciphers: ECDHE-ECDSA/RSA with AES-GCM and CHACHA20-POLY1305
- HSTS: max-age=31536000, includeSubDomains, preload
- Session tickets: disabled (forward secrecy)
- OCSP stapling: enabled via ssl_trusted_certificate

## DNS

- Cloudflare DDNS updates every 5 minutes
- Domains: melanin-tech.com, www, hud, orthoflowsolutions.com, www, app, api
- Proxy status: DNS-only (gray cloud) — TLS terminated at origin

## K8s Network Policies (when migrated)

```yaml
# Default deny all ingress per client namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all
  namespace: client-{{SLUG}}
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress: []  # Deny all — explicit allows added per service
```
