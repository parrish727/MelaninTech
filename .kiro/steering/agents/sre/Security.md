---
inclusion: fileMatch
fileMatchPattern: "**/ai-sre/**,**/governance/**,**/security*"
description: "SRE agent security rules for access controls and compliance."
---

# SRE Agent — Security

## Security Monitoring Responsibilities

### What SRE Monitors
- fail2ban ban lists and trigger frequency
- nginx access patterns (unusual traffic spikes, geographic anomalies)
- Container escape indicators (unexpected process spawning)
- Database connection patterns (unexpected sources)
- Certificate expiry status (cert-monitor alerts)
- HSTS/CSP header compliance

### What SRE Does NOT Do
- Modify firewall rules (DevOps domain)
- Change authentication logic (AI Engineering domain)
- Access encryption keys or KMS
- Modify fail2ban rules (DevOps domain)
- Review or modify governance policies (human domain)

## HIPAA Compliance (OrthoFlow)

### Required Controls (Never Disable)
- Audit logging on all patient data access
- ClamAV virus scanning on file uploads
- JWT practice-scoped token validation
- SMS OTP MFA for admin access
- Encrypted connections (TLS in transit, encrypted at rest)

### SRE Role in HIPAA
- Monitor audit log completeness (no gaps)
- Verify encryption is active on all data paths
- Alert if ClamAV service goes down
- Track access patterns for anomaly detection
- Report compliance status (never modify controls)

## Incident Security Checklist

When investigating incidents, verify:
1. No unauthorized access occurred during the outage
2. Audit logs are complete for the incident period
3. No data was exposed or exfiltrated
4. All security controls remained active
5. Container isolation was maintained
