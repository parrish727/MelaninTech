"""
Darius Provider Router — one place that decides which model serves each call.

Design goals (per Melanin Tech migration plan):
  * Anthropic stays FULLY in place — it is the default AND the fallback. Darius
    keeps learning from Anthropic traces; nothing here removes that.
  * LLMGateway is the open-weight *switch*: set DARIUS_MODEL_SOURCE=llmgateway to
    route the open-weight models (Qwen / Mistral / Kimi / Hermes) through our
    SELF-HOSTED, open-source LLMGateway (our own provider keys) while A/B
    evaluating. Set =local for on-box Ollama. Set =anthropic (default) for
    today's behavior. OpenRouter (closed SaaS) is intentionally NOT a source —
    the open-weight path stays fully open-source/self-hosted.
  * Graceful fallback: if the selected source is misconfigured (missing key,
    unreachable Ollama), the router silently falls back to Anthropic so Darius
    never hard-breaks mid-task.

Every subsystem (planner, evaluator, context, swarm) calls `resolve(tier)` and
feeds the result straight into `litellm.completion(**kwargs_for_completion())`.

Logical tiers (map to the existing DARIUS_MODEL_* env vars so behavior is
unchanged when source=anthropic):
    apex     — architecture / hardest reasoning
    heavy    — heavy coding / multi-step
    default  — standard agent tasks
    light    — planning / classification / compression (fast, cheap)
    plan     — task decomposition
    eval     — output scoring
    compress — context compression

Usage:
    from AI.darius.provider_router import resolve

    r = resolve("plan")
    resp = completion(**r.completion_kwargs(),
                      messages=[...], max_tokens=2048, temperature=0.1)
    # r.label / r.provider / r.model  -> for trace + cost logging
"""
from __future__ import annotations

import os
from dataclasses import dataclass


# ── Source selection ──────────────────────────────────────────────────────────
# anthropic (default) | llmgateway | local
#   OpenRouter is intentionally NOT a source: the open-weight path is our
#   self-hosted LLMGateway (open-source), using our own provider keys.
def _source() -> str:
    return os.environ.get("DARIUS_MODEL_SOURCE", "anthropic").strip().lower()


_ANTHROPIC_KEY = lambda: os.environ.get("ANTHROPIC_API_KEY", "")
_OLLAMA_URL = lambda: os.environ.get("OLLAMA_URL", "http://ollama:11434")
# LLMGateway: self-hosted open-source gateway (OpenAI-compatible). The single
# open-weight path (Qwen/Mistral/Kimi/Hermes) via our own provider keys.
_LLMGATEWAY_URL = lambda: os.environ.get("LLMGATEWAY_URL", "http://llmgateway:4001/v1")
_LLMGATEWAY_KEY = lambda: os.environ.get("LLMGATEWAY_API_KEY", "")


# ── Anthropic tier defaults (mirror the per-subsystem env vars already in use) ─
# These are read lazily so tests / runtime env changes take effect.
def _anthropic_model(tier: str) -> str:
    table = {
        "apex": os.environ.get("DARIUS_MODEL_APEX", "anthropic/claude-opus-4-6"),
        "heavy": os.environ.get("DARIUS_MODEL_HEAVY", "anthropic/claude-sonnet-5"),
        "default": os.environ.get("DARIUS_MODEL", "anthropic/claude-sonnet-4-6"),
        "light": os.environ.get("DARIUS_MODEL_LIGHT", "anthropic/claude-haiku-4-5-20251001"),
        "plan": os.environ.get("DARIUS_MODEL_PLAN", "anthropic/claude-sonnet-4-6"),
        "eval": os.environ.get("DARIUS_MODEL_EVAL", "anthropic/claude-sonnet-4-6"),
        "compress": os.environ.get("DARIUS_MODEL_COMPRESS", "anthropic/claude-haiku-4-5-20251001"),
    }
    return table.get(tier, table["default"])


# ── LLMGateway tier map (OpenAI-compatible model ids served by the gateway) ────
# Self-hosted open-source gateway resolves these open-weight slugs to OUR OWN
# provider keys (Mistral, Alibaba/Qwen, Moonshot/Kimi, Hermes). This is the ONLY
# open-weight path — no closed SaaS routers in the stack. Overridable per tier
# via DARIUS_GW_MODEL_<TIER>.
_LLMGATEWAY_DEFAULTS = {
    "apex": "qwen/qwen-2.5-72b-instruct",
    "heavy": "qwen/qwen-2.5-72b-instruct",
    "default": "mistralai/mistral-large",
    "light": "mistralai/mistral-small",
    "plan": "qwen/qwen-2.5-72b-instruct",
    "eval": "mistralai/mistral-small",
    "compress": "mistralai/mistral-small",
}


def _llmgateway_model(tier: str) -> str:
    env = os.environ.get(f"DARIUS_GW_MODEL_{tier.upper()}")
    if env:
        return env
    return _LLMGATEWAY_DEFAULTS.get(tier, _LLMGATEWAY_DEFAULTS["default"])


# ── Local (Ollama) tier map ────────────────────────────────────────────────────
def _local_model(tier: str) -> str:
    heavy = os.environ.get("DARIUS_LOCAL_HEAVY", "mistral-small:24b")
    light = os.environ.get("DARIUS_LOCAL_LIGHT", "qwen3:14b")
    return heavy if tier in ("apex", "heavy", "default", "plan") else light


_HEAVY_TIERS = frozenset({"apex", "heavy", "default", "plan"})


@dataclass(frozen=True)
class Resolved:
    """The concrete model choice for one call, ready for litellm.completion."""

    provider: str          # "anthropic" | "llmgateway" | "local"
    model: str             # full litellm model id
    tier: str
    api_key: str | None
    api_base: str | None
    fell_back: bool        # True if we wanted another source but fell back
    requested_source: str  # what was asked for before fallback

    @property
    def label(self) -> str:
        """Compact provider/model label for traces + cost tracking."""
        short = self.model.split("/")[-1]
        return f"{self.provider}:{short}"

    def completion_kwargs(self) -> dict:
        """kwargs to splat into litellm.completion (model/api_key/api_base)."""
        kw: dict = {"model": self.model}
        if self.api_key:
            kw["api_key"] = self.api_key
        if self.api_base:
            kw["api_base"] = self.api_base
        return kw

    def supports_prompt_cache(self) -> bool:
        """Anthropic cache_control blocks are only valid on the Anthropic path."""
        return self.provider == "anthropic"


def _ollama_reachable() -> bool:
    import httpx
    try:
        return httpx.get(f"{_OLLAMA_URL()}/api/tags", timeout=3).status_code == 200
    except Exception:
        return False


def _llmgateway_reachable() -> bool:
    import httpx
    # Health endpoint sits at the gateway root (strip the /v1 suffix if present).
    base = _LLMGATEWAY_URL().rstrip("/")
    base = base.removesuffix("/v1")
    try:
        return httpx.get(f"{base}/health", timeout=3).status_code == 200
    except Exception:
        return False


def _anthropic_resolved(tier: str, requested: str, fell_back: bool) -> Resolved:
    return Resolved(
        provider="anthropic",
        model=_anthropic_model(tier),
        tier=tier,
        api_key=_ANTHROPIC_KEY() or None,
        api_base=None,
        fell_back=fell_back,
        requested_source=requested,
    )


def resolve(tier: str = "default") -> Resolved:
    """
    Resolve a logical tier to a concrete model for the current source.

    Never raises: if the requested source is unavailable it falls back to
    Anthropic (keeping Darius running). Anthropic is also the default source.
    """
    src = _source()

    if src == "llmgateway":
        if _LLMGATEWAY_KEY() and _llmgateway_reachable():
            return Resolved(
                provider="llmgateway",
                # litellm talks to any OpenAI-compatible endpoint via openai/<model>
                model=f"openai/{_llmgateway_model(tier)}",
                tier=tier,
                api_key=_LLMGATEWAY_KEY(),
                api_base=_LLMGATEWAY_URL(),
                fell_back=False,
                requested_source="llmgateway",
            )
        # Gateway down or unconfigured -> keep Anthropic in place.
        return _anthropic_resolved(tier, requested="llmgateway", fell_back=True)

    if src == "local":
        if _ollama_reachable():
            return Resolved(
                provider="local",
                model=f"ollama/{_local_model(tier)}",
                tier=tier,
                api_key="ollama",  # litellm requires a non-empty key
                api_base=_OLLAMA_URL(),
                fell_back=False,
                requested_source="local",
            )
        return _anthropic_resolved(tier, requested="local", fell_back=True)

    # Default / explicit anthropic.
    return _anthropic_resolved(tier, requested="anthropic", fell_back=False)


def active_source() -> str:
    """The currently configured source (before any per-call fallback)."""
    return _source()


def confidence_fallback_threshold() -> float:
    """Open-weight responses scoring below this re-run on Anthropic. 0 disables."""
    try:
        return float(os.environ.get("DARIUS_CONFIDENCE_FALLBACK", "0.90"))
    except ValueError:
        return 0.90


def should_confidence_fallback(provider: str, score: float | None) -> bool:
    """
    Decide whether to re-run on Anthropic for quality.

    Only applies when:
      - the response came from a NON-Anthropic provider (open weight / gateway), and
      - we have an evaluator score, and
      - that score is below the configured confidence threshold.

    Anthropic is never downgraded to itself, so Anthropic responses never trigger this.
    """
    if provider == "anthropic":
        return False
    threshold = confidence_fallback_threshold()
    if threshold <= 0 or score is None:
        return False
    return score < threshold
