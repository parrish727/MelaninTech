---
inclusion: auto
description: "Shared behavioral rules for all agents covering planning, risk assessment, and code review."
---

# Shared — Agent Behavior Standards

These behavioral rules apply to ALL agents in the framework (DevOps, SRE, AI Engineering, Darius).
They govern how agents approach planning, risk assessment, and code review.

---

## 1. Planning Confidence Gate

**Do not create a plan until you have over 96% confidence you understand what to plan for.**

Before proposing any implementation plan, architecture change, or multi-step workflow:

- Ask follow-up questions as if you are speaking with a Principal Engineer / Architect / CTO
- Keep questions focused and on-topic — do not go down rabbit holes or explore subtopics
- Make appropriate, relevant assumptions along the way and state them explicitly
- Each question should meaningfully increase your confidence toward the 96% threshold
- Once you reach sufficient confidence, state your assumptions and proceed with the plan

**Anti-patterns (don't do these):**
- ❌ Generating a plan immediately on first message
- ❌ Asking 10+ questions before starting (keep it tight — 2-4 targeted questions)
- ❌ Asking obvious questions that are answered by the codebase or context
- ❌ Going down tangential subtopics unrelated to the core task
- ❌ Asking about things you can look up yourself (file structure, existing patterns, etc.)

**Good patterns:**
- ✅ "I'll assume X based on the existing codebase. Is that correct, or should I handle Y differently?"
- ✅ "Two things I need to confirm before planning: [specific question 1] and [specific question 2]"
- ✅ "Based on the current architecture, I'm going to approach this as [brief summary]. Any constraints I'm missing?"
- ✅ Reading existing code first, then asking only what you can't determine from context

---

## 2. Risk Assessment Before Implementation

**After creating a plan, identify areas that introduce the most product risk.**

Before executing any plan, perform this risk assessment step:

1. Review the full plan
2. Identify all areas that introduce product risk (data loss, downtime, security exposure, breaking changes, user-facing regressions)
3. List risks from **most to least critical**
4. For each risk item, add a specific mitigation to the plan that reduces implementation risk

**Risk categories to evaluate:**
- **Data integrity** — Can this corrupt, lose, or expose data?
- **Availability** — Can this cause downtime for any production service?
- **Security** — Does this weaken authentication, authorization, or encryption?
- **Breaking changes** — Does this break existing APIs, contracts, or integrations?
- **User experience** — Can this cause user-facing regressions or confusion?
- **Reversibility** — If this fails, how hard is it to roll back?
- **Blast radius** — How many services/users are affected if this goes wrong?

**Output format:**
```
## Risk Assessment

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | [highest risk item] | Critical/High/Medium | [specific mitigation added to plan] |
| 2 | ... | ... | ... |
```

After listing risks, **update the plan** to include the mitigations as explicit steps (rollback procedures, feature flags, staged rollouts, backup steps, etc.).

---

## 3. Code Review Before Completion (SRE / DevOps / Darius)

**Before finalizing any implementation, perform a thorough code review.**

This applies to the SRE Agent, DevOps Agent, and Darius when they are executing or reviewing implementation work. When code is being written or has been written:

1. Review all changed/created files as a Senior Engineer would
2. Identify ALL of the following:
   - **Errors** — Logic bugs, runtime exceptions, type mismatches, missing error handling
   - **Inconsistent logic** — Contradictions between components, mismatched assumptions, race conditions
   - **Inefficiencies** — N+1 queries, unnecessary re-renders, redundant computations, excessive memory allocation
   - **Bug risks** — Edge cases not handled, null/undefined access, off-by-one errors, concurrency issues
   - **Security concerns** — Injection vectors, missing validation, exposed secrets, privilege escalation
   - **Standard violations** — Deviations from the coding standards defined in the framework

3. Prioritize findings from **most critical to least critical**:
   - 🔴 **Critical** — Will cause failures, data loss, or security vulnerability
   - 🟡 **High** — Likely to cause bugs under normal usage
   - 🟠 **Medium** — Inefficiency or inconsistency that degrades quality
   - 🔵 **Low** — Style, naming, or minor improvement

4. **Fix all critical and high issues before presenting the result**
5. List medium and low issues with recommendations (fix or defer)

**Output format:**
```
## Code Review Findings

| # | Severity | File | Issue | Resolution |
|---|----------|------|-------|------------|
| 1 | 🔴 Critical | path/to/file.py | [description] | [fixed / fix applied] |
| 2 | 🟡 High | path/to/file.ts | [description] | [fixed / fix applied] |
| 3 | 🟠 Medium | path/to/file.py | [description] | [recommendation] |
```

**Rules:**
- Critical and High findings are fixed immediately — do not present code with known critical bugs
- Never skip this review for multi-file changes
- For single-file, small changes (< 20 lines), a mental check is sufficient (no formal table needed)
- The review happens BEFORE presenting the final result, not after
