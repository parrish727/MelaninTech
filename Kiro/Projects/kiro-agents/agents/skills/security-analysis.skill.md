# Phase Skill — Security Analysis

## Phase
`analyze` — Darius reasons over a security finding routed by the security-agent and produces
a structured, evidence-grounded assessment before any remediation is proposed.

## Inputs
- Live security posture (open findings, fail2ban bans, container/socket state)
- The relevant `governance/*.md` policy (loaded and passed in by the security-agent)
- The specific finding/task to analyze

## Required Output Structure
1. **Threat classification** — one of the 8 threat classes; cite the matching threat skill.
2. **Root cause** — what happened, with concrete evidence (IPs, paths, status codes, timestamps,
   container names). No speculation presented as fact; state what was checked vs assumed.
3. **Governance reference** — the exact policy and rule being enforced or violated.
4. **Blast radius** — which systems/LOBs are affected; is anything actually compromised vs blocked.
5. **Proposed remediation** — mapped to the autonomous allowlist (ban_ip/restart_container/
   seal_endpoint) OR explicitly flagged propose-only (human approval required).
6. **False-positive / risk assessment** — likelihood this is benign; risk of the proposed action.

## Evaluation Criteria (how Darius scores this analysis)
| Dimension | Weight | Pass condition |
|-----------|--------|----------------|
| Evidence grounding | 0.30 | Every claim backed by a concrete artifact (log line, status, ID) |
| Governance alignment | 0.25 | Correct policy cited; enforcement matches the policy as written |
| Classification accuracy | 0.20 | Threat class matches the signature in the threat skill |
| Remediation safety | 0.15 | Autonomous actions strictly within allowlist; destructive = propose-only |
| False-positive handling | 0.10 | FP risk assessed; low-confidence findings not auto-actioned |

**Pass threshold: 0.70.** Below threshold → revise (gather more evidence) or reject (insufficient
signal, close as informational).

## Hard Rules
- Never invent policy — enforce only what exists in `governance/*.md`.
- Never recommend exposing a secret value; reference by name.
- Never classify a destructive action as autonomous.
- If guardrails (`_guard_proposal`/`_guard_path`) failed to catch an attack, that gap is itself
  a P1 finding — surface it explicitly.
