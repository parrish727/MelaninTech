---
inclusion: fileMatch
fileMatchPattern: "**/docker-compose*,**/Dockerfile*,**/k8s/**,**/nginx*"
description: "DevOps agent tool definitions for Docker and infrastructure management."
---

# DevOps Agent — Tools

## Available MCP Tools

### Docker (via shell)
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| `docker compose ps` | Service status | Read-only |
| `docker compose logs` | Container logs | Read-only |
| `docker inspect` | Container metadata | Read-only |
| `docker stats` | Resource usage | Read-only |
| `docker compose up -d` | Start/rebuild service | Write (approval needed) |
| `docker compose restart` | Restart service | Write (approval for prod) |
| `docker compose down` | Stop service | Write (approval needed) |
| `docker compose config` | Validate compose file | Read-only |

### Kubernetes (via kubectl)
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| `kubectl get` | List resources | Read-only |
| `kubectl describe` | Resource details | Read-only |
| `kubectl logs` | Pod logs | Read-only |
| `kubectl top` | Resource metrics | Read-only |
| `kubectl apply` | Deploy manifests | Write (approval needed) |
| `kubectl delete` | Remove resources | High-impact (double approval) |
| `kubectl exec` | Container shell | Write (blocked for prod) |

### nginx
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| `nginx -t` | Config validation | Read-only |
| `nginx -s reload` | Apply config | Write (approval for prod) |
| Access logs | Request analysis | Read-only |
| Error logs | Issue diagnosis | Read-only |

### Network Diagnostics
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| `curl` | HTTP endpoint probes | Read-only |
| `dig` / `nslookup` | DNS resolution | Read-only |
| `netstat` / `ss` | Port binding verification | Read-only |

## Tool Selection Rules

1. **Always start read-only** — gather state before proposing changes
2. **Validate before apply** — `docker compose config`, `kubectl --dry-run`, `nginx -t`
3. **One service at a time** — no batch operations without explicit request
4. **Log before and after** — capture state before change for rollback reference
5. **Never use `docker rm -f`** — always use compose lifecycle commands

## Deferred Tools (Not in DevOps Domain)

| Need | Defer To |
|------|----------|
| Database queries, schema changes | SRE Agent |
| Application code fixes | AI Engineering Agent |
| LLM/Ollama model management | AI Engineering Agent |
| UI/frontend issues | Frontend Agent (frontend_agent.py) |
| Slack bot logic | Orchestrator code (Code Agent) |
