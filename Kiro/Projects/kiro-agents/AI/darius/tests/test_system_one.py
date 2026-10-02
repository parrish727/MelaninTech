"""
Tests for the local Jev (System One) engine.

Fully offline: uses MockProvider and a deterministic custom provider. No network,
no litellm, no smolagents required.

Run with: python -m pytest AI/darius/tests/test_jev.py -v
Or standalone: python AI/darius/tests/test_jev.py
"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from AI.darius.system_one import (  # noqa: E402
    Choice,
    Decision,
    SystemOneValidationError,
    MockProvider,
    Claim,
    Score,
    ScoreLevel,
    get_engine,
    judge,
    route_by_confidence,
    score_at_least,
    semantic_if,
)
from AI.darius.system_one.engine import SystemOneEngine  # noqa: E402
from AI.darius.system_one.provider import _coerce  # noqa: E402
from AI.darius.system_one.service import parse_question, run_system_one  # noqa: E402
from AI.darius.system_one.types import (  # noqa: E402
    SystemOneRequest,
    normalize,
    normalized_entropy_confidence,
)


class ScriptedProvider:
    """Returns caller-supplied distributions keyed by question id."""

    def __init__(self, table):
        self.table = table

    def distribution(self, state, question):
        return self.table[question.id]


# ── Type system + validation ──────────────────────────────────────────────────
class TestTypeSystem(unittest.TestCase):
    def test_noul_kind_and_validate(self):
        n = Claim("q", "Is it true?")
        self.assertEqual(n.kind, "claim")
        n.validate()  # no raise

    def test_noul_empty_question_rejected(self):
        with self.assertRaises(SystemOneValidationError):
            Claim("q", "   ").validate()

    def test_choice_requires_two_options(self):
        with self.assertRaises(SystemOneValidationError):
            Choice("q", "Which?", ("only",)).validate()

    def test_choice_rejects_duplicates(self):
        with self.assertRaises(SystemOneValidationError):
            Choice("q", "Which?", ("a", "a")).validate()

    def test_choice_max_options(self):
        opts = tuple(f"opt{i}" for i in range(256))
        with self.assertRaises(SystemOneValidationError):
            Choice("q", "Which?", opts).validate()

    def test_score_level_bounds(self):
        with self.assertRaises(SystemOneValidationError):
            Score("q", "How?", (ScoreLevel(0, "only"),)).validate()  # 1 level < min 2
        too_many = tuple(ScoreLevel(i, str(i)) for i in range(11))
        with self.assertRaises(SystemOneValidationError):
            Score("q", "How?", too_many).validate()  # 11 > max 10

    def test_score_from_labels_contiguous(self):
        s = Score.from_labels("sev", "How severe?", ["a", "b", "c"])
        s.validate()
        self.assertEqual([lvl.value for lvl in s.levels], [0, 1, 2])

    def test_request_rejects_duplicate_ids(self):
        req = SystemOneRequest("state", (Claim("dup", "x?"), Claim("dup", "y?")))
        with self.assertRaises(SystemOneValidationError):
            req.validate()

    def test_request_rejects_empty(self):
        with self.assertRaises(SystemOneValidationError):
            SystemOneRequest("state", tuple()).validate()


# ── Confidence + normalization math ────────────────────────────────────────────
class TestConfidenceMath(unittest.TestCase):
    def test_uniform_is_low_confidence(self):
        self.assertAlmostEqual(normalized_entropy_confidence([0.5, 0.5]), 0.0, places=6)
        self.assertAlmostEqual(normalized_entropy_confidence([0.25] * 4), 0.0, places=6)

    def test_concentrated_is_high_confidence(self):
        c = normalized_entropy_confidence([0.98, 0.02])
        self.assertGreater(c, 0.85)

    def test_confidence_monotonic(self):
        flat = normalized_entropy_confidence([0.4, 0.35, 0.25])
        peaked = normalized_entropy_confidence([0.8, 0.15, 0.05])
        self.assertGreater(peaked, flat)

    def test_confidence_bounds(self):
        for probs in ([1.0, 0.0], [0.33, 0.33, 0.34], [0.6, 0.4]):
            c = normalized_entropy_confidence(probs)
            self.assertGreaterEqual(c, 0.0)
            self.assertLessEqual(c, 1.0)

    def test_normalize_sums_to_one(self):
        out = normalize([2.0, 2.0, 4.0])
        self.assertAlmostEqual(sum(out), 1.0, places=9)
        self.assertAlmostEqual(out[2], 0.5, places=9)

    def test_normalize_all_zero_is_uniform(self):
        out = normalize([0.0, 0.0, 0.0])
        self.assertEqual(out, [1 / 3, 1 / 3, 1 / 3])


# ── Schema safety (coercion) ────────────────────────────────────────────────────
class TestSchemaSafety(unittest.TestCase):
    def test_choice_coerced_to_answer_space_size(self):
        q = Choice("q", "Which?", ("a", "b", "c"))
        # Provider returns wrong length + junk — must be coerced to len 3, summing 1.
        out = _coerce([5.0, 1.0, 2.0, 99.0, -3.0], q)
        self.assertEqual(len(out), 3)
        self.assertAlmostEqual(sum(out), 1.0, places=9)

    def test_choice_short_output_padded(self):
        q = Choice("q", "Which?", ("a", "b", "c"))
        out = _coerce([1.0], q)  # too short
        self.assertEqual(len(out), 3)
        self.assertAlmostEqual(sum(out), 1.0, places=9)

    def test_noul_clamped(self):
        q = Claim("q", "true?")
        self.assertEqual(_coerce([1.7], q), [1.0])
        self.assertEqual(_coerce([-0.4], q), [0.0])

    def test_winner_always_in_option_set(self):
        # Even with a nonsense provider, the winner is a declared option.
        q = Choice("q", "Which?", ("alpha", "beta"))
        prov = ScriptedProvider({"q": [3.0, 1.0]})
        res = judge("state", [q], provider=prov)["q"]
        self.assertIn(res.winner, ("alpha", "beta"))
        self.assertEqual(res.winner, "alpha")


# ── Engine behavior ────────────────────────────────────────────────────────────
class TestEngine(unittest.TestCase):
    def test_noul_value_threshold(self):
        prov = ScriptedProvider({"a": [0.96], "b": [0.10]})
        resp = judge("s", [Claim("a", "?"), Claim("b", "?")], provider=prov)
        self.assertTrue(resp["a"].value)
        self.assertFalse(resp["b"].value)
        self.assertAlmostEqual(resp["a"].probability, 0.96, places=6)

    def test_choice_distribution_and_confidence(self):
        prov = ScriptedProvider({"team": [0.58, 0.37, 0.05]})
        q = Choice("team", "Which team?", ("billing", "technical", "account"))
        res = judge("s", [q], provider=prov)["team"]
        self.assertEqual(res.winner, "billing")
        self.assertAlmostEqual(res.distribution["billing"], 0.58, places=6)
        self.assertAlmostEqual(sum(res.distribution.values()), 1.0, places=6)
        self.assertTrue(0.0 <= res.confidence <= 1.0)

    def test_score_weighted_position_between_levels(self):
        # Mass split between level 1 and 2 -> score between 1 and 2.
        prov = ScriptedProvider({"sev": [0.0, 0.5, 0.5, 0.0]})
        s = Score.from_labels("sev", "How severe?",
                              ["minor", "moderate", "serious", "critical"])
        res = judge("s", [s], provider=prov)["sev"]
        self.assertAlmostEqual(res.score, 1.5, places=6)
        self.assertIn(res.winner_level, (1, 2))
        self.assertEqual(res.legend[3], "critical")

    def test_parallel_eval_all_questions_answered(self):
        table = {f"q{i}": [0.9] for i in range(7)}
        questions = [Claim(f"q{i}", f"question {i}?") for i in range(7)]
        prov = ScriptedProvider(table)
        resp = judge("shared state", questions, provider=prov)
        self.assertEqual(set(resp.results.keys()), {f"q{i}" for i in range(7)})
        for i in range(7):
            self.assertTrue(resp[f"q{i}"].value)

    def test_result_order_preserved(self):
        questions = [Claim("first", "?"), Claim("second", "?"), Claim("third", "?")]
        prov = ScriptedProvider({"first": [0.9], "second": [0.9], "third": [0.9]})
        resp = judge("s", questions, provider=prov)
        self.assertEqual(list(resp.results.keys()), ["first", "second", "third"])

    def test_question_independence(self):
        # Two questions, same state: each answer depends only on its own dist.
        prov = ScriptedProvider({"pos": [0.95], "neg": [0.05]})
        resp = judge("s", [Claim("pos", "?"), Claim("neg", "?")], provider=prov)
        self.assertGreater(resp["pos"].probability, resp["neg"].probability)


# ── Semantic-IF + routing ────────────────────────────────────────────────────
class TestSemanticIf(unittest.TestCase):
    def test_semantic_if_noul(self):
        prov = ScriptedProvider({"risk": [0.97]})
        res = judge("s", [Claim("risk", "safeguarding risk?")], provider=prov)["risk"]
        self.assertTrue(semantic_if(res, threshold=0.95))
        self.assertFalse(semantic_if(res, threshold=0.99))

    def test_semantic_if_choice_needs_threshold_and_confidence(self):
        prov = ScriptedProvider({"t": [0.55, 0.45]})
        res = judge("s", [Choice("t", "?", ("a", "b"))], provider=prov)["t"]
        # winner prob 0.55 < 0.9 threshold -> False
        self.assertFalse(semantic_if(res, threshold=0.9))

    def test_score_at_least_escalation(self):
        prov = ScriptedProvider({"sev": [0.1, 0.1, 0.4, 0.4]})
        s = Score.from_labels("sev", "?", ["a", "b", "c", "d"])
        res = judge("s", [s], provider=prov)["sev"]
        # mass at level>=2 is 0.8 >= 0.5
        self.assertTrue(score_at_least(res, 2, mass_threshold=0.5))
        # mass at level>=3 is 0.4 < 0.5
        self.assertFalse(score_at_least(res, 3, mass_threshold=0.5))

    def test_route_by_confidence(self):
        prov = ScriptedProvider({
            "hi": [0.98, 0.02],
            "mid": [0.72, 0.28],
            "lo": [0.34, 0.33, 0.33],
        })
        resp = judge("s", [
            Choice("hi", "?", ("a", "b")),
            Choice("mid", "?", ("a", "b")),
            Choice("lo", "?", ("a", "b", "c")),
        ], provider=prov)
        self.assertEqual(route_by_confidence(resp["hi"]), Decision.ACT)
        self.assertEqual(route_by_confidence(resp["lo"]), Decision.REASON)
        self.assertIn(route_by_confidence(resp["mid"]), (Decision.VERIFY, Decision.ACT, Decision.REASON))


# ── Service (wire format) + mock provider ─────────────────────────────────────
class TestService(unittest.TestCase):
    def test_parse_question_types(self):
        self.assertEqual(parse_question({"id": "a", "type": "claim", "question": "?"}).kind, "claim")
        self.assertEqual(parse_question({"id": "b", "type": "choice", "question": "?",
                                         "options": ["x", "y"]}).kind, "choice")
        self.assertEqual(parse_question({"id": "c", "type": "score", "question": "?",
                                         "levels": ["l0", "l1"]}).kind, "score")

    def test_parse_unknown_type_raises(self):
        with self.assertRaises(SystemOneValidationError):
            parse_question({"id": "a", "type": "bogus", "question": "?"})

    def test_run_system_one_wire_roundtrip_mock(self):
        payload = {
            "state": {"message": "I want a refund for my broken order"},
            "questions": [
                {"id": "refund", "type": "claim", "question": "Does this request a refund?"},
                {"id": "team", "type": "choice", "question": "Which team?",
                 "options": ["Billing", "Technical", "Refund", "Other"]},
                {"id": "sev", "type": "score", "question": "How urgent?",
                 "levels": ["low", "broken", "critical"]},
            ],
        }
        out = run_system_one(payload, provider=MockProvider())
        self.assertEqual(set(out["results"].keys()), {"refund", "team", "sev"})
        # Mock is deterministic: "refund" keyword present in state -> winner "Refund".
        self.assertEqual(out["results"]["team"]["winner"], "Refund")
        # Schema safety: every distribution sums ~1.
        for r in ("team", "sev"):
            self.assertAlmostEqual(sum(out["results"][r]["distribution"].values()), 1.0, places=3)

    def test_mock_provider_deterministic(self):
        payload = {
            "state": "the tenant reports a safeguarding concern",
            "questions": [{"id": "sg", "type": "claim",
                           "question": "Does this indicate a safeguarding concern?"}],
        }
        a = run_system_one(payload, provider=MockProvider())
        b = run_system_one(payload, provider=MockProvider())
        self.assertEqual(a, b)
        self.assertGreater(a["results"]["sg"]["probability"], 0.5)


class TestEngineInjection(unittest.TestCase):
    def test_get_engine_with_provider_is_isolated(self):
        eng = get_engine(provider=MockProvider())
        self.assertIsInstance(eng, SystemOneEngine)


if __name__ == "__main__":
    unittest.main(verbosity=2)
