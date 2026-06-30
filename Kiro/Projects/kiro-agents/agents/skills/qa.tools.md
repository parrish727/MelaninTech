# QA Agent Tools

Inherits: [shared.tools.md](shared.tools.md)

## Additional Capabilities

### Read-Only Access (all projects)
- `/app/Projects` (ro)
- `/app/melanin-tech-website` (ro)
- `/app/orthoflow-frontend` (ro)
- `/app/orthoflow-backend` (ro)

### Testing Scope
- Code review against agent-rules.md standards
- TypeScript strict mode compliance checks
- Python type hint verification
- Input validation presence on API routes
- File path comment format verification
- Destructive pattern scanning
- Security review (secrets, path traversal, injection)

### Runs After
- Triggered automatically after every approved proposal execution
