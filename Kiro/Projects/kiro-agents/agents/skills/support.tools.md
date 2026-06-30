# Support Agent Tools

Inherits: [shared.tools.md](shared.tools.md)

## Additional Capabilities

### Volume Mounts (read-only)
- `/app/Projects` — read access to diagnose bugs

### Contract Gate
- Only processes tasks for clients with active support contracts
- Contract types: post_launch (90-day), usage (ticket-count based)
- Enforced by orchestrator before routing

### Bug Diagnosis
- Reads error logs, stack traces, and source code
- Proposes fixes with minimal code changes
- Focuses on root cause, not symptoms
