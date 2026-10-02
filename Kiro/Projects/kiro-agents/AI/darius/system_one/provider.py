"""
Melanin System One providers — the adapter seam.

A SystemOneProvider turns (state, question) into a raw probability distribution over
that question's answer space. The engine (engine.py) wraps providers with
validation, parallel fan-out, confidence derivation and typed results.

Providers here:
  MockProvider      — deterministic, offline. Keyword-heuristic distributions for
                      tests and for running without an API key.
  AnthropicProvider — elicits calibrated probabilities from Claude via constrained
                      JSON. Output is ALWAYS coerced into the declared answer space,
                      so schema hallucination is impossible by construction.

When TypeSafe releases the official Jev client, add a TypeSafeProvider here that
implements the same SystemOneProvider protocol and select it in engine.py — no
call-site changes required anywhere else.
"""
from __future__ import annotations

import json
import os
import re
from typing import Protocol

from AI.darius.system_one.types import (
    Choice,
    Claim,
    Question,
    Score,
    normalize,
)


class SystemOneProvider(Protocol):
    """Return a probability list aligned to the question's answer space.

    - Claim  -> [P(true)]                 (length 1)
    - Choice-> [P(opt) for opt in options] (length == len(options))
    - Score -> [P(level) for level in levels] (length == len(levels))
    """

    def distribution(self, state, question: Question) -> list[float]: ...


def _answer_space_len(question: Question) -> int:
    if isinstance(question, Claim):
        return 1
    if isinstance(question, Choice):
        return len(question.options)
    if isinstance(question, Score):
        return len(question.levels)
    raise TypeError(f"Unknown question type: {type(question)}")


def _coerce(raw: list[float], question: Question) -> list[float]:
    """Force a raw provider output into the exact shape of the answer space.

    This is the schema-safety guarantee: no matter what the provider returns,
    the engine only ever sees a correctly-sized, normalized distribution over
    the declared answer space.
    """
    expected = _answer_space_len(question)
    vals = list(raw)[:expected]
    if len(vals) < expected:
        vals += [0.0] * (expected - len(vals))
    if isinstance(question, Claim):
        # Single probability; clamp to [0,1], no renormalization.
        p = vals[0]
        return [max(0.0, min(1.0, p))]
    return normalize(vals)


def _state_to_text(state) -> str:
    if isinstance(state, str):
        return state
    try:
        return json.dumps(state, indent=2, default=str)
    except Exception:
        return str(state)


# ── Mock provider ─────────────────────────────────────────────────────────────
class MockProvider:
    """
    Deterministic, offline provider for tests and no-API-key runs.

    Heuristic: counts how many of the question's own salient tokens appear in the
    state text, producing a stable, inspectable distribution. Not accurate — its
    purpose is to exercise the engine deterministically.
    """

    def distribution(self, state, question: Question) -> list[float]:
        text = _state_to_text(state).lower()

        if isinstance(question, Claim):
            # Presence of question keywords in state nudges P(true) up.
            kws = _salient_tokens(question.question)
            hits = sum(1 for k in kws if k in text)
            p = 0.5 + 0.4 * (hits / max(1, len(kws))) if kws else 0.5
            return [min(0.98, max(0.02, p))]

        if isinstance(question, Choice):
            weights = []
            for opt in question.options:
                toks = _salient_tokens(opt)
                score = sum(text.count(t) for t in toks) if toks else 0
                # Option label literally present in state is a strong signal.
                if opt.lower() in text:
                    score += 3
                weights.append(float(score) + 0.1)  # +0.1 smoothing
            return weights

        if isinstance(question, Score):
            weights = []
            for lvl in question.levels:
                toks = _salient_tokens(lvl.label)
                score = sum(text.count(t) for t in toks) if toks else 0
                weights.append(float(score) + 0.1)
            return weights

        raise TypeError(f"Unknown question type: {type(question)}")


_STOPWORDS = frozenset(
    ["the", "a", "an", "is", "are", "does", "do", "this", "that", "these", "those", "of", "to", "in", "on", "for", "and", "or", "not", "with", "it", "its", "as", "at", "be", "by", "from", "has", "have", "was", "were", "which", "who", "whom", "what", "when", "where", "why", "how", "no", "yes", "any", "some", "all", "more", "most", "level", "impact", "material", "required"]
)


def _salient_tokens(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in toks if t not in _STOPWORDS and len(t) > 2]


# ── Anthropic provider ────────────────────────────────────────────────────────
_ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# System One judgements are fast/light — use the light tier by default.
_SYSTEM_ONE_MODEL = os.environ.get("SYSTEM_ONE_MODEL", "anthropic/claude-haiku-4-5-20251001")


class LiteLLMProvider:
    """
    Model-parameterized System One provider. Backs a typed judgement with ANY
    litellm-addressable model (Anthropic, Ollama-local, self-hosted LLMGateway, ...), so the
    same A/B candidate that answers free-text tasks can also serve typed
    decisions. This is what lets the migration measure open-weight models on
    typed-decision parity.

    Elicits a calibrated probability distribution constrained to the declared
    answer space via strict JSON. The engine coerces + normalizes afterwards, so
    the result is always schema-valid regardless of the model's raw response.

    Args:
        model:    full litellm model id, e.g. "anthropic/claude-haiku-4-5-20251001",
                  "ollama/qwen3:14b", "openai/qwen/qwen-2.5-72b-instruct" (via gateway).
        api_key:  provider key (Anthropic / LLMGateway). Not needed for Ollama.
        api_base: base URL (used for Ollama, e.g. http://ollama:11434).
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        timeout: int = 30,
    ):
        self.model = model or _SYSTEM_ONE_MODEL
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = timeout

    @classmethod
    def from_candidate(cls, provider: str, model: str, timeout: int = 30) -> LiteLLMProvider:
        """Build from an A/B roster entry (matches scripts/ab_eval.py conventions)."""
        if provider == "anthropic":
            return cls(model=f"anthropic/{model}",
                       api_key=os.environ.get("ANTHROPIC_API_KEY", ""), timeout=timeout)
        if provider == "llmgateway":
            # Self-hosted OpenAI-compatible gateway: openai/<model> + api_base.
            return cls(model=f"openai/{model}",
                       api_key=os.environ.get("LLMGATEWAY_API_KEY", ""),
                       api_base=os.environ.get("LLMGATEWAY_URL", "http://llmgateway:4001/v1"),
                       timeout=timeout)
        if provider == "ollama":
            return cls(model=f"ollama/{model}",
                       api_base=os.environ.get("OLLAMA_URL", "http://ollama:11434"),
                       timeout=timeout)
        raise ValueError(f"unknown provider '{provider}'")

    def distribution(self, state, question: Question) -> list[float]:
        from litellm import completion

        kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": self._build_prompt(state, question)},
            ],
            "max_tokens": 400,
            "temperature": 0.0,
            "timeout": self.timeout,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        resp = completion(**kwargs)
        raw = (resp.choices[0].message.content or "").strip()
        return self._parse(raw, question)

    def _build_prompt(self, state, question: Question) -> str:
        state_text = _state_to_text(state)
        if isinstance(question, Claim):
            schema = '{"probability_true": <float 0..1>}'
            space = "a single probability that the proposition is TRUE"
        elif isinstance(question, Choice):
            opts = "\n".join(f'  - "{o}"' for o in question.options)
            schema = '{"probabilities": {"<option>": <float>, ...}}  (one key per option, summing to ~1)'
            space = f"a probability for EACH of these options (and only these):\n{opts}"
        elif isinstance(question, Score):
            legend = "\n".join(f"  {lvl.value} = {lvl.label}" for lvl in question.levels)
            schema = '{"probabilities": {"<level_index>": <float>, ...}}  (one key per level index, summing to ~1)'
            space = f"a probability for EACH ordered level (and only these):\n{legend}"
        else:
            raise TypeError(f"Unknown question type: {type(question)}")

        return (
            f"STATE:\n{state_text}\n\n"
            f"QUESTION: {question.question}\n\n"
            f"Return {space}.\n"
            f"Output ONLY strict JSON matching: {schema}\n"
            f"No prose, no explanation, no markdown fences."
        )

    def _parse(self, raw: str, question: Question) -> list[float]:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            data = json.loads(raw)
        except Exception:
            # Last-resort: pull the first JSON object out of the text.
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(m.group(0)) if m else {}

        if isinstance(question, Claim):
            return [float(data.get("probability_true", 0.5))]

        probs = data.get("probabilities", {}) if isinstance(data, dict) else {}
        if isinstance(question, Choice):
            return [float(probs.get(opt, 0.0)) for opt in question.options]
        if isinstance(question, Score):
            return [float(probs.get(str(lvl.value), probs.get(lvl.value, 0.0)))
                    for lvl in question.levels]
        raise TypeError(f"Unknown question type: {type(question)}")


_SYSTEM = (
    "You are a System One semantic-judgement engine. You do not generate prose, "
    "plans, or explanations. Given STATE and one QUESTION with a fixed answer "
    "space, you return a calibrated probability distribution over that answer "
    "space as strict JSON. Probabilities should reflect genuine uncertainty: "
    "concentrate mass when the state strongly supports one answer, spread it when "
    "the state is ambiguous. Never invent options outside the provided answer space."
)


class AnthropicProvider(LiteLLMProvider):
    """Backward-compatible Claude-backed provider (a LiteLLMProvider preset)."""

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout: int = 30):
        super().__init__(
            model=model or _SYSTEM_ONE_MODEL,
            api_key=api_key or _ANTHROPIC_KEY,
            timeout=timeout,
        )


def default_provider() -> SystemOneProvider:
    """Anthropic if a key is configured, else the deterministic mock."""
    if _ANTHROPIC_KEY:
        return AnthropicProvider()
    return MockProvider()
