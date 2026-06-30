# Data Protection Policy

## Encryption

| Data State | Method | Implementation |
|------------|--------|----------------|
| In transit | TLS 1.2/1.3 | nginx ssl termination, HSTS enforced |
| At rest (database) | PostgreSQL encryption | pgcrypto for PHI fields |
| At rest (files) | macOS FileVault | Full-disk encryption on host |
| At rest (backups) | AES-256 | Encrypted before offsite transfer |
| At rest (S3/MinIO) | Server-side encryption | MinIO SSE enabled |

## PHI Handling (HIPAA)

OrthoFlow processes Protected Health Information:
- Patient names, subscriber IDs, treatment records
- All PHI fields marked in data model with encryption-at-rest
- Access logged in `AuditLog` table (user, IP, timestamp, action)
- No PHI in logs, Slack messages, or agent proposals
- Data retention: per practice policy (minimum 6 years per HIPAA)

## Backup & Recovery

| Data | Frequency | Retention | Location |
|------|-----------|-----------|----------|
| PostgreSQL (kiro) | Daily | 30 days | Local + offsite |
| PostgreSQL (orthoflow) | Daily | 90 days | Local + offsite |
| MinIO objects | Continuous (versioned) | 1 year | Local |
| Docker volumes | Weekly | 14 days | Local |
| Git repos | On every push | Indefinite | GitHub (private) |

## Data Isolation

- Each OrthoFlow practice is isolated at application level (practice_id on every query)
- K8s: per-client namespace with separate database credentials (Enterprise tier)
- Agent system: project isolation enforced at filesystem + prompt level
- No cross-tenant data access possible without explicit practice_id in JWT

## Data Deletion

- Practice offboarding: all data deleted within 30 days of contract termination
- Right to deletion: supported via admin API (cascading delete + audit log entry)
- Backups containing deleted data expire per retention schedule

## Enforcement

- `AuditLog` table — immutable append-only log of all data access
- OrthoFlow JWT scopes access to single practice_id
- Agent guardrails block PII in proposals/Slack
- HUD security tab monitors for anomalous access patterns
