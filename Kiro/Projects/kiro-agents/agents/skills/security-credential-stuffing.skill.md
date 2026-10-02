# Threat Skill — Credential Stuffing / Brute Force

## Signature
Repeated authentication failures against login surfaces: HUD (`hud.melanin-tech.com`,
password + TOTP), OrthoFlow (`app.orthoflowsolutions.com`, JWT + SMS OTP), or any admin
endpoint. High rate of 401/403 from one or few IPs, or distributed low-and-slow attempts.

## Governance
Enforces `access-control-policy.md` (failed-login lockout via fail2ban, 10 attempts → 1hr ban;
JWT expiry 24hr HUD / 1hr OrthoFlow; MFA required on admin surfaces) and `network-policy.md`
(`nginx-http-auth` jail).

## Detection
- `nginx-http-auth` fail2ban jail bans
- Spike in 401/403 responses to `/api/auth`, `/api/login`, HUD login in the access log
- Recorded as `credential_stuffing` findings (P2 if a single account is targeted, P3 for spray)

## Analysis (Darius)
1. Determine target: single account (targeted) vs spray (many accounts, few tries each).
2. Confirm MFA is enforced on the targeted surface — if MFA is bypassable, that is P1.
3. Check for any successful auth (200 with token) from the attacking IP → P1 if present.
4. Assess source distribution (single IP vs botnet) to pick ban vs edge-WAF remediation.

## Remediation
- **Autonomous (allowlist):** `ban_ip <ip>` for IPs exceeding the auth-failure threshold.
- **Propose-only:** tightening the `nginx-http-auth` jail (lower maxretry / longer bantime),
  forcing a password reset on a targeted account, Cloudflare edge rate rule — via approval.

## Escalation
- Any successful login from an attacking IP → P1, alert CEO, propose session revocation +
  forced credential rotation (rotation itself is propose-only, never autonomous).
