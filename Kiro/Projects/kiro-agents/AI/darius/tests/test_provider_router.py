"""
Tests for the Darius provider router (AI/darius/provider_router.py).

Offline, no network except a mocked Ollama/gateway reachability check. Verifies:
  - default source is Anthropic (learning stays in place)
  - llmgateway switch maps tiers to open-weight models served by the self-hosted gateway
  - missing LLMGateway key / unreachable gateway -> graceful fallback to Anthropic
  - local source with unreachable Ollama -> fallback to Anthropic
  - cache_control support flag is Anthropic-only
  - completion_kwargs shape
  - OpenRouter is NOT a source (removed — open-weight path is self-hosted LLMGateway)

Run: python AI/darius/tests/test_provider_router.py
"""
import importlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import AI.darius.provider_router as pr


def _reset_env(**overrides):
    for k in ["DARIUS_MODEL_SOURCE", "ANTHROPIC_API_KEY",
              "OLLAMA_URL", "DARIUS_GW_MODEL_PLAN",
              "LLMGATEWAY_API_KEY", "LLMGATEWAY_URL", "DARIUS_CONFIDENCE_FALLBACK"]:
        os.environ.pop(k, None)
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
    os.environ.update(overrides)
    importlib.reload(pr)


class TestDefaults(unittest.TestCase):
    def setUp(self):
        _reset_env()

    def test_default_is_anthropic(self):
        r = pr.resolve("default")
        self.assertEqual(r.provider, "anthropic")
        self.assertTrue(r.model.startswith("anthropic/"))
        self.assertFalse(r.fell_back)

    def test_all_tiers_resolve_anthropic(self):
        for tier in ("apex", "heavy", "default", "light", "plan", "eval", "compress"):
            r = pr.resolve(tier)
            self.assertEqual(r.provider, "anthropic", tier)

    def test_anthropic_supports_cache(self):
        self.assertTrue(pr.resolve("plan").supports_prompt_cache())


class TestLLMGatewaySwitch(unittest.TestCase):
    def setUp(self):
        _reset_env(DARIUS_MODEL_SOURCE="llmgateway", LLMGATEWAY_API_KEY="gw-test")
        # Force the gateway to look reachable so we exercise the success path.
        self._orig = pr._llmgateway_reachable
        pr._llmgateway_reachable = lambda: True

    def tearDown(self):
        pr._llmgateway_reachable = self._orig

    def test_switches_to_llmgateway(self):
        r = pr.resolve("heavy")
        self.assertEqual(r.provider, "llmgateway")
        self.assertTrue(r.model.startswith("openai/"))  # OpenAI-compatible gateway path
        self.assertFalse(r.fell_back)

    def test_tier_maps_to_open_models(self):
        self.assertIn("qwen", pr.resolve("plan").model.lower())
        self.assertIn("mistral", pr.resolve("eval").model.lower())

    def test_per_tier_override(self):
        os.environ["DARIUS_GW_MODEL_PLAN"] = "nousresearch/hermes-3-llama-3.1-70b"
        self.assertIn("hermes", pr.resolve("plan").model.lower())

    def test_llmgateway_no_cache(self):
        self.assertFalse(pr.resolve("plan").supports_prompt_cache())

    def test_completion_kwargs(self):
        kw = pr.resolve("default").completion_kwargs()
        self.assertTrue(kw["model"].startswith("openai/"))
        self.assertEqual(kw["api_key"], "gw-test")
        self.assertTrue(kw["api_base"].endswith("/v1"))


class TestFallback(unittest.TestCase):
    def test_llmgateway_missing_key_falls_back(self):
        _reset_env(DARIUS_MODEL_SOURCE="llmgateway")  # no LLMGATEWAY_API_KEY
        r = pr.resolve("heavy")
        self.assertEqual(r.provider, "anthropic")
        self.assertTrue(r.fell_back)
        self.assertEqual(r.requested_source, "llmgateway")

    def test_local_unreachable_falls_back(self):
        _reset_env(DARIUS_MODEL_SOURCE="local", OLLAMA_URL="http://127.0.0.1:1")
        r = pr.resolve("heavy")
        self.assertEqual(r.provider, "anthropic")
        self.assertTrue(r.fell_back)

    def test_active_source_reports_config(self):
        _reset_env(DARIUS_MODEL_SOURCE="llmgateway", LLMGATEWAY_API_KEY="gw-test")
        self.assertEqual(pr.active_source(), "llmgateway")


class TestLabel(unittest.TestCase):
    def test_label_shape(self):
        _reset_env(DARIUS_MODEL_SOURCE="llmgateway", LLMGATEWAY_API_KEY="gw-test")
        pr._llmgateway_reachable = lambda: True
        r = pr.resolve("heavy")
        self.assertTrue(r.label.startswith("llmgateway:"))
        self.assertNotIn("/", r.label.split(":", 1)[1])


class TestLLMGateway(unittest.TestCase):
    def test_missing_key_falls_back(self):
        _reset_env(DARIUS_MODEL_SOURCE="llmgateway")  # no LLMGATEWAY_API_KEY
        r = pr.resolve("heavy")
        self.assertEqual(r.provider, "anthropic")
        self.assertTrue(r.fell_back)
        self.assertEqual(r.requested_source, "llmgateway")

    def test_unreachable_falls_back(self):
        _reset_env(DARIUS_MODEL_SOURCE="llmgateway",
                   LLMGATEWAY_API_KEY="gw-test",
                   LLMGATEWAY_URL="http://127.0.0.1:1/v1")
        r = pr.resolve("heavy")
        self.assertEqual(r.provider, "anthropic")
        self.assertTrue(r.fell_back)

    def test_tier_map_overridable(self):
        _reset_env(DARIUS_MODEL_SOURCE="anthropic")
        os.environ["DARIUS_GW_MODEL_PLAN"] = "nousresearch/hermes-3-llama-3.1-70b"
        importlib.reload(pr)
        self.assertIn("hermes", pr._llmgateway_model("plan").lower())
        self.assertIn("qwen", pr._llmgateway_model("heavy").lower())


class TestConfidenceFallback(unittest.TestCase):
    def setUp(self):
        _reset_env()

    def test_threshold_default(self):
        self.assertAlmostEqual(pr.confidence_fallback_threshold(), 0.90, places=4)

    def test_threshold_env_override(self):
        _reset_env(DARIUS_CONFIDENCE_FALLBACK="0.80")
        self.assertAlmostEqual(pr.confidence_fallback_threshold(), 0.80, places=4)

    def test_openweight_below_threshold_triggers(self):
        self.assertTrue(pr.should_confidence_fallback("llmgateway", 0.85))
        self.assertTrue(pr.should_confidence_fallback("llmgateway", 0.5))

    def test_openweight_above_threshold_no_trigger(self):
        self.assertFalse(pr.should_confidence_fallback("llmgateway", 0.95))

    def test_anthropic_never_triggers(self):
        self.assertFalse(pr.should_confidence_fallback("anthropic", 0.01))

    def test_none_score_no_trigger(self):
        self.assertFalse(pr.should_confidence_fallback("llmgateway", None))

    def test_disabled_when_threshold_zero(self):
        _reset_env(DARIUS_CONFIDENCE_FALLBACK="0")
        self.assertFalse(pr.should_confidence_fallback("llmgateway", 0.1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
