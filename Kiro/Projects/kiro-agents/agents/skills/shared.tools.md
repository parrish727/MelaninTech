# Standard Agent Tools

All agents built on `base_agent.py` share these capabilities:

## LLM Generation
- Model selection based on task complexity (light/default/heavy)
- Anthropic Claude via direct API or OpenRouter
- Blocked: any `openai/` model name

## MCP Context Injection
- `project_info` — fetched automatically, prepended to every prompt
- `recall_memory` — similar past tasks retrieved from pgvector

## Guardrails (enforced on every proposal)
- **Model guard** — rejects OpenAI model names
- **Path guard** — blocks writes outside `/app/Projects` and registered project paths (symlink-safe via `os.path.realpath`)
- **Proposal guard** — scans output for destructive patterns: `rm -rf`, `DROP TABLE`, `DROP DATABASE`, `TRUNCATE`, `format /`, `mkfs`

## Heartbeat
- Sends pulse to orchestrator every 15s while LLM is generating
- Prevents watchdog from restarting the container during long tasks

## File Writing (on approval)
- Orchestrator parses fenced code blocks with path comments
- Writes each block to the correct file path under the project directory
- `os.makedirs(..., exist_ok=True)` for parent directories

## Project Isolation
- Each agent receives only the project context for the assigned task
- Volume mounts are scoped per-agent (ro/rw as appropriate)
- Cross-project access is blocked at the filesystem level
