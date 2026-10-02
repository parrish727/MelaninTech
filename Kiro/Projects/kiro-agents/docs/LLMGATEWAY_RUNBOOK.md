# LLMGateway Activation Runbook (Darius)

**Status:** staged, not activated. Default remains `DARIUS_MODEL_SOURCE=anthropic`.
**Owner:** pktech_dev · **Scope:** route Darius LLM calls through self-hosted LLMGateway.

## What this gives us
- All Darius LLM calls route through one self-hosted gateway (our keys, our infra,
  on `agent-net`), with unified cost/latency/usage analytics.
- Open-weight models (Qwen / Mistral / Hermes) serve primary; Anthropic stays as:
  1. graceful fallback when the gateway is unreachable (routing layer), and
  2. **confidence fallback** — any open-weight response the evaluator scores below
     `DARIUS_CONFIDENCE_FALLBACK` (default 0.90) is transparently re-run on Anthropic
     so customer-facing quality never drops, and
  3. the A/B eval baseline (separate internal audit; see `scripts/cutover_confidence.py`).

## Architecture (who does what)
- **LLMGateway** (`apps/gateway`, port 4001): request routing, error-based provider
  fail-over (500/404/403/timeout retry to a fallback provider), cost/latency logging.
- **Darius `provider_router.py`**: picks the tier model, points litellm at the gateway
  (`openai/<model>` + `api_base=http://llmgateway:4001/v1`), and owns the
  **confidence-based** Anthropic fallback (LLMGateway has no concept of eval score).

## One-time setup
1. Fill these in `kiro-agents/.env` (never commit real values):
   ```
   # LLMGateway core secrets
   LLMGATEWAY_AUTH_SECRET=<openssl rand -base64 32>
   LLMGATEWAY_API_KEY_HASH_SECRET=<openssl rand -base64 32>
   LLMGATEWAY_POSTGRES_PASSWORD=<strong password>
   # Darius -> gateway API key (create in the LLMGateway UI after first boot)
   LLMGATEWAY_API_KEY=<gateway api key>
   # Provider keys the gateway uses (ours)
   LLM_MISTRAL_API_KEY=<...>
   LLM_MOONSHOT_API_KEY=<...>     # Kimi
   LLM_ALIBABA_API_KEY=<...>      # Qwen
   LLM_TOGETHER_AI_API_KEY=<...>  # open-weight host (optional)
   # ANTHROPIC_API_KEY already set — reused as LLM_ANTHROPIC_API_KEY in compose
   ```
2. Deploy the gateway via the normal flow (GitHub → GHCR → Watchtower). The service
   is labeled `com.centurylinklabs.watchtower.enable=true` and pulls
   `ghcr.io/theopenco/llmgateway-unified:latest`.
3. Boot once, open the UI at `http://127.0.0.1:3002`, create an org + API key, add the
   provider keys (or rely on the `LLM_*` env vars), and copy the gateway API key into
   `LLMGATEWAY_API_KEY`.
4. Verify health: `curl -s http://127.0.0.1:4001/health` → ok.

## Activate (flip Darius to the gateway)
Set in the Darius env (compose already reads it):
```
DARIUS_MODEL_SOURCE=llmgateway
```
Restart darius-agent. Verify:
```
# A task now reports a gateway/open-weight model, not claude, unless fallback kicks in:
curl -s -X POST http://localhost:8100/task \
  -H 'Content-Type: application/json' \
  -d '{"task":"reply with the single word OK","project":"gw-smoke"}' | jq .model
```
- If the gateway is down or `LLMGATEWAY_API_KEY` is unset, `provider_router` falls
  back to Anthropic automatically (safe-by-default).

## Tune the quality gate
- `DARIUS_CONFIDENCE_FALLBACK` (default `0.90`): raise toward 0.95 to be stricter
  (more Anthropic re-runs, higher cost, higher floor); lower to trust open weights
  more. Set `0` to disable confidence fallback entirely.
- Per-tier open-weight model overrides: `DARIUS_GW_MODEL_<TIER>`
  (e.g. `DARIUS_GW_MODEL_PLAN=nousresearch/hermes-3-llama-3.1-70b`).

## Rollback
Set `DARIUS_MODEL_SOURCE=anthropic` (or unset) and restart darius-agent. Instant,
no data migration — Anthropic was never removed.

## Verify quality before trusting it (internal audit — separate track)
Run the combined eval with the gateway models serving:
```
DARIUS_MODEL_SOURCE=llmgateway python scripts/cutover_confidence.py
```
Review per-LOB free-text + System One typed-decision parity. Only widen open-weight
usage on LOBs/tasks that hold parity; the confidence fallback covers the rest live.

## Open items / tickets
- **LICENSE review (deferred):** LLMGateway core is AGPLv3; `ee/` enterprise features
  need a commercial license. Revisit before using any `ee/` feature or exposing a
  modified gateway as an external service. (Ticket: LLMGATEWAY-LICENSE.)
- Confirm exact gateway model slugs against the gateway's live model list
  before production (slugs drift).
