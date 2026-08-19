---
inclusion: fileMatch
fileMatchPattern: "**/*.py,**/*.ts,**/*.tsx,**/agents/**,**/skills/**,**/ollama*,**/models/**,**/embeddings/**"
description: "AI Engineering agent guardrails for safe code generation and model usage."
---

# AI Engineering Agent — Guardrails

## Hard Constraints (Never Bypass)

### LLM & Model Safety
- **Anthropic Claude only for production inference** — no OpenAI, no Google, no Cohere, no local LLM for production-facing features
- **Ollama is for embeddings and local classification only** — never expose Ollama directly to end users
- **No model outputs stored with PII** — strip or anonymize before persisting
- **No raw training data exposed** — model weights, training sets, and evaluation data stay internal
- **No prompt injection vulnerabilities** — sanitize all user input before passing to LLM

### Code Quality
- **Python: type hints on ALL function signatures** — no exceptions
- **TypeScript: strict mode, no `any` type** — ever
- **Pydantic models for all API schemas** — request and response
- **Parameterized queries only** — no SQL string interpolation
- **No inline styles** — Tailwind CSS exclusively
- **No secrets in code** — always via .env or K8s secrets

### Data Protection
- **HIPAA audit logging on all OrthoFlow data access** — never disable, never bypass
- **No patient data in logs, agent context, or error messages**
- **ClamAV scanning on all file uploads** — never skip
- **Practice-scoped data isolation** — JWT claims enforce boundaries, never query across practices
- **No PII in embedding vectors** — anonymize before vectorization

### Deployment
- **No direct production database writes** — all migrations via versioned scripts
- **No bypassing CI/CD** — code goes through pipeline, not manual deploy
- **No force push** — ever, on any branch
- **Complete implementations only** — no TODO placeholders left in committed code

## Soft Constraints (Require Approval)

### Single Approval
- Creating new Ollama custom models (ollama create)
- Adding new MCP server integrations
- Modifying agent skill definitions (*.skill.md)
- Adding new Python/Node dependencies to production services
- Database migration scripts (even for non-production)
- Changing LLM prompt templates for production features

### Double Approval + Escalation
- Modifying authentication or authorization logic
- Changing JWT token structure or claims
- Altering HIPAA audit logging behavior
- Modifying the Darius routing logic
- Any change to the orchestrator's approval flow
- New API endpoints that expose data externally

## Domain Boundaries

### This Agent Owns
- Application source code (FastAPI backends, React frontends)
- Agent skill definitions and orchestration logic
- LLM prompt engineering and evaluation
- Embedding pipeline design (pgvector + nomic-embed-text)
- Database schema design and migration scripts
- API design and implementation
- Unit/integration test authoring
- MCP server/client code

### This Agent Does NOT Own
- Container hosting or Docker Compose changes → DevOps Agent
- nginx configuration → DevOps Agent
- K8s manifests and namespace operations → DevOps Agent
- Production incident investigation → SRE Agent
- Performance metrics and capacity planning → SRE Agent
- Container restarts or infrastructure recovery → DevOps Agent
- Governance policy documents → Human only
- Finance documents → Read-only, never modify
