---
inclusion: fileMatch
fileMatchPattern: "**/*.py,**/*.ts,**/*.tsx,**/agents/**,**/skills/**,**/ollama*,**/package.json,**/pyproject.toml,**/requirements*.txt"
description: "AI Engineering agent parameters for model configs, dependencies, and project settings."
---

# AI Engineering Agent — Parameters

## Identity
- **Role:** Senior AI/Software Engineer
- **Modes:** Development (full-stack features), ML Engineering (models, embeddings, pipelines), Agent Authoring (skills, routing, MCP)
- **Escalation Target:** pktech_dev (Slack DM)

## Technology Stack

### Backend
- Python 3.11+ (FastAPI, Pydantic, SQLAlchemy, httpx)
- PostgreSQL 16 + pgvector (semantic search)
- Redis (caching, queues)
- MinIO (object storage / file uploads)
- Ollama (nomic-embed-text for embeddings, custom classification models)
- Anthropic Claude API (Sonnet for general, Haiku for fast, Opus for complex)

### Frontend
- TypeScript (strict mode)
- React + Vite (SPA)
- Next.js 16 (SSR/SSG for marketing site)
- Tailwind CSS (utility-first, no inline styles)
- Framer Motion (animations)
- Lucide React (icons)

### AI/ML
- Anthropic Claude API — production inference (only provider)
- Ollama — local embeddings (nomic-embed-text) and classification
- pgvector — vector storage and similarity search
- MCP — Model Context Protocol (tool interface for agents)

### Agent System
- Skill pattern: `agents/skills/*.skill.md` (hot-reloadable, declarative)
- Script pattern: `agents/scripts/` (deterministic multi-step)
- Template pattern: `agents/template/spawn.py` (dynamic agent spawning)
- Darius: orchestration, chaining, replay, MCP discovery

## Project Paths

| Project | Path | Stack |
|---------|------|-------|
| Agent System | `Kiro/Projects/kiro-agents/` | Python, FastAPI, Docker, Slack |
| Agent Skills | `Kiro/Projects/kiro-agents/agents/skills/` | Markdown (hot-reload) |
| Darius | `Kiro/Projects/kiro-agents/AI/darius/` | Python orchestration |
| OrthoFlow Backend | `LinesOfBusiness/Orthodontic_Dental/orthoflow-ai/OrthoFlow/backend/` | FastAPI |
| OrthoFlow Frontend | `LinesOfBusiness/Orthodontic_Dental/orthoflow-ai/OrthoFlow/frontend/` | React+Vite |
| HTC App | `LinesOfBusiness/Held_Together_Caregiving/htc-app/` | FastAPI + React |
| Music Catalogue | `music-catalogue-system/` | FastAPI + React |
| Website | `melanin-tech-website/` | Next.js 16 |

## LLM Configuration

| Use Case | Model | Context | Notes |
|----------|-------|---------|-------|
| General coding | Claude Sonnet | Full context | Default for features |
| Fast responses | Claude Haiku | Reduced | Chat, simple tasks |
| Complex reasoning | Claude Opus | Full context | Architecture, debugging |
| Embeddings | nomic-embed-text (Ollama) | 8192 tokens | Local, no API cost |
| Classification | Custom Ollama models | Varies | Per-project (e.g., orthoflow-classify) |

## Database Connections

| Database | Port | Purpose | Access |
|----------|------|---------|--------|
| kiro_agents | 5432 | Agent memory, pgvector | Full (dev), read-only (prod) |
| orthoflow | 5433 | OrthoFlow application | Full (dev), migrations via CI/CD (prod) |
| HUD | 5432 (shared) | HUD state | Read/write (internal only) |

## Response Format
- Start with understanding the existing codebase (read before write)
- Match project conventions (imports, naming, structure)
- Provide complete implementations (no stubs or TODOs)
- Include error handling and edge cases
- Reference relevant tests or suggest test coverage
- Note any soft constraint triggers (dependency additions, auth changes)
