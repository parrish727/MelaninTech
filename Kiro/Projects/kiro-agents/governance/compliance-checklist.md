# Compliance Checklist

## HIPAA (OrthoFlow — handles PHI)

| Control | Requirement | Implementation | Status |
|---------|-------------|----------------|--------|
| §164.312(a)(1) | Access Control | JWT + RBAC (owner/manager/bookkeeper) | ✅ |
| §164.312(a)(2)(i) | Unique User ID | UUID per user, practice-scoped JWT | ✅ |
| §164.312(a)(2)(iii) | Auto Logoff | JWT 1hr expiry | ✅ |
| §164.312(a)(2)(iv) | Encryption | TLS in transit, pgcrypto at rest | ✅ |
| §164.312(b) | Audit Controls | AuditLog table — every access logged | ✅ |
| §164.312(c)(1) | Integrity | Immutable invoice records, versioned S3 | ✅ |
| §164.312(d) | Authentication | SMS OTP MFA + password | ✅ |
| §164.312(e)(1) | Transmission Security | TLS 1.2+ enforced, HSTS | ✅ |
| §164.308(a)(1) | Risk Analysis | This governance directory | ✅ |
| §164.308(a)(5) | Security Awareness | Agent rules + guardrail automation | ✅ |
| §164.310(d)(1) | Device Controls | FileVault, Docker isolation | ✅ |
| §164.314(a) | BAA Required | Needed for: hosting provider, clearinghouse | ⚠️ Pending |

## SOC 2 Type II (Trust Service Criteria)

| Criteria | Requirement | Implementation | Status |
|----------|-------------|----------------|--------|
| CC6.1 | Logical Access | JWT + 2FA + RBAC + network isolation | ✅ |
| CC6.2 | Access Provisioning | Manual (CEO only) — documented | ✅ |
| CC6.3 | Access Removal | JWT expiry + manual revocation | ✅ |
| CC6.6 | Encryption | TLS + at-rest encryption | ✅ |
| CC7.1 | Change Management | Approval pipeline + guardrail hooks | ✅ |
| CC7.2 | Monitoring | HUD + watchdog + fail2ban + Slack alerts | ✅ |
| CC7.3 | Incident Response | incident-response-policy.md | ✅ |
| CC8.1 | System Operations | Docker Compose + restart policies | ✅ |
| A1.1 | Availability | restart: unless-stopped, watchdog auto-recovery | ✅ |
| A1.2 | Recovery | Backups + git history + container rebuild | ✅ |
| P1-P8 | Privacy | Data isolation, retention, deletion procedures | ✅ |

## CMS (Medicare/Medicaid — OrthoFlow Claims)

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| HIPAA 837D format | X12 5010 claim generation | ✅ Built |
| NPI validation | Luhn check + NPPES lookup | ✅ Built |
| Fee schedule enforcement | State rules engine | ✅ Built |
| Timely filing tracking | Configurable deadline alerts | ✅ Built |
| Audit trail for claims | AuditLog extension | ✅ Built |
| PHI encryption (subscriber IDs) | pgcrypto field-level | ✅ Built |
| Clearinghouse integration | API submission to vendor | ⚠️ Pending vendor enrollment per practice |
| Denial detection | AI-powered denial pattern recognition | ✅ Built |
| Appeal writing | AI-drafted appeal letters | ✅ Built |
| ERA/835 processing | Payment posting from remittance advice | ✅ Built |

## TCPA (OrthoFlow — Patient Communications)

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Prior express written consent | Digital consent capture with timestamp + IP | ✅ Built |
| Opt-out mechanism | STOP keyword processing, one-click unsubscribe | ✅ Built |
| Consent revocation | Immediate opt-out honored, audit logged | ✅ Built |
| Time-of-day restrictions | Quiet hours enforcement (before 8am / after 9pm local) | ✅ Built |
| SMS messaging | Two-way texting infrastructure | ⚠️ Disabled pending legal review |
| Email reminders | Automated appointment/payment reminders | ✅ Active |
| Message templates | Pre-approved template library | ✅ Built |
| Delivery tracking | Dashboard with delivery/bounce/opt-out metrics | ✅ Built |
| Do-Not-Call list | DNC registry check integration | ✅ Built |

## Imaging (OrthoFlow — Phase 4a)

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| PHI protection (stored images) | MinIO server-side encryption enabled | ✅ |
| PHI protection (DICOM export) | De-identification on export (strips patient metadata) | ✅ |
| Access control | Practice-scoped, role-gated image access | ✅ |
| Audit trail | All image view/upload/download events logged | ✅ |
| Retention policy | Configurable per practice (default: 7 years) | ✅ |
| Secure upload | ClamAV scan on all uploaded files | ✅ |

## Infrastructure Security

| Control | Implementation | Status |
|---------|----------------|--------|
| Container least-privilege | cap_drop: ALL, read_only, tmpfs | ✅ |
| No root containers | Non-root where possible | ⚠️ Some agents run as root |
| Docker socket access limited | Only orchestrator, HUD, deploy-agent | ✅ |
| Network segmentation | Docker bridge (no port exposure for internal) | ✅ |
| DDoS protection | Cloudflare + nginx rate limiting | ✅ |
| Brute force protection | fail2ban (3 jails active) | ✅ |
| TLS cert auto-renewal | certbot + cert-monitor alerts | ✅ |
| Secret scanning | guardrail-check.yaml on every change | ✅ |
| Dependency pinning | Docker images pinned, npm lockfiles | ✅ |
| Vulnerability scanning | Trivy in GitHub Actions CI (OrthoFlow), pre-deploy image scan | ✅ |

## Gaps to Address

1. **BAA agreements** — need signed BAAs with clearinghouse vendors (per practice, upon enrollment)
2. **Non-root containers** — migrate remaining agents to non-root user in Dockerfile
3. **Formal penetration test** — schedule annually
4. **Disaster recovery test** — validate backup restore procedure quarterly
5. **SMS legal review** — patient SMS messaging disabled until TCPA compliance review complete
