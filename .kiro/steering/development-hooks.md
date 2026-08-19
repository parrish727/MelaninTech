---
inclusion: fileMatch
fileMatchPattern: "**/.kiro/hooks/**,**/hooks*"
description: "Development hooks configuration and automated quality gates."
---

# Development Hooks

## Active Hooks

### Automated Quality Gates (on file save)

| Hook | Trigger | Action | File |
|------|---------|--------|------|
| Python Lint | `**/*.py` saved | `ruff check` | `.kiro/hooks/python-lint.json` |
| TypeScript Check | `**/*.ts,**/*.tsx` saved | `tsc --noEmit` | `.kiro/hooks/typescript-check.json` |
| Docker Validate | `**/docker-compose*,**/Dockerfile*` saved | `docker compose config --quiet` | `.kiro/hooks/docker-validate.json` |

### Governance (preToolUse)

| Hook | Trigger | Action | File |
|------|---------|--------|------|
| Guardrail Check | Any write tool | Verify hard constraints | `.kiro/hooks/governance-guard.json` |

### Documentation Sync (on infrastructure change)

| Hook | Trigger | Action | File |
|------|---------|--------|------|
| Sync Docs v2.0 | Infrastructure/agent/steering file edits | Update related docs (Glossary, Architecture, Onboarding, SRE) | `.kiro/hooks/sync-docs.json` |

### Manual Triggers (userTriggered)

| Hook | Purpose | File |
|------|---------|------|
| Environment Verify | Check all tools/services running | `.kiro/hooks/environment-verify.json` |

## Hook Design Principles

1. **Fast** — hooks should complete in < 10 seconds
2. **Non-blocking** — failures warn but don't prevent work
3. **Focused** — one concern per hook (lint OR test, not both)
4. **Idempotent** — safe to run repeatedly without side effects
5. **Silent on success** — only report when there's a problem

## Adding New Hooks

Hooks use this schema:
```json
{
  "name": "Hook Name",
  "version": "1.0.0",
  "description": "What it does",
  "when": {
    "type": "fileEdited|fileCreated|fileDeleted|userTriggered|promptSubmit|agentStop|preToolUse|postToolUse",
    "patterns": ["glob patterns"],
    "toolTypes": ["read", "write", "shell", "web", "spec", "*"]
  },
  "then": {
    "type": "askAgent|runCommand",
    "prompt": "for askAgent",
    "command": "for runCommand"
  }
}
```

## Planned Hooks (Not Yet Implemented)

- K8s manifest validation (`kubectl --dry-run`) on `.yaml` saves in `k8s/`
- shellcheck on `.sh` file saves
- Secret detection on all file writes (block if credential patterns found)
- Test runner on `*_test.py` or `*.test.ts` saves
