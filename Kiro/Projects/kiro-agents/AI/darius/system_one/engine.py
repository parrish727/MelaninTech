"""
Melanin System One engine — orchestrates typed semantic judgements.

Responsibilities:
  * validate the request (answer spaces, unique ids)
  * fan questions out to the provider IN PARALLEL (independent questions, one
    shared state — the spec's "fan out semantic questions; compose in code")
  * coerce raw provider outputs into schema-valid distributions
  * derive confidence and build typed results (ClaimResult/ChoiceResult/ScoreResult)

Also provides semantic-IF helpers implementing the Observe -> Judge -> Reason ->
Act pattern: gate deterministic actions on calibrated probability/confidence.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from AI.darius.system_one.provider import SystemOneProvider, _coerce, default_provider
from AI.darius.system_one.types import (
    Choice,
    ChoiceResult,
    Claim,
    ClaimResult,
    Question,
    Result,
    Score,
    ScoreResult,
    SystemOneRequest,
    SystemOneResponse,
    normalize,
    normalized_entropy_confidence,
)


class SystemOneEngine:
    def __init__(self, provider: SystemOneProvider | None = None, max_workers: int = 8):
        self.provider = provider or default_provider()
        self.max_workers = max_workers

    # ── single-question evaluation ────────────────────────────────────────────
    def _evaluate_one(self, state, question: Question) -> Result:
        raw = self.provider.distribution(state, question)
        dist = _coerce(raw, question)  # schema-safe, correctly sized, normalized

        if isinstance(question, Claim):
            return ClaimResult(id=question.id, kind="claim", probability=dist[0])

        if isinstance(question, Choice):
            probs = normalize(dist)
            pairs = dict(zip(question.options, probs))
            winner = max(pairs, key=pairs.get)
            conf = normalized_entropy_confidence(probs)
            return ChoiceResult(
                id=question.id, kind="choice", winner=winner,
                distribution=pairs, confidence=conf,
            )

        if isinstance(question, Score):
            probs = normalize(dist)
            legend = {lvl.value: lvl.label for lvl in question.levels}
            distribution = {lvl.value: probs[i] for i, lvl in enumerate(question.levels)}
            # Probability-weighted position (may fall between levels).
            weighted = sum(lvl.value * probs[i] for i, lvl in enumerate(question.levels))
            winner_level = max(distribution, key=distribution.get)
            conf = normalized_entropy_confidence(probs)
            return ScoreResult(
                id=question.id, kind="score", score=weighted,
                winner_level=winner_level, legend=legend,
                distribution=distribution, confidence=conf,
            )

        raise TypeError(f"Unknown question type: {type(question)}")

    # ── request evaluation (parallel fan-out) ───────────────────────────────────
    def judge(self, request: SystemOneRequest) -> SystemOneResponse:
        request.validate()
        results: dict[str, Result] = {}

        if len(request.questions) == 1:
            q = request.questions[0]
            results[q.id] = self._evaluate_one(request.state, q)
            return SystemOneResponse(results=results)

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(request.questions))) as pool:
            futures = {
                pool.submit(self._evaluate_one, request.state, q): q
                for q in request.questions
            }
            for fut in as_completed(futures):
                q = futures[fut]
                results[q.id] = fut.result()

        # Preserve request order for stable output.
        ordered = {q.id: results[q.id] for q in request.questions}
        return SystemOneResponse(results=ordered)


# ── Convenience API ───────────────────────────────────────────────────────────
_DEFAULT_ENGINE: SystemOneEngine | None = None


def get_engine(provider: SystemOneProvider | None = None) -> SystemOneEngine:
    global _DEFAULT_ENGINE
    if provider is not None:
        return SystemOneEngine(provider=provider)
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = SystemOneEngine()
    return _DEFAULT_ENGINE


def judge(state, questions: list[Question], provider: SystemOneProvider | None = None) -> SystemOneResponse:
    """One-shot: evaluate `questions` against `state`, in parallel."""
    return get_engine(provider).judge(SystemOneRequest(state=state, questions=tuple(questions)))


# ── Semantic-IF helpers (Observe -> Judge -> Reason -> Act) ───────────────────
def semantic_if(
    result: Result,
    *,
    threshold: float = 0.9,
    min_confidence: float = 0.0,
) -> bool:
    """
    A "smart if-statement": returns True only when the judgement clears the bar.

    - Claim   : True when P(true) >= threshold.
    - Choice : True when winner probability >= threshold AND confidence >= min_confidence.
    - Score  : True when the winner-level probability >= threshold AND confidence
               >= min_confidence. (For "score above level N" logic, use
               score_at_least().)
    """
    if isinstance(result, ClaimResult):
        return result.probability >= threshold
    if isinstance(result, ChoiceResult):
        top = result.distribution[result.winner]
        return top >= threshold and result.confidence >= min_confidence
    if isinstance(result, ScoreResult):
        top = result.distribution[result.winner_level]
        return top >= threshold and result.confidence >= min_confidence
    raise TypeError(f"Unsupported result type: {type(result)}")


def score_at_least(result: ScoreResult, level: int, *, mass_threshold: float = 0.5) -> bool:
    """True when the cumulative probability mass at or above `level` >= threshold.

    Useful for escalation gates like "severity is Serious (2) or worse".
    """
    mass = sum(p for lvl, p in result.distribution.items() if lvl >= level)
    return mass >= mass_threshold


class Decision:
    """Three-way routing outcome for the Observe->Judge->Reason->Act pattern."""

    ACT = "act"                    # high certainty -> deterministic action
    VERIFY = "verify"              # medium certainty -> human / verification
    REASON = "reason"             # low certainty -> escalate to a reasoning model


def route_by_confidence(
    result: Result,
    *,
    act_threshold: float = 0.9,
    verify_threshold: float = 0.6,
) -> str:
    """Map a judgement's strength to an ACT / VERIFY / REASON route.

    Strength signal:
      - Claim   : max(P(true), P(false)) — how far from the 0.5 coin-flip.
      - Choice : the winning option's probability (top-1 mass).
      - Score  : the winning level's probability (top-1 mass).

    Top-1 mass is used rather than the entropy-based `confidence` field because
    entropy is overly conservative for small answer spaces (e.g. a 0.98/0.02
    two-way split is a clear ACT, but has moderate normalized entropy). The
    entropy-based `confidence` remains on the result for callers who want the
    distribution-concentration view.
    """
    if isinstance(result, ClaimResult):
        strength = max(result.probability, 1.0 - result.probability)
    elif isinstance(result, ChoiceResult):
        strength = result.distribution[result.winner]
    elif isinstance(result, ScoreResult):
        strength = result.distribution[result.winner_level]
    else:
        raise TypeError(f"Unsupported result type: {type(result)}")

    if strength >= act_threshold:
        return Decision.ACT
    if strength >= verify_threshold:
        return Decision.VERIFY
    return Decision.REASON
