---
inclusion: fileMatch
fileMatchPattern: "**/*.py,**/*.ts,**/*.tsx,**/agents/**,**.env*"
description: "AI Engineering agent environment configuration and detection rules."
---

# AI Engineering Agent — Environments

## Development Environment

### Local Setup
- Python 3.11+ with venv (`Kiro/Projects/kiro-agents/.venv/`)
- Node.js 18+ (for frontend projects)
- Docker Compose running on `docker_agent-net`
- Ollama on localhost:11434 (embeddings + classification)
- PostgreSQL on localhost:5432 (kiro_agents) and :5433 (OrthoFlow)

### IDE Configuration
- Kiro IDE with steering files active
- MCP servers: PostgreSQL, GitHub, Figma, Playwright, Fetch
- Hooks: ruff on save, tsc on save, docker validate on compose changes

## Per-Project Environment

### OrthoFlow
```env
# Backend (port 8000)
DATABASE_URL=postgresql+asyncpg://orthoflow:${ORTHOFLOW_DB_PASSWORD}@orthoflow-postgres:5433/orthoflow
REDIS_URL=redis://orthoflow-redis:6380/0
MINIO_ENDPOINT=orthoflow-minio:9100
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
OLLAMA_URL=http://orthoflow-ollama:11435

# Frontend (port 5173)
VITE_API_URL=http://localhost:8000
VITE_APP_NAME=OrthoFlow
```

### Kiro Agents
```env
# Orchestrator + Agents
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
SLACK_SIGNING_SECRET=${SLACK_SIGNING_SECRET}
DATABASE_URL=postgresql+asyncpg://kiro:${POSTGRES_PASSWORD}@postgres:5432/kiro_agents
OLLAMA_URL=http://ollama:11434
```

### Website (melanin-tech-website)
```env
# Next.js (port 3000)
NEXT_PUBLIC_SITE_URL=https://www.melanin-tech.com
NODE_ENV=production
```

## Environment Rules for Code

### Production Code Restrictions
- No `print()` or `console.log()` — use structured logging
- No hardcoded URLs — use environment variables
- No test data or demo credentials in production builds
- No debug flags or verbose logging in production config
- All API calls must have timeout configuration
- All database queries must use connection pooling

### Development Conveniences (OK in dev, stripped for prod)
- Hot-reload (FastAPI --reload, Vite HMR)
- Debug logging level
- CORS allow-all (only in dev, specific origins in prod)
- Demo accounts (admin@testortho.com/test123)
- Seed data scripts

## Environment Detection in Code

```python
import os

ENVIRONMENT = os.getenv("ENVIRONMENT", "production")  # Fail-safe: production

def is_production() -> bool:
    return ENVIRONMENT == "production"

def is_development() -> bool:
    return ENVIRONMENT in ("development", "dev", "local")

# Use for feature flags, logging levels, CORS config
if is_production():
    CORS_ORIGINS = ["https://www.melanin-tech.com", "https://app.orthoflowsolutions.com"]
else:
    CORS_ORIGINS = ["*"]
```

```typescript
const API_URL = import.meta.env.VITE_API_URL;
const IS_DEV = import.meta.env.DEV;

// Never hardcode URLs
// ❌ fetch("http://localhost:8000/api/invoices")
// ✅ fetch(`${API_URL}/api/invoices`)
```
