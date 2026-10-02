"""
Melanin System One service — JSON-in / JSON-out facade over the engine.

Shared by the Darius smolagents tool and the HUD API endpoint so both speak the
same wire format. Also usable directly from deterministic Python.

Wire format (request):
{
  "state": <str | object | array>,
  "questions": [
    {"id": "refund",  "type": "claim",   "question": "Does this request a refund?"},
    {"id": "team",    "type": "choice", "question": "Which team?",
     "options": ["Billing", "Technical", "Account", "Other"]},
    {"id": "severity","type": "score",  "question": "How severe?",
     "levels": ["No impact", "Degraded", "Unavailable"]}
  ]
}

Wire format (response): SystemOneResponse.to_dict()
{
  "results": {
    "refund":   {"kind": "claim",   "probability": 0.96, "value": true},
    "team":     {"kind": "choice", "winner": "Billing", "distribution": {...}, "confidence": 0.71},
    "severity": {"kind": "score",  "score": 1.3, "winner_level": 1, "legend": {...},
                 "distribution": {...}, "confidence": 0.55}
  }
}
"""
from __future__ import annotations

from typing import Any

from AI.darius.system_one.engine import judge as _judge
from AI.darius.system_one.provider import MockProvider, SystemOneProvider
from AI.darius.system_one.types import (
    Choice,
    Claim,
    Question,
    Score,
    SystemOneValidationError,
)


def parse_question(spec: dict) -> Question:
    """Turn one question spec dict into a typed primitive."""
    if not isinstance(spec, dict):
        raise SystemOneValidationError(f"Question spec must be an object, got {type(spec)}")
    qid = spec.get("id")
    qtype = (spec.get("type") or "").lower()
    text = spec.get("question", "")
    if not qid:
        raise SystemOneValidationError("Each question needs an 'id'")

    if qtype == "claim":
        return Claim(id=qid, question=text)
    if qtype == "choice":
        options = spec.get("options")
        if not isinstance(options, list) or not options:
            raise SystemOneValidationError(f"Choice '{qid}' needs a non-empty 'options' list")
        return Choice(id=qid, question=text, options=tuple(str(o) for o in options))
    if qtype == "score":
        levels = spec.get("levels")
        if not isinstance(levels, list) or not levels:
            raise SystemOneValidationError(f"Score '{qid}' needs a non-empty 'levels' list")
        return Score.from_labels(qid, text, [str(lvl) for lvl in levels])
    raise SystemOneValidationError(f"Question '{qid}' has unknown type '{qtype}' (claim|choice|score)")


def parse_request(payload: dict) -> tuple[Any, list[Question]]:
    if not isinstance(payload, dict):
        raise SystemOneValidationError("Request must be a JSON object")
    if "questions" not in payload:
        raise SystemOneValidationError("Request needs a 'questions' array")
    state = payload.get("state", "")
    questions = [parse_question(q) for q in payload["questions"]]
    return state, questions


def run_system_one(payload: dict, provider: SystemOneProvider | None = None) -> dict:
    """
    Execute a System One request from the JSON wire format and return a JSON-safe dict.

    `provider` overrides the default (Anthropic if key present, else mock). Pass
    MockProvider() for deterministic offline runs.
    """
    state, questions = parse_request(payload)
    response = _judge(state, questions, provider=provider)
    return response.to_dict()


# ── smolagents Tool ───────────────────────────────────────────────────────────
try:
    from smolagents import Tool

    class SystemOneTool(Tool):
        name = "system_one_judge"
        description = (
            "Make fast, typed semantic judgements over some state — the System One "
            "'smart if-statement'. Given state plus one or more typed questions "
            "(claim=yes/no probability, choice=one-of-N with distribution+confidence, "
            "score=ordered levels with distribution+confidence), returns structured "
            "decisions software can consume directly. Use for classify/detect/score/"
            "route/verify/rank — NOT for writing prose, planning, or multi-step reasoning. "
            "Independent questions are evaluated in parallel; compose answers in code."
        )
        inputs = {
            "state": {
                "type": "object",
                "description": "The material to judge: an object, or a string wrapped as {\"text\": \"...\"}.",
            },
            "questions": {
                "type": "object",
                "description": (
                    "List of question specs. Each: {id, type: claim|choice|score, question, "
                    "and for choice: options[], for score: levels[] (ordered, concrete)}. "
                    "Pass as {\"items\": [ ... ]}."
                ),
            },
        }
        output_type = "string"

        def forward(self, state, questions) -> str:
            import json

            # Accept both {"items":[...]} and a bare list for robustness.
            if isinstance(questions, dict) and "items" in questions:
                q_list = questions["items"]
            elif isinstance(questions, list):
                q_list = questions
            else:
                q_list = [questions]

            # Unwrap {"text": "..."} state convenience form.
            if isinstance(state, dict) and set(state.keys()) == {"text"}:
                state = state["text"]

            try:
                result = run_system_one({"state": state, "questions": q_list})
                return json.dumps(result, indent=2)
            except SystemOneValidationError as e:
                return json.dumps({"error": f"validation: {e}"})
            except Exception as e:  # provider/runtime failure
                return json.dumps({"error": f"system_one error: {e}"})

except ImportError:  # smolagents not installed in this environment
    SystemOneTool = None  # type: ignore
