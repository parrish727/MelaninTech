# Melanin Technologies — Kubernetes Manifests

## Prerequisites
- Kubernetes cluster running (kind, k3s, or production)
- `kubectl` configured
- Local Docker images built (see below)

## Build images first
```bash
cd kiro-agents
docker compose -f docker/docker-compose.yml build
```

## Load images into cluster (kind)
```bash
kind load docker-image docker-orchestrator:latest
kind load docker-image docker-mcp-server:latest
kind load docker-image docker-darius-agent:latest
kind load docker-image docker-playwright-mcp:latest
# ... repeat for each agent image
kind load docker-image melanin-tech-website:latest
```

## Create secrets (run once)
```bash
kubectl create secret generic agent-secrets -n melanin-tech \
  --from-literal=ANTHROPIC_API_KEY=<your-key> \
  --from-literal=SLACK_BOT_TOKEN=<your-token> \
  --from-literal=SLACK_APP_TOKEN=<your-token> \
  --from-literal=SLACK_SIGNING_SECRET=<your-secret> \
  --from-literal=SLACK_CHANNEL_ID=<your-channel> \
  --from-literal=POSTGRES_PASSWORD=kiro_secret \
  --from-literal=POSTGRES_DSN=postgresql://kiro:kiro_secret@postgres:5432/kiro \
  --from-literal=GITHUB_TOKEN=<your-pat> \
  --from-literal=FIGMA_ACCESS_TOKEN=<your-token> \
  --from-literal=FIGMA_FILE_ID=<your-file-id>
```

## Deploy kiro-agents stack
```bash
kubectl apply -f k8s/kiro-agents/
```

## Deploy melanin-tech-website
```bash
kubectl apply -f k8s/melanin-website/
```

## Check status
```bash
kubectl get pods -n melanin-tech
kubectl get pods -n melanin-website
```

## Port layout
| Service | Port | NodePort |
|---|---|---|
| production-server | 3000 | 30000 |
| preview-server | 3001 | 30001 |
| testing-server | 3002 | 30002 |
| staging-server | 3003 | 30003 |
| mcp-server | 9000 | — |
| mcp-github | 9010 | — |
| playwright-mcp | 9001 | — |
