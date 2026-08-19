---
inclusion: fileMatch
fileMatchPattern: "**/*.py,**/*.ts,**/*.tsx,**/agents/**,**/skills/**,**/package.json,**/pyproject.toml"
description: "AI Engineering agent tool definitions and available capabilities."
---

# AI Engineering Agent — Tools

## Available Tools

### Code Development
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| File read/write | Source code implementation | Standard |
| Terminal (ruff) | Python linting | Read-only |
| Terminal (tsc) | TypeScript type checking | Read-only |
| Terminal (pytest) | Python test execution | Read-only |
| Terminal (vitest) | TypeScript test execution | Read-only |
| Terminal (npm/pip) | Dependency installation | Write (approval for prod) |

### LLM & Embeddings
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| Anthropic Claude API | Production inference | Standard (cost-aware) |
| Ollama REST API | Embeddings, classification | Standard |
| `ollama list` | View available models | Read-only |
| `ollama pull` | Download models | Write (disk space) |
| `ollama create` | Create custom models | Write (approval needed) |

### Database
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| SQLAlchemy migrations | Schema changes | Write (approval needed) |
| Alembic | Migration generation/execution | Write (approval needed) |
| psql (via docker exec) | Direct SQL (dev only) | Write (dev), blocked (prod) |
| pgvector queries | Semantic search testing | Read-only |

### MCP Servers (Available)
| Server | Tools Provided | Purpose |
|--------|---------------|---------|
| PostgreSQL MCP | query, schema inspection | Database interaction |
| GitHub MCP | repos, PRs, issues | Code collaboration |
| Figma MCP | design tokens, assets | Design-to-code |
| Playwright MCP | screenshots, testing | Visual regression |
| Fetch MCP | HTTP requests | API testing |

### Build & Deploy
| Tool | Purpose | Risk Level |
|------|---------|-----------|
| `docker compose build` | Build service image | Write |
| `npm run build` | Frontend production build | Read-only |
| `pip install` | Python dependency install | Write |
| `npm install` | Node dependency install | Write |

## Tool Selection Rules

1. **Read existing code first** — understand the codebase before writing
2. **Match existing patterns** — don't introduce new libraries or patterns without justification
3. **Type-safe always** — use type hints (Python) and strict types (TypeScript)
4. **Test after implement** — run relevant tests to verify changes
5. **Lint before committing** — ruff check (Python), tsc --noEmit (TypeScript)
6. **Cost-aware LLM usage** — prefer Haiku for simple tasks, Sonnet for features, Opus only when needed

## Deferred Tools (Not in AI Engineering Domain)

| Need | Defer To | Reason |
|------|----------|--------|
| Container restart/rebuild | DevOps Agent | Infrastructure lifecycle |
| nginx config changes | DevOps Agent | Reverse proxy management |
| K8s manifest changes | DevOps Agent | Orchestration layer |
| Performance diagnostics | SRE Agent | Observability domain |
| Incident investigation | SRE Agent | Production monitoring |
| Capacity planning | SRE Agent | Infrastructure metrics |
| Container health monitoring | SRE Agent | Reliability domain |
| DNS/TLS changes | DevOps Agent | Network infrastructure |

## Dependency Management

### Adding Python Dependencies
```bash
# Add to requirements.txt with pinned version
pip install <package>==<version>
pip freeze | grep <package> >> requirements.txt

# Or via pyproject.toml
[project.dependencies]
"fastapi>=0.100,<1.0"
"pydantic>=2.0,<3.0"
```

### Adding Node Dependencies
```bash
# Add with exact version
npm install --save-exact <package>@<version>

# Dev dependencies
npm install --save-dev --save-exact <package>@<version>
```

### Rules
- Pin exact versions for production dependencies
- Prefer well-known, actively maintained packages
- Check for typosquatting (verify package name carefully)
- Document WHY a dependency was added (in PR description)
- Remove unused dependencies promptly
