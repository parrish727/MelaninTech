"""
Tests for the System One eval scoring math (scripts/system_one_eval.py).

Offline: builds results directly and checks accuracy/Brier/ECE/confidence.
Run: python AI/darius/tests/test_system_one_eval.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from AI.darius.system_one import Choice, Claim, MockProvider, Score, get_engine  # noqa: E402
from AI.darius.system_one.types import SystemOneRequest  # noqa: E402
from scripts import system_one_eval as se  # noqa: E402


def _judge(state, question):
    return get_engine(provider=MockProvider()).judge(
        SystemOneRequest(state=state, questions=(question,))
    )[question.id]


class TestTruthAndScoring(unittest.TestCase):
    def test_claim_correct_and_brier(self):
        case = {"id": "c", "type": "claim", "state": "wants a refund now",
                "question": "refund?", "ground_truth": True, "lob": "core"}
        q = Claim("c", "refund?")

        class P:  # provider that returns P(true)=0.9
            def distribution(self, s, question): return [0.9]
        res = get_engine(provider=P()).judge(SystemOneRequest(case["state"], (q,)))["c"]
        row = se.score_case(res, case, q)
        self.assertTrue(row["correct"])
        self.assertAlmostEqual(row["brier"], (0.9 - 1.0) ** 2, places=4)
        self.assertAlmostEqual(row["p_correct"], 0.9, places=4)

    def test_choice_correct_winner(self):
        case = {"id": "r", "type": "choice", "state": "double charged",
                "question": "team?", "options": ["Billing", "Tech"],
                "ground_truth": "Billing", "lob": "core"}
        q = Choice("r", "team?", ("Billing", "Tech"))

        class P:
            def distribution(self, s, question): return [0.8, 0.2]
        res = get_engine(provider=P()).judge(SystemOneRequest(case["state"], (q,)))["r"]
        row = se.score_case(res, case, q)
        self.assertTrue(row["correct"])
        # Brier = (0.8-1)^2 + (0.2-0)^2
        self.assertAlmostEqual(row["brier"], 0.04 + 0.04, places=4)

    def test_choice_wrong_winner(self):
        case = {"id": "r", "type": "choice", "state": "x", "question": "team?",
                "options": ["Billing", "Tech"], "ground_truth": "Tech", "lob": "core"}
        q = Choice("r", "team?", ("Billing", "Tech"))

        class P:
            def distribution(self, s, question): return [0.7, 0.3]
        res = get_engine(provider=P()).judge(SystemOneRequest(case["state"], (q,)))["r"]
        row = se.score_case(res, case, q)
        self.assertFalse(row["correct"])
        self.assertAlmostEqual(row["p_correct"], 0.3, places=4)

    def test_score_level_match(self):
        case = {"id": "s", "type": "score", "state": "down hard", "question": "sev?",
                "levels": ["none", "degraded", "down"], "ground_truth": 2, "lob": "core"}
        q = Score.from_labels("s", "sev?", ["none", "degraded", "down"])

        class P:
            def distribution(self, s, question): return [0.1, 0.2, 0.7]
        res = get_engine(provider=P()).judge(SystemOneRequest(case["state"], (q,)))["s"]
        row = se.score_case(res, case, q)
        self.assertTrue(row["correct"])
        self.assertAlmostEqual(row["p_correct"], 0.7, places=4)


class TestECE(unittest.TestCase):
    def test_perfect_calibration_low_ece(self):
        # All confident and all correct -> ECE near 0.
        rows = [{"winner_confidence": 0.95, "correct": True} for _ in range(10)]
        self.assertLess(se.expected_calibration_error(rows), 0.1)

    def test_overconfident_high_ece(self):
        # High confidence but half wrong -> large calibration gap.
        rows = [{"winner_confidence": 0.95, "correct": i % 2 == 0} for i in range(10)]
        self.assertGreater(se.expected_calibration_error(rows), 0.3)

    def test_empty_ece_zero(self):
        self.assertEqual(se.expected_calibration_error([]), 0.0)


class TestConfidence(unittest.TestCase):
    def _run(self, acc, ece, n, errors=0):
        return {"n": n, "errors": errors, "accuracy": acc, "brier": 0.2, "ece": ece, "by_type": {}, "rows": []}

    def test_parity_with_baseline_high_conf(self):
        base = self._run(0.9, 0.05, 100)
        cand = self._run(0.9, 0.05, 100)
        conf, _ = se.system_one_confidence(cand, base)
        self.assertGreaterEqual(conf, 85)

    def test_worse_accuracy_lower_conf(self):
        base = self._run(0.9, 0.05, 100)
        good, _ = se.system_one_confidence(self._run(0.9, 0.05, 100), base)
        bad, _ = se.system_one_confidence(self._run(0.5, 0.05, 100), base)
        self.assertGreater(good, bad)

    def test_errors_cap_confidence(self):
        base = self._run(0.9, 0.05, 10)
        conf, _ = se.system_one_confidence(self._run(0.9, 0.05, 10, errors=6), base)
        self.assertLessEqual(conf, 10.0)

    def test_poor_calibration_lowers_conf(self):
        base = self._run(0.9, 0.02, 100)
        well, _ = se.system_one_confidence(self._run(0.9, 0.02, 100), base)
        poorly, _ = se.system_one_confidence(self._run(0.9, 0.30, 100), base)
        self.assertGreater(well, poorly)


class TestGoldenSetLoads(unittest.TestCase):
    def test_golden_set_parses_and_runs(self):
        cases = se.load_golden()
        self.assertGreater(len(cases), 0)
        # Every case must build a valid question + a resolvable ground truth.
        for c in cases:
            q = se.build_question(c)
            vec, idx = se.truth_vector(c, q)
            self.assertTrue(0 <= idx < max(1, len(vec)))

    def test_run_model_mock_no_errors(self):
        cases = se.load_golden()
        run = se.run_model(MockProvider(), cases)
        self.assertEqual(run["errors"], 0, f"mock run had errors: "
                         f"{[r for r in run['rows'] if 'error' in r][:3]}")
        self.assertGreater(run["n"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
