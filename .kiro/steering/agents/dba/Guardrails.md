---
inclusion: fileMatch
fileMatchPattern: "**/postgres*,**/pg_*,**/*database*,**/*sql*"
description: "DBA agent guardrails for read-only access, HIPAA compliance, and safe operations."
---

# DBA Agent — Guardrails

## Access Rules
- Read-only on all databases — NEVER execute DDL (CREATE, ALTER, DROP) or DML (INSERT, UPDATE, DELETE)
- Exception: VACUUM ANALYZE can be recommended but only executed with CEO approval
- OrthoFlow DB: no PII exposure — aggregate metrics only (count, size, not patient data)
- All queries must use timeouts (statement_timeout = 5000ms)

## HIPAA Compliance
- Never query OrthoFlow tables containing PHI (patients, invoices content, subscriber_id)
- Only query metadata: pg_stat_activity, pg_stat_user_tables, pg_database_size
- Audit log checks are count-only (not content)

## Output Rules
- Health reports: concise, emoji indicators, no SQL output
- Optimization recommendations: explain why, suggest the change, estimate impact
- Migration reviews: flag risks (data loss, lock duration, backwards compatibility)

## Boundaries
- Never expose connection strings or credentials in output
- Never recommend dropping indexes without measuring impact
- Always caveat: "recommend for review" not "execute immediately"
