# Darius Agent Tools

## read_file
Read file contents (50KB cap). Use for checking configs, code, specs before acting.

## write_file
Write content to a file. Creates parent dirs. Blocked: `rm -rf /`, `mkfs`, `DROP TABLE/DATABASE`.

## list_dir
List directory contents. Use for exploring project structure.

## shell
Execute shell commands (60s timeout). Confirmation required for: `rm`, `git push/reset`, `docker rm/stop`, `DROP`, `TRUNCATE`, `DELETE FROM`.

## git
Run git commands in a repo. Confirmation required for push/reset/force operations.

## mcp
Call any MCP tool via proxy (http://mcp-server:9000). Available: list_files, read_file, recall_memory, project_info, web_fetch, shell_exec, github, postgres_mcp, figma_mcp, fetch_mcp.

## dispatch
Delegate to specialist agents: frontend, backend, scaffold, deploy, support, code, file. Returns their proposal for review. Timeout: 120s.
