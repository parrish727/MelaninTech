---
inclusion: auto
description: "Shared environment definitions for all agents including environment detection and mapping."
---

# Shared — Environment Definitions

## Environment Map

All agents share a common environment model. Environment is detected from container name, port, and domain.

| Environment | Detection Criteria | Protection Level |
|-------------|-------------------|-----------------|
| Production | `production-server`, port 3000, `www.melanin-tech.com` | Maximum (read-only) |
| OrthoFlow Prod | `orthoflow-*`, ports 5173/8000, `app.orthoflowsolutions.com` | Maximum (HIPAA) |
| HUD | `hud-*`, ports 4000/8080, `hud.melanin-tech.com` | High (auth-gated) |
| Preview | `preview-server`, port 3001 | Standard (write with approval) |
| Testing | `testing-server`, port 3002 | Low (full access) |
| Staging | `staging-server`, port 3003 | Low (full access) |
| K8s Dev | Kind cluster namespaces | Low (full access) |

## Fail-Safe Rule

**If environment cannot be determined → assume production → apply maximum restrictions.**

This is non-negotiable. Unknown contexts are never treated as safe.

## Environment Variables

Environment is also determined from:
- `NODE_ENV` (production, development, test)
- `ENVIRONMENT` env var in container
- Docker Compose service name prefix
- K8s namespace labels

## Cross-Environment Rules

1. **Never copy production data to non-production** without anonymization
2. **Never expose production ports** to non-standard networks
3. **Production credentials are never used** in development environments
4. **Staging may mirror production config** but with separate secrets
5. **Testing databases may be reset freely** — no approval needed
