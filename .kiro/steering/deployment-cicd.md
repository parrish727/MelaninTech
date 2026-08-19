---
inclusion: fileMatch
fileMatchPattern: "**.drone*,**/ci/**,**/cd/**,**/deploy*,**/Dockerfile*,**/docker-compose*,**/watchtower*"
description: "CI/CD pipeline configuration and deployment standards for all services."
---

# Deployment & CI/CD

## Deployment Pipelines

### melanin-tech.com (Website)
```
Code Change → Branch → Local Build → Docker Compose rebuild → nginx routes automatically
```
- No CI pipeline (builds locally)
- `docker compose up -d --build production-server`
- Preview: `docker compose up -d --build preview-server`
- Zero-downtime: health check must pass before nginx routes traffic

### OrthoFlow AI
```
Code Change → PR to main → GitHub Actions → GHCR push → Watchtower auto-deploys
```
- Fully automated deploy-on-merge
- Watchtower polls GHCR, pulls new images, recreates containers
- Health check gates the new container before traffic routes
- Rollback: manually pull previous image tag

### Agent System (Kiro)
```
Skill updates: Edit .skill.md → hot-reloaded (no restart)
Code changes: Edit .py → docker compose up -d --build <agent>
Infrastructure: Edit docker-compose.yml → docker compose up -d
```

## Drone CI (localhost:1616)

### Configuration
- Port: 1616 (UI), 1661 (runner)
- Pipeline format: `.drone.yml`
- Secrets: Drone secret store (separate from .env)

### Pipeline Standards
```yaml
kind: pipeline
type: docker
name: default

steps:
  - name: lint
    image: python:3.11-slim
    commands:
      - pip install ruff
      - ruff check .

  - name: test
    image: python:3.11-slim
    commands:
      - pip install -r requirements.txt
      - pytest --tb=short

  - name: build
    image: docker
    commands:
      - docker build -t ${DRONE_REPO_NAME}:${DRONE_COMMIT_SHA:0:8} .
    volumes:
      - name: docker_sock
        path: /var/run/docker.sock
```

## Container Build Standards

### Dockerfile Requirements
- Multi-stage builds (builder → runtime)
- Minimal base images (alpine, slim)
- Non-root user (`USER app` or `USER 1000`)
- No package managers in final stage
- HEALTHCHECK instruction
- Explicit version tags (no `:latest` in production)
- `.dockerignore` for build context

### Example Pattern
```dockerfile
# Build stage
FROM python:3.11-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app
RUN adduser --system --group app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --chown=app:app . .
USER app
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Deployment Checklist

Before any production deployment:
- [ ] All tests pass
- [ ] Docker build succeeds locally
- [ ] Health check endpoint verified
- [ ] No secrets in image layers
- [ ] Resource limits defined in compose
- [ ] Rollback plan documented
- [ ] Approval obtained (production = double approval)
