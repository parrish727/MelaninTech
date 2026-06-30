# Business Associate Agreement (BAA) — Policy & Requirements

## What Is a BAA

A Business Associate Agreement is a legally required contract under HIPAA (45 CFR §164.502(e), §164.504(e)). Any time a covered entity (healthcare practice) shares Protected Health Information (PHI) with a third party (business associate), both parties must execute a BAA **before** any PHI is transmitted.

**Melanin Technologies Inc. is a Business Associate** — OrthoFlow processes patient data (names, subscriber IDs, treatment records, insurance claims) on behalf of orthodontic practices.

---

## Who Requires a BAA

| Party | Relationship | Direction | Timing |
|-------|-------------|-----------|--------|
| Orthodontic practice (client) | Covered Entity → Us | They sign our BAA | Before go-live on OrthoFlow |
| Clearinghouse (Tesia/DentalXChange) | Us → Sub-processor | We sign their BAA | Before Medicare/Medicaid claims launch |
| Cloud hosting (AWS/GCP, if migrated) | Us → Sub-processor | We sign their BAA | Before migration |
| Offsite backup provider | Us → Sub-processor | We sign their BAA | Before enabling offsite backups |

### Not Required Currently

- **Self-hosted infrastructure** (Mac Pro) — no third-party data handler
- **Cloudflare** — DNS-only mode, no PHI access (encrypted passthrough)
- **Slack** — no PHI transmitted (enforced by agent-rules.md)
- **GitHub** — private repos, no PHI in code (enforced by guardrail-check)

---

## BAA Contents (Required Elements per HHS)

1. **Permitted uses and disclosures** — BA may only use PHI as needed to perform services
2. **Safeguards** — BA must implement administrative, physical, and technical safeguards
3. **Reporting** — BA must report any unauthorized use, disclosure, or breach
4. **Breach notification** — within 60 days of discovery, notify covered entity
5. **Subcontractor flow-down** — BA must ensure subcontractors agree to same restrictions
6. **Access rights** — BA must make PHI available to individuals who request it
7. **Amendment** — BA must accommodate amendments to PHI when directed
8. **Accounting of disclosures** — BA must document and make available
9. **HHS access** — BA must make practices/records available to HHS for compliance review
10. **Return/destruction** — on termination, return or destroy all PHI (or document why retention is needed)
11. **Termination** — covered entity may terminate if BA violates agreement

---

## Our Compliance Position

| Requirement | Our Implementation |
|-------------|-------------------|
| Administrative safeguards | Governance policies, agent-rules.md, change management |
| Physical safeguards | FileVault encryption, locked server location |
| Technical safeguards | TLS, pgcrypto, JWT+MFA, RBAC, audit logging |
| Breach detection | HUD monitoring, fail2ban, watchdog alerts |
| Breach notification | incident-response-policy.md (P1 procedure) |
| Data isolation | practice_id scoping, K8s namespaces (Enterprise) |
| Data destruction | Cascading delete API + backup expiry per retention schedule |
| Subcontractor management | BAA required with clearinghouse before claims processing |

---

## Process

1. BAA template lives at: `MelaninDocs/Onboarding/BAA_Template.md`
2. Included in OrthoFlow client onboarding flow
3. Signed digitally (DocuSign or equivalent) before practice activation
4. Stored for 6 years minimum (HIPAA retention requirement)
5. Reviewed annually for updates

---

*Last updated: May 29, 2026*
