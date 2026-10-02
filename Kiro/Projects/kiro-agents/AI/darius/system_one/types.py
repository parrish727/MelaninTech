"""
Melanin System One types — OUR typed semantic-decision contract.

This implements the "System One" pattern (as popularized by TypeSafe AI Jev).
It is NOT Jev; it reproduces the same *contract* — state + typed questions in,
typed probabilistic decisions out — so application code can be written against
the contract now and swap to a real TypeSafe client later with zero call-site
changes (see system_one/provider.py for the adapter seam).

Primitives (mirrors the TypeSafe spec):
  Claim   — probability that a yes/no proposition is true (no separate confidence:
           the probability IS the yes/no uncertainty).
  Choice — one option from a predefined set (<=255). Returns the winner, a full
           probability distribution over options, and a derived confidence.
  Score  — position on an ordered set of 2..10 descriptive levels. Returns a
           probability-weighted position, the per-level distribution, the legend,
           and a derived confidence.

Key guarantees this shim preserves:
  * Schema safety: results are ALWAYS a valid member of the declared answer
    space. The engine never emits free text or an out-of-space value, so the
    "type-safe / schema hallucination" class of failure is eliminated by design.
    (Semantic judgement errors remain possible — calibration != correctness.)
  * Probability + confidence are first-class outputs.
  * Independent questions are evaluated in parallel and composed in code.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

# ── Answer-space limits (from the TypeSafe spec) ──────────────────────────────
CHOICE_MAX_OPTIONS = 255
SCORE_MIN_LEVELS = 2
SCORE_MAX_LEVELS = 10

PrimitiveKind = Literal["claim", "choice", "score"]


class SystemOneValidationError(ValueError):
    """Raised when a question's answer space is invalid."""


# ── Question primitives ───────────────────────────────────────────────────────
@dataclass(frozen=True)
class Claim:
    """A yes/no semantic proposition. Answer space is implicitly {true, false}."""

    id: str
    question: str
    kind: PrimitiveKind = field(default="claim", init=False)

    def validate(self) -> None:
        if not self.id:
            raise SystemOneValidationError("Claim requires a non-empty id")
        if not self.question.strip():
            raise SystemOneValidationError(f"Claim '{self.id}' requires a non-empty question")


@dataclass(frozen=True)
class Choice:
    """Select exactly one option from a predefined set."""

    id: str
    question: str
    options: tuple[str, ...]
    kind: PrimitiveKind = field(default="choice", init=False)

    def validate(self) -> None:
        if not self.id:
            raise SystemOneValidationError("Choice requires a non-empty id")
        if not self.question.strip():
            raise SystemOneValidationError(f"Choice '{self.id}' requires a non-empty question")
        if len(self.options) < 2:
            raise SystemOneValidationError(
                f"Choice '{self.id}' needs at least 2 options, got {len(self.options)}"
            )
        if len(self.options) > CHOICE_MAX_OPTIONS:
            raise SystemOneValidationError(
                f"Choice '{self.id}' exceeds {CHOICE_MAX_OPTIONS} options ({len(self.options)})"
            )
        if len(set(self.options)) != len(self.options):
            raise SystemOneValidationError(f"Choice '{self.id}' has duplicate options")


@dataclass(frozen=True)
class ScoreLevel:
    """One level on a Score scale. `value` is the ordinal position (0-based)."""

    value: int
    label: str


@dataclass(frozen=True)
class Score:
    """Position something on an ordered set of 2..10 concrete descriptive levels."""

    id: str
    question: str
    levels: tuple[ScoreLevel, ...]
    kind: PrimitiveKind = field(default="score", init=False)

    def validate(self) -> None:
        if not self.id:
            raise SystemOneValidationError("Score requires a non-empty id")
        if not self.question.strip():
            raise SystemOneValidationError(f"Score '{self.id}' requires a non-empty question")
        n = len(self.levels)
        if n < SCORE_MIN_LEVELS or n > SCORE_MAX_LEVELS:
            raise SystemOneValidationError(
                f"Score '{self.id}' needs {SCORE_MIN_LEVELS}..{SCORE_MAX_LEVELS} levels, got {n}"
            )
        values = [lvl.value for lvl in self.levels]
        if values != list(range(n)):
            raise SystemOneValidationError(
                f"Score '{self.id}' levels must have contiguous 0-based values 0..{n - 1}"
            )

    @staticmethod
    def from_labels(id: str, question: str, labels: list[str]) -> Score:
        """Convenience: build a Score from ordered labels (auto-assigns values)."""
        levels = tuple(ScoreLevel(i, lbl) for i, lbl in enumerate(labels))
        return Score(id=id, question=question, levels=levels)


Question = Claim | Choice | Score


# ── Request ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class SystemOneRequest:
    """
    A single System One request: one shared `state` + one or more independent questions.

    All questions are evaluated against the SAME state and are independent of one
    another (the answer to one never becomes hidden context for another). Genuine
    dependencies should be expressed as separate, sequential requests.
    """

    state: Any  # str | dict | list | application record
    questions: tuple[Question, ...]

    def validate(self) -> None:
        if not self.questions:
            raise SystemOneValidationError("SystemOneRequest requires at least one question")
        ids = [q.id for q in self.questions]
        if len(set(ids)) != len(ids):
            raise SystemOneValidationError(f"Duplicate question ids in request: {ids}")
        for q in self.questions:
            q.validate()


# ── Results ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ClaimResult:
    id: str
    kind: PrimitiveKind
    probability: float  # P(true), in [0, 1]

    @property
    def value(self) -> bool:
        return self.probability >= 0.5

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind,
            "probability": round(self.probability, 4),
            "value": self.value,
        }


@dataclass(frozen=True)
class ChoiceResult:
    id: str
    kind: PrimitiveKind
    winner: str
    distribution: dict[str, float]  # option -> probability, sums to ~1
    confidence: float               # derived concentration measure, [0, 1]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "winner": self.winner,
            "distribution": {k: round(v, 4) for k, v in self.distribution.items()},
            "confidence": round(self.confidence, 4),
        }


@dataclass(frozen=True)
class ScoreResult:
    id: str
    kind: PrimitiveKind
    score: float                    # probability-weighted position (may be between levels)
    winner_level: int               # argmax level index
    legend: dict[int, str]          # level index -> label
    distribution: dict[int, float]  # level index -> probability
    confidence: float               # derived concentration measure, [0, 1]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind,
            "score": round(self.score, 4),
            "winner_level": self.winner_level,
            "legend": {str(k): v for k, v in self.legend.items()},
            "distribution": {str(k): round(v, 4) for k, v in self.distribution.items()},
            "confidence": round(self.confidence, 4),
        }


Result = ClaimResult | ChoiceResult | ScoreResult


@dataclass(frozen=True)
class SystemOneResponse:
    """Keyed by question id so callers compose answers in code."""

    results: dict[str, Result]

    def __getitem__(self, qid: str) -> Result:
        return self.results[qid]

    def get(self, qid: str, default=None):
        return self.results.get(qid, default)

    def to_dict(self) -> dict:
        return {"results": {qid: r.to_dict() for qid, r in self.results.items()}}


# ── Confidence derivation ─────────────────────────────────────────────────────
def normalized_entropy_confidence(probs: list[float]) -> float:
    """
    Derive a confidence in [0, 1] from a probability distribution.

    A concentrated distribution (one option dominates) -> high confidence.
    A flat/uniform distribution -> low confidence.

    Implemented as 1 - normalized Shannon entropy, so it is comparable across
    distributions with different numbers of options. For n<=1 returns 1.0.
    """
    n = len(probs)
    if n <= 1:
        return 1.0
    total = sum(probs)
    if total <= 0:
        return 0.0
    p = [x / total for x in probs]
    entropy = -sum(x * math.log(x) for x in p if x > 0)
    max_entropy = math.log(n)
    if max_entropy <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (entropy / max_entropy)))


def normalize(probs: list[float]) -> list[float]:
    """Clamp to non-negative and renormalize to sum 1. Uniform if all zero."""
    clamped = [max(0.0, x) for x in probs]
    total = sum(clamped)
    if total <= 0:
        n = len(clamped)
        return [1.0 / n] * n if n else []
    return [x / total for x in clamped]
