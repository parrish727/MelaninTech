# Revisit: Together AI (hosted large open-weights) — trigger = first client

**Created:** 2026-10-01
**Status:** DEFERRED — intentionally not configured yet.
**Trigger to revisit:** when OrthoFlow or Melanin Tech lands our FIRST client (i.e.
real production load / higher-capacity usage).

## Decision
`LLM_TOGETHER_AI_API_KEY` is left **commented out** in `kiro-agents/.env`. Together AI
is NOT part of the stack today — deliberately.

## Why deferred
- Hermes now runs on our **self-hosted Ollama**, routed through LLMGateway
  (`ollama-local/hermes3:8b`). Together's original purpose (a *hosted* way to serve
  Hermes) is covered locally for free, so Together would be redundant right now.
- Adding another paid provider now = extra cost + surface area with no current need.
- The migration's real gate is the gateway secrets + ONE of Mistral/Alibaba/Moonshot
  to measure a hosted frontier open-weight. Together is not on that critical path.

## When to come back (and what for)
Revisit Together AI once we have our first client AND we hit a need for a **larger
open-weight model at higher capacity** that the current CPU-only box can't serve, e.g.:
- Hermes-70B (vs the local 8B) or Qwen-72B hosted, before GPU hardware is in place.
- Burst/throughput beyond what local Ollama can handle under real client load.
- A hosted fallback for the heavy tier if local latency is too high for client SLAs.

## How to activate when the time comes
1. Get a key: api.together.ai → Settings → API Keys → Create key (add billing).
2. Uncomment + set `LLM_TOGETHER_AI_API_KEY=<key>` in `kiro-agents/.env`.
3. Register Together models in the LLMGateway UI (it's a first-class provider there).
4. Add the desired model(s) as `llmgateway` candidates in `eval/ab_candidates.yaml`
   and run `scripts/cutover_confidence.py` to measure parity BEFORE routing to them.
5. Keep the measure-before-flip + <0.90 confidence-fallback discipline.

## Architecture note (stays true regardless)
Everything routes through LLMGateway (single front door, unified cost/latency ledger).
Together, if added, is just another hosted upstream behind the gateway — no change to
how Darius/evals address models (`openai/<model>` at the gateway).
