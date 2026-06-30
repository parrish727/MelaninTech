# DariusHUD — Tools

## Available Tools

### read_file
Read contents of any file in the project tree (capped at 50KB).
- **Use for:** Checking configs, reading specs, reviewing code before suggesting changes.

### write_file
Write content to a file, creating parent directories as needed.
- **Use for:** Generating reports, updating configs, creating new files.
- **Blocked patterns:** `rm -rf /`, `mkfs`, `DROP TABLE`, `DROP DATABASE`

### list_dir
List files and directories at a given path.
- **Use for:** Exploring project structure, finding relevant files.

### shell
Execute shell commands (60s timeout). Destructive commands require confirmation.
- **Use for:** Running scripts, checking system state, git operations.
- **Confirmation required:** `rm`, `git push`, `git reset`, `docker rm`, `docker stop`, `DROP`, `TRUNCATE`, `DELETE FROM`

### git
Run git commands in a repo directory.
- **Use for:** Checking status, viewing logs, creating branches.
- **Confirmation required:** push, reset, force operations.

### mcp
Call any MCP skill via the Kiro MCP proxy server.
- **Available MCP tools:** list_files, read_file, recall_memory, project_info, web_fetch, shell_exec, github, postgres_mcp, figma_mcp, fetch_mcp
- **Use for:** Querying semantic memory, fetching web content, GitHub operations, database queries, Figma design access.

### dispatch
Dispatch a task to a specialist agent and receive their proposal.
- **Available agents:** frontend, backend, scaffold, deploy, support, code, file
- **Use for:** Delegating well-defined tasks instead of writing code directly.
- **Returns:** The agent's proposal (code/plan), which can be reviewed before execution.

## Tool Selection Guidelines

| Scenario | Tool |
|----------|------|
| Need to check a file before answering | `read_file` |
| User asks about system state | `shell` (docker ps, etc.) |
| Need historical context | `mcp` → recall_memory |
| User wants code written | `dispatch` → appropriate agent |
| Need to verify a deployment | `shell` → curl/docker logs |
| Database query needed | `mcp` → postgres_mcp |
| Need to look something up online | `mcp` → fetch_mcp |

## Guardrails

- Never execute destructive commands without confirmation callback approval
- Path traversal blocked — `os.path.realpath` enforced on all file operations
- Shell output capped at 8KB stdout, 2KB stderr
- MCP responses capped at 10KB
- Agent dispatch timeout: 120s
- All blocked patterns raise `ValueError` immediately
