# Threat Skill — DDoS / Rate-Limit Abuse

## Signature
Volumetric or sustained request floods tripping nginx rate limiting repeatedly: many
`limiting requests` entries in the error log, excessive concurrent connections, or a single
IP/subnet generating disproportionate load across one or more LOBs.

## Governance
Enforces `network-policy.md` (rate zones: general 30 req/min, contact 5 req/min;
`nginx-limit-req` jail: 10 rate-limit hits → ban) and the per-LOB `limit_req`/`limit_conn`
directives already in the nginx configs.

## Detection
- `nginx-limit-req` fail2ban jail bans
- High count of `limiting requests` in the nginx error log over a short window
- `Excessive bans` threshold crossed (watchdog `check_fail2ban_bans`, MAX_FAILED_BANS)
- Recorded as `ddos_ratelimit` findings (P3 normally, P2 if a service's availability degrades)

## Analysis (Darius)
1. Quantify: requests/min, distinct source IPs, which hostnames/paths are targeted.
2. Determine if origin is actually degraded (cross-check with SRE latency) or fully absorbed
   by rate limiting (site still 200). Absorbed = P3; degraded = P2 and coordinate with SRE.
3. Single-source vs distributed — picks ban (local) vs Cloudflare edge (effective for proxied).
4. Confirm Cloudflare proxy is active for the targeted LOB (edge absorbs volumetric best).

## Remediation
- **Autonomous (allowlist):** `ban_ip <ip>` for top offenders; `seal_endpoint <host>` to apply
  the 444 lockdown if a specific endpoint is being hammered with junk.
- **Propose-only:** tightening rate zones, Cloudflare edge rate rules / "Under Attack" mode,
  adjusting `limit_conn` — via approval.

## Escalation
- Service availability degraded (not just rate-limited) → P2, coordinate with SRE Agent, and
  propose Cloudflare edge mitigation (requires the full-scope CF API token — currently pending).
- Distributed botnet beyond local fail2ban capacity → propose edge WAF; local bans are triage.
