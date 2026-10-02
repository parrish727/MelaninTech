# Phase Skill — Security Remediation

## Phase
`remediate` — turning an evaluated analysis into action. The security-agent executes;
Darius validates the remediation is safe, reversible, and within policy before/after.

## Decision Gate
```
Is the proposed action in the autonomous allowlist (ban_ip / restart_container / seal_endpoint)?
  ├── YES → is it reversible AND low false-positive risk (confidence ≥ threshold)?
  │         ├── YES → execute autonomously (self-healing), persist action_taken, alert Slack (informational)
  │         └── NO  → downgrade to propose-only
  └── NO  → propose-only: post to Slack with Approve/Dismiss, wait for human decision
```

## Autonomous Actions (allowlist — non-destructive, reversible)
- `ban_ip <ip>` → fail2ban jail add. Reversible via unban. Default for scanner/stuffing/ddos sources.
- `restart_container <name>` → clear hijacked/compromised/hung state. Reverts to known-good image only.
- `seal_endpoint <host>` → apply the nginx 444 lockdown pattern. Reversible by reloading prior config.

## Never Autonomous (always human-gated)
- Wiping `.env` / revoking all secrets (the kill switch) — Slack approval only
- Taking production offline
- Pulling/deploying a new image (deploy flows through GitHub → GHCR → Watchtower, via PR)
- Rotating credentials, resetting user passwords
- Any `git push` to main/production
- Anything matching `_BLOCKED_PATTERNS` (rm -rf, DROP TABLE, etc.)

## Evaluation Criteria (how Darius scores a remediation)
| Dimension | Weight | Pass condition |
|-----------|--------|----------------|
| Reversibility | 0.30 | Autonomous actions are fully reversible; rollback path stated |
| Policy compliance | 0.25 | Matches governance; no change-management or branch-protection bypass |
| Proportionality | 0.20 | Action matches severity; no overreach (e.g. no mass-ban on P4) |
| Verification plan | 0.15 | Defines how success is confirmed (ban present, endpoint sealed, service healthy) |
| Auditability | 0.10 | action_taken + evidence persisted to security_findings |

**Pass threshold: 0.70.** Below threshold → downgrade to propose-only and escalate to human.

## Post-Action Verification
After any action, confirm and persist the result:
- `ban_ip` → verify the IP appears in the jail's ban list
- `restart_container` → verify container is `running` + healthy
- `seal_endpoint` → verify probe paths now return 444 and the legit page still serves 200
Update the finding to `verified` (or `auto_remediated`) with evidence. If verification fails,
revert and escalate.

## Hard Rules
- Default to the least-disruptive effective action.
- Self-healing is bounded by the allowlist — it never grows to destructive actions.
- Every action is logged to `security_findings` for the Darius validation scorecard.
