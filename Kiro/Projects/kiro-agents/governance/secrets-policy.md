# Secrets Policy

## Rules

1. **No secrets in source code.** All credentials live in `.env` files (legacy) or Vaultwarden vault (primary).
2. **Vaultwarden** at `https://emerald.melanin-tech.com` is the primary secret store — encrypted, zero-knowledge, RBAC-capable.
3. **`.env` is in `.gitignore`** — retained as runtime injection mechanism, backed by vault as source of truth.
4. **Agent guardrail scans** for hardcoded patterns: API keys, tokens, passwords, DSN strings.
5. **Slack messages** must redact secrets with `<REDACTED>` — enforced in agent-rules.md.
6. **Docker Compose** uses `${VARIABLE}` interpolation from `--env-file` — never inline values.

## Secret Store

- **Primary:** Vaultwarden (self-hosted Bitwarden) at `https://emerald.melanin-tech.com`
- **Runtime:** `.env` file on host (pulled from vault, injected into containers)
- **Backup:** Vault data persisted in Docker volume `vaultwarden-data`
- **Access:** Master password + optional 2FA (Bitwarden clients: web, mobile, browser extension)

## Secret Inventory

| Secret | Vault Folder | Rotation Schedule |
|--------|--------------|-------------------|
| ANTHROPIC_API_KEY | LLM | On compromise only |
| OPENROUTER_API_KEY | LLM | On compromise only |
| SLACK_BOT_TOKEN | Slack | On compromise only |
| SLACK_APP_TOKEN | Slack | On compromise only |
| SLACK_SIGNING_SECRET | Slack | On compromise only |
| POSTGRES_PASSWORD | Infrastructure | Quarterly |
| HUD_PASSWORD | Infrastructure | Quarterly |
| HUD_TOTP_SECRET | Infrastructure | On compromise only |
| CF_API_TOKEN | Infrastructure | Annually |
| GITHUB_TOKEN | Integrations | 90 days (GitHub enforced) |
| FIGMA_ACCESS_TOKEN | Integrations | Annually |
| VAULTWARDEN_ADMIN_TOKEN | Vault | On compromise only |

## Enforcement

- `guardrail-check.yaml` — scans for secret patterns on every agent/orchestrator file change
- `.gitignore` — blocks `.env`, `*.pem`, `*.key`, `credentials*`
- `agent-rules.md` — hard rule: "Never expose secrets, API keys, credentials, or PII"
- Docker volumes mount `.env` as read-only (`:ro`)
- Vaultwarden vault encrypted with AES-256 (zero-knowledge — server never sees plaintext)

## Rotation Procedure

1. Generate new credential
2. Update in Vaultwarden vault
3. Update `.env` on host to match
4. `docker compose up -d` (picks up new env on container restart)
5. Verify service health via HUD
6. Revoke old credential at provider
