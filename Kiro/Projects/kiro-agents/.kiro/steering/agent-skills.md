# Agent Skills — Melanin Technologies Inc.

## Orchestrator
- Slack slash command handling (`/task`, `/task-internal`, `/tickets`)
- Task classification and routing to the correct delivery agent
- Human-in-the-loop approval flow (approve / modify / reject)
- Persistent vector memory via pgvector + Ollama (nomic-embed-text)
- Ticket lifecycle management (open → in_progress → done / failed)
- Watchdog: stuck agent detection, container restart, retry up to 9 attempts
- 5-hour Slack digest with 12-hour activity window

## ScaffoldAgent
- Bootstrap new full-stack projects (Next.js + FastAPI + PostgreSQL)
- Generate folder structure, base configs, Dockerfiles, README
- Output: fenced code blocks with file path comments for auto-write

## BackendAgent
- FastAPI route and model generation
- PostgreSQL schema design and migration scripts
- Auth patterns (JWT, API keys)
- Input validation with Pydantic

## FrontendAgent
- Next.js + TypeScript component generation
- Tailwind CSS styling
- Framer Motion animations
- Responsive, accessible markup (WCAG AA)

## DeployAgent
- Docker Compose service definitions
- CI/CD pipeline scripts
- Daemon process management (npm run dev, uvicorn, gunicorn)
- Short-lived script execution with stdout/stderr capture
- Has access to `/var/run/docker.sock`

## SupportAgent
- Bug diagnosis and fix proposals
- Requires active support contract (post-launch 90-day or usage-based)
- Contract enforcement: checks before routing, consumes ticket on use

## CodeAgent
- General-purpose code generation and refactoring
- Language-agnostic (Python, TypeScript, Rust, Bash)
- Read-only project access

## FileAgent
- File read, create, move, delete operations
- Scoped to `/app/Projects/FileAgent` output directory
- Read-only on source, read-write on output

## Model Selection (all agents)
- Heavy tasks (architect, design, refactor, optimize, review, analyze): `claude-opus-4-6`
- Light tasks (rename, move, delete, list, simple, quick): `claude-haiku-4-5-20251001`
- Default: `claude-sonnet-4-6`
