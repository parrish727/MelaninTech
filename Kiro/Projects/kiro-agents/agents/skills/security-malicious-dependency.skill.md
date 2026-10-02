# Threat Skill — Malicious Dependency / Trojan / Supply-Chain

## Signature
Poisoned or trojaned packages entering the build: typosquatted names, newly-published
versions with install-time scripts, dependencies pulling unexpected network egress, or a
lockfile change that adds an unknown transitive package. Especially relevant for an agentic
company: a compromised package in an agent image can exfiltrate secrets or hijack tools.

## Governance
Enforces `change-management-policy.md` (all changes via feature → PR → CI → merge; no direct
pushes) and `secrets-policy.md` (no credential exposure). Dependencies pinned to exact versions.

## Detection
- Trivy scans in CI flag HIGH/CRITICAL CVEs (backend + frontend images)
- Unexpected dependency added in a PR diff (lockfile delta without a corresponding ticket)
- Container making outbound connections not in its documented egress profile
- Recorded as `malicious_dependency` findings (severity P1 if in a running image, P2 in a PR)

## Analysis (Darius)
1. Identify the package, version, and how it entered (PR, direct install, base image).
2. Check for typosquatting (name similarity to a known-good package) and publish recency.
3. Inspect for install-time scripts, obfuscated code, or unexpected network/filesystem access.
4. Determine blast radius — which agent images/containers include it.
5. Cross-reference the Trivy `.trivyignore` — is this a known-accepted CVE or a new one?

## Remediation
- **Autonomous (allowlist):** `restart_container <name>` only to roll back to a known-good
  image already present (self-healing); never to pull a new image autonomously.
- **Propose-only:** pin/downgrade/remove the dependency, rebuild image, update `.trivyignore`
  with documented reasoning — all via PR through CI (never bypass change-management).

## Escalation
- Confirmed malicious package in a running production image → P1, alert CEO, propose immediate
  rollback PR to the last known-good image tag; do NOT auto-deploy.
- Pin all deployment through GitHub → GHCR → Watchtower; never local docker build.
