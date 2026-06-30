# Code Agent Tools

Inherits: [shared.tools.md](shared.tools.md)

## Additional Capabilities

### Volume Mounts (read-only)
- `/app/Projects` — read access to all project source

### Scope
- General-purpose code generation (catches all tasks not routed to specialist agents)
- Language-agnostic: Python, TypeScript, Rust, Bash, SQL, YAML
- Refactoring, optimization, algorithm implementation
- Read-only — proposes code but cannot write directly
