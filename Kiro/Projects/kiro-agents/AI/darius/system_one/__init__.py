"""
Melanin System One ("Verdict") — a local typed semantic-decision engine.

This is OUR implementation of the "System One" pattern popularized by TypeSafe
AI's Jev model: state + typed questions in, typed probabilistic decisions out.
It is NOT TypeSafe Jev and does not use TypeSafe's code or service. It implements
the same *contract* so that when TypeSafe releases their official client we can
add a TypeSafeProvider (system_one/provider.py) and swap it in with zero
call-site changes.

Primitives (our names): Claim (yes/no probability), Choice (one-of-N +
distribution + confidence), Score (ordered levels + distribution + confidence).

Public API:
    from AI.darius.system_one import judge, Claim, Choice, Score, semantic_if

    resp = judge(state, [
        Claim("safeguarding", "Does the incident indicate an immediate safeguarding risk?"),
        Choice("team", "Which team should handle this?", ("Safeguarding", "Housing", "IT", "Other")),
        Score.from_labels("severity", "How severe is this incident?", [
            "Minor; no material impact",
            "Moderate; intervention required",
            "Serious; significant harm possible",
            "Critical; immediate action required",
        ]),
    ])
    if semantic_if(resp["safeguarding"], threshold=0.95):
        escalate()
"""
from AI.darius.system_one.engine import (
    Decision,
    SystemOneEngine,
    get_engine,
    judge,
    route_by_confidence,
    score_at_least,
    semantic_if,
)
from AI.darius.system_one.provider import (
    AnthropicProvider,
    LiteLLMProvider,
    MockProvider,
    SystemOneProvider,
    default_provider,
)
from AI.darius.system_one.types import (
    Choice,
    ChoiceResult,
    Claim,
    ClaimResult,
    Question,
    Result,
    Score,
    ScoreLevel,
    ScoreResult,
    SystemOneRequest,
    SystemOneResponse,
    SystemOneValidationError,
)

__all__ = [
    "AnthropicProvider",
    "Choice",
    "ChoiceResult",
    # primitives
    "Claim",
    # results
    "ClaimResult",
    "Decision",
    "LiteLLMProvider",
    "MockProvider",
    "Question",
    "Result",
    "Score",
    "ScoreLevel",
    "ScoreResult",
    # engine + api
    "SystemOneEngine",
    # providers
    "SystemOneProvider",
    # request/response
    "SystemOneRequest",
    "SystemOneResponse",
    "SystemOneValidationError",
    "default_provider",
    "get_engine",
    "judge",
    "route_by_confidence",
    "score_at_least",
    "semantic_if",
]
