# Threat Skill — Secret Scanner / Bot Probing

## Signature
Automated requests probing for exposed secrets/config: `.env`, `.env.save`, `.env.prod`,
`/config/*`, `credentials.json`, `smtp_credentials`, `mailgun`, `sendgrid`, `stripe`,
`/wp-*`, `/.git`, `/.aws`, `id_rsa`, `*.sql`, `/_cat/`. Often from AI crawler bots
(DeepSeekBot, PanguBot, Bytespider, GPTBot) or scanners (sqlmap, nikto, nuclei, wpscan).

## Governance
Enforces `network-policy.md` (fail2ban jails, rate limiting) and `secrets-policy.md`
(no secrets in source; `.env` gitignored; vault at emerald.melanin-tech.com is source of truth).

## Detection
- `nginx-botsearch` fail2ban jail bans on the access log (real client IP via CF-Connecting-IP)
- nginx 403/444 responses to dotfile/config/CMS probe patterns
- Recorded as `secret_scanner` findings (severity P3 — blocked attempts)

## Analysis (Darius)
1. Confirm the probed paths map to no real exposed resource (verify the secret is NOT reachable).
2. Verify `.gitignore` + nginx deny rules are intact for the probed patterns.
3. Assess volume/distribution — single IP vs distributed botnet.
4. Confirm no 200 responses to any secret path (a 200 = P1 escalation to secret_leak).

## Remediation
- **Autonomous (allowlist):** `ban_ip <ip>` for repeat offenders; `seal_endpoint <host>`
  to apply the 444 lockdown pattern to a heavily-probed hostname.
- **Propose-only:** adding new nginx deny patterns, Cloudflare edge WAF rules, UA blocklists.

## Escalation
- Any secret path returning 200/300 → immediately reclassify as `secret_leak` P1.
- Distributed attack exceeding rate zones across multiple LOBs → propose Cloudflare edge WAF.
