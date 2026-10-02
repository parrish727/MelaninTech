#!/usr/bin/env python3
"""
A/B Model Parity Eval — Darius cutover readiness harness.

Runs the existing golden sets (eval/golden_sets/<lob>/*.yaml) through a Claude
BASELINE plus every CANDIDATE model (local Ollama + self-hosted LLMGateway open-weights), scores
each response identically to scripts/eval_runner.py (keyword 0.4 + Claude-judge 0.6),
then computes, per candidate:

  - overall score and per-LOB score
  - delta vs the Claude baseline (overall + per LOB)
  - win / tie / loss counts per case vs baseline
  - a CUTOVER CONFIDENCE % with an explicit, defensible rubric

Design goals:
  * Does NOT require Darius to be running — models are called directly via litellm,
    so we measure the MODEL, not the orchestration layer.
  * Any provider that is unreachable/unconfigured is SKIPPED gracefully (recorded
    as "unavailable"), never crashes the run.
  * `--mock` runs a deterministic self-test with zero network for CI / smoke tests.

Usage:
    # Full run (needs ANTHROPIC_API_KEY; OLLAMA_URL and LLMGATEWAY_URL/LLMGATEWAY_API_KEY optional)
    python scripts/ab_eval.py

    # One LOB only
    python scripts/ab_eval.py --lob orthoflow

    # Only specific candidates
    python scripts/ab_eval.py --candidates qwen-2.5-72b-gateway,kimi-k2-gateway

    # Self-test with no network (proves the harness end-to-end)
    python scripts/ab_eval.py --mock

    # Keyword-only scoring (no judge cost)
    python scripts/ab_eval.py --fast

Env:
    ANTHROPIC_API_KEY   — baseline + judge (required unless --mock or baseline overridden)
    LLMGATEWAY_API_KEY   — enables llmgateway candidates
    OLLAMA_URL          — enables ollama candidates (default http://ollama:11434)

Artifacts:
    eval/reports/ab_report_<timestamp>.json    — full machine-readable results
    eval/reports/ab_report_<timestamp>.md       — human-readable summary
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ab_eval")

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SETS_DIR = ROOT / "eval" / "golden_sets"
CANDIDATES_FILE = ROOT / "eval" / "ab_candidates.yaml"
REPORTS_DIR = ROOT / "eval" / "reports"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLMGATEWAY_URL = os.environ.get("LLMGATEWAY_URL", "http://llmgateway:4001/v1")
LLMGATEWAY_API_KEY = os.environ.get("LLMGATEWAY_API_KEY", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")

# Case is considered a "pass" at this combined score (matches eval_runner.py).
CASE_PASS = 0.6
# A candidate is "cutover-ready" for a LOB at/above this LOB score AND within
# PARITY_TOLERANCE of the baseline (matches eval_runner default gate of 0.85).
LOB_GATE = float(os.environ.get("EVAL_THRESHOLD", "0.85"))
# How far below baseline we still call "parity" (judge scoring has noise).
PARITY_TOLERANCE = 0.03
# A per-case win/loss must differ by more than this to count (else it's a tie).
CASE_MARGIN = 0.05

# Darius operating context so candidate answers are comparable to production.
DARIUS_SYSTEM = (
    "You are Darius, the AI operations and delivery intelligence layer for "
    "Melanin Technologies Inc. You answer questions and produce work for the "
    "company's line-of-business products (OrthoFlow, ParcelPro, ArtistOS, HTC) "
    "and internal platform. Be direct, concrete, and technically precise. Lead "
    "with the answer, then supporting detail. Use specific tech names, service "
    "names, and correct domain terminology."
)

JUDGE_PROMPT = """You are an evaluation judge for an AI agent system. Score the agent's response based on:
1. Relevance — Does it address the query?
2. Accuracy — Are the facts correct?
3. Completeness — Does it cover the expected behavior?
4. No hallucination — Does it avoid making things up?

Query: {query}
Expected behavior: {expected_behavior}
Expected keywords (at least some should appear): {expected_keywords}
Agent response: {response}

Score from 0.0 to 1.0. Output ONLY a JSON object:
{{"score": 0.XX, "reasoning": "brief explanation"}}"""


# ─────────────────────────────────────────────────────────────────────────────
# YAML loading — prefer PyYAML, fall back to a minimal parser for the simple,
# flat golden-set / candidate files so the harness runs in bare environments.
# ─────────────────────────────────────────────────────────────────────────────
def _load_yaml(path: Path) -> dict | list:
    try:
        import yaml  # type: ignore
        with open(path) as fp:
            return yaml.safe_load(fp)
    except ModuleNotFoundError:
        with open(path) as fp:
            return _mini_yaml(fp.read())


def _mini_yaml(text: str):
    """
    Minimal YAML subset parser sufficient for the golden-set and candidate files:
      - top-level `key: value` scalars and `key:` mapping/list headers
      - `- ` list items that begin mapping blocks
      - nested `key: value` scalars and `key:` + `- item` string lists
    Not a general YAML parser; handles only the shapes used in eval/.
    """
    root: dict = {}
    lines = [ln.rstrip() for ln in text.splitlines()]
    # Strip comments and blanks
    clean = []
    for ln in lines:
        if not ln.strip() or ln.strip().startswith("#"):
            continue
        clean.append(ln)

    def indent(s: str) -> int:
        return len(s) - len(s.lstrip(" "))

    def strip_q(v: str):
        v = v.strip()
        # Inline flow sequence: [a, "b", c]  -> real list (used by options/levels)
        if len(v) >= 2 and v[0] == "[" and v[-1] == "]":
            inner = v[1:-1].strip()
            if not inner:
                return []
            items = []
            buf = ""
            quote = None
            for ch in inner:
                if quote:
                    if ch == quote:
                        quote = None
                    else:
                        buf += ch
                elif ch in "\"'":
                    quote = ch
                elif ch == ",":
                    items.append(buf.strip())
                    buf = ""
                else:
                    buf += ch
            if buf.strip():
                items.append(buf.strip())
            return [it.strip().strip("\"'") for it in items]
        if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
            return v[1:-1]
        return v

    i = 0
    n = len(clean)

    def parse_block(base_indent: int):
        nonlocal i
        # Returns either a dict or a list depending on first token at this indent.
        # Peek
        if i >= n:
            return {}
        first = clean[i]
        if first.lstrip().startswith("- "):
            lst = []
            while i < n and indent(clean[i]) == base_indent and clean[i].lstrip().startswith("- "):
                item_line = clean[i]
                rest = item_line.lstrip()[2:]  # after "- "
                item_indent = indent(item_line)
                # inline "- key: value" starts a mapping
                mapping: dict = {}
                if ":" in rest:
                    k, _, v = rest.partition(":")
                    if v.strip():
                        mapping[k.strip()] = strip_q(v)
                    else:
                        # nested block under this key
                        i += 1
                        mapping[k.strip()] = parse_block(_next_indent(item_indent + 2))
                        # continue collecting sibling keys of this list item below
                        _collect_map(mapping, item_indent + 2)
                        lst.append(mapping)
                        continue
                    i += 1
                    _collect_map(mapping, item_indent + 2)
                    lst.append(mapping)
                else:
                    i += 1
                    lst.append(strip_q(rest))
            return lst
        else:
            d: dict = {}
            _collect_map(d, base_indent)
            return d

    def _next_indent(default: int) -> int:
        return indent(clean[i]) if i < n else default

    def _collect_map(d: dict, min_indent: int):
        nonlocal i
        while i < n:
            ln = clean[i]
            ind = indent(ln)
            if ind < min_indent:
                break
            if ln.lstrip().startswith("- "):
                break
            k, _, v = ln.lstrip().partition(":")
            k = k.strip()
            if v.strip():
                d[k] = strip_q(v)
                i += 1
            else:
                i += 1
                child = parse_block(_next_indent(ind + 2))
                d[k] = child
        return d

    _collect_map(root, 0)
    return root


# ─────────────────────────────────────────────────────────────────────────────
# Golden set loading (same structure as eval_runner.py)
# ─────────────────────────────────────────────────────────────────────────────
def load_golden_sets(lob: str | None = None) -> dict[str, list[dict]]:
    lob_cases: dict[str, list[dict]] = {}
    if lob:
        folders = [GOLDEN_SETS_DIR / lob]
    else:
        folders = sorted([d for d in GOLDEN_SETS_DIR.iterdir() if d.is_dir()])

    for folder in folders:
        if not folder.exists():
            logger.warning(f"LOB folder not found: {folder}")
            continue
        lob_name = folder.name
        cases: list[dict] = []
        for f in sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml")):
            data = _load_yaml(f)
            if isinstance(data, dict):
                file_project = data.get("project", lob_name)
                file_lob = data.get("lob", lob_name)
                for case in data.get("cases", []):
                    case.setdefault("project", file_project)
                    case.setdefault("lob", file_lob)
                    cases.append(case)
            elif isinstance(data, list):
                cases.extend(data)
        if cases:
            lob_cases[lob_name] = cases
    return lob_cases


def load_candidate_config() -> dict:
    return _load_yaml(CANDIDATES_FILE)


# ─────────────────────────────────────────────────────────────────────────────
# Provider abstraction — one generate() per (provider, model)
# ─────────────────────────────────────────────────────────────────────────────
class ProviderError(Exception):
    """Raised when a provider is unreachable or unconfigured."""


def _ollama_reachable() -> bool:
    import httpx

    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _llmgateway_reachable() -> bool:
    import httpx

    base = LLMGATEWAY_URL.rstrip("/")
    base = base.removesuffix("/v1")
    try:
        return httpx.get(f"{base}/health", timeout=3).status_code == 200
    except Exception:
        return False


class ModelClient:
    """Wraps a single model behind a uniform generate(prompt) -> (text, latency_ms)."""

    def __init__(self, name: str, provider: str, model: str, timeout: int = 180, mock: bool = False):
        self.name = name
        self.provider = provider
        self.model = model
        self.timeout = timeout
        self.mock = mock

    def preflight(self) -> tuple[bool, str]:
        """Return (available, reason). Cheap check before running cases."""
        if self.mock or self.provider == "mock":
            return True, "mock"
        if self.provider == "anthropic":
            if not ANTHROPIC_API_KEY:
                return False, "ANTHROPIC_API_KEY not set"
            return True, "ok"
        if self.provider == "llmgateway":
            if not LLMGATEWAY_API_KEY:
                return False, "LLMGATEWAY_API_KEY not set"
            if not _llmgateway_reachable():
                return False, f"LLMGateway unreachable at {LLMGATEWAY_URL}"
            return True, "ok"
        if self.provider == "ollama":
            if not _ollama_reachable():
                return False, f"Ollama unreachable at {OLLAMA_URL}"
            return True, "ok"
        return False, f"unknown provider '{self.provider}'"

    def generate(self, prompt: str) -> tuple[str, int]:
        if self.mock or self.provider == "mock":
            return _mock_response(self.name, prompt, _CURRENT_PROMPT.get("keywords")), 1

        start = time.time()
        try:
            if self.provider == "anthropic":
                text = self._call_litellm(f"anthropic/{self.model}", api_key=ANTHROPIC_API_KEY)
            elif self.provider == "llmgateway":
                # OpenAI-compatible self-hosted gateway: openai/<model> + api_base.
                text = self._call_litellm(
                    f"openai/{self.model}", api_key=LLMGATEWAY_API_KEY, api_base=LLMGATEWAY_URL
                )
            elif self.provider == "ollama":
                text = self._call_litellm(
                    f"ollama/{self.model}", api_base=OLLAMA_URL
                )
            else:
                raise ProviderError(f"unknown provider '{self.provider}'")
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(f"{self.name} generation failed: {e}") from e

        latency_ms = int((time.time() - start) * 1000)
        return text, latency_ms

    def _call_litellm(self, model_id: str, api_key: str | None = None, api_base: str | None = None) -> str:
        from litellm import completion

        kwargs: dict = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": DARIUS_SYSTEM},
                {"role": "user", "content": prompt_wrap(model_id)},
            ],
            "max_tokens": 1024,
            "temperature": 0.2,
            "timeout": self.timeout,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base
        resp = completion(**kwargs)
        return (resp.choices[0].message.content or "").strip()


# _PROMPT is set per-case by run_case; prompt_wrap lets _call_litellm read it.
_CURRENT_PROMPT: dict = {"text": "", "keywords": []}


def prompt_wrap(_model_id: str) -> str:
    return _CURRENT_PROMPT["text"]


def _mock_response(candidate_name: str, prompt: str, expected_keywords: list[str] | None = None) -> str:
    """
    Deterministic pseudo-responses for --mock self-test.

    Each candidate "knows" a fixed fraction (by tier/quality) of the case's own
    expected keywords, so keyword + judge scores differentiate per model and the
    parity / win-tie-loss / confidence math is exercised with a realistic shape.
    Baseline knows all of them.
    """
    coverage = {
        "baseline": 1.00,
        "qwen3-14b-local": 0.55,
        "mistral-small-24b-local": 0.72,
        "hermes3-8b-gateway": 0.70,
        "qwen-2.5-72b-gateway": 0.92,
        "mistral-large-gateway": 0.88,
        "kimi-k2-gateway": 0.90,
    }.get(candidate_name, 0.75)

    kws = expected_keywords or []
    take = max(1, round(len(kws) * coverage)) if kws else 0
    used = kws[:take]
    filler = (
        "This response addresses the query using the platform's standard stack "
        "and conventions. "
    )
    if used:
        return filler + " ".join(f"We use {k}." for k in used)
    return filler + "General overview without specifics."


# ─────────────────────────────────────────────────────────────────────────────
# Scoring — identical weighting to eval_runner.py
# ─────────────────────────────────────────────────────────────────────────────
def score_keyword(response: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    rl = response.lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in rl)
    return found / len(expected_keywords)


def score_llm_judge(
    query: str, response: str, expected_behavior: str, expected_keywords: list[str],
    judge: ModelClient, use_judge: bool,
) -> dict:
    if not use_judge:
        return {"score": None, "reasoning": "judge disabled (--fast)"}
    if judge.mock or judge.provider == "mock":
        # Mock judge: track keyword coverage closely so the self-test produces
        # differentiated, realistic-shaped scores that exercise win/tie/loss.
        kw = score_keyword(response, expected_keywords)
        return {"score": round(min(1.0, 0.15 + kw * 0.85), 3), "reasoning": "mock judge"}
    if not ANTHROPIC_API_KEY:
        return {"score": None, "reasoning": "no ANTHROPIC_API_KEY for judge"}
    try:
        from litellm import completion

        prompt = JUDGE_PROMPT.format(
            query=query,
            expected_behavior=expected_behavior,
            expected_keywords=", ".join(expected_keywords),
            response=response[:3000],
        )
        result = completion(
            model=f"anthropic/{judge.model}",
            api_key=ANTHROPIC_API_KEY,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.0,
        )
        text = (result.choices[0].message.content or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = json.loads(text)
        return {"score": float(data["score"]), "reasoning": data.get("reasoning", "")}
    except Exception as e:
        return {"score": None, "reasoning": f"judge error: {e}"}


def combined_score(kw: float, judge_score: float | None) -> float:
    if judge_score is not None:
        return (kw * 0.4) + (judge_score * 0.6)
    return kw


# ─────────────────────────────────────────────────────────────────────────────
# Run one model across all cases
# ─────────────────────────────────────────────────────────────────────────────
def run_model_over_cases(
    client: ModelClient,
    lob_cases: dict[str, list[dict]],
    judge: ModelClient,
    use_judge: bool,
) -> dict:
    """Returns per-case + per-LOB results for one model."""
    per_case: dict[str, dict] = {}
    lob_scores: dict[str, list[float]] = {}
    all_scores: list[float] = []
    errors = 0

    for lob_name, cases in sorted(lob_cases.items()):
        lob_scores.setdefault(lob_name, [])
        for case in cases:
            cid = case["id"]
            query = case["query"]
            expected_behavior = case.get("expected_behavior", "")
            expected_keywords = case.get("expected_keywords", [])

            _CURRENT_PROMPT["text"] = query
            _CURRENT_PROMPT["keywords"] = expected_keywords
            try:
                response, latency_ms = client.generate(query)
            except ProviderError as e:
                per_case[cid] = {
                    "lob": lob_name, "status": "error", "score": 0.0,
                    "error": str(e), "latency_ms": None,
                }
                errors += 1
                lob_scores[lob_name].append(0.0)
                all_scores.append(0.0)
                continue

            kw = score_keyword(response, expected_keywords)
            judge_res = score_llm_judge(
                query, response, expected_behavior, expected_keywords, judge, use_judge
            )
            score = combined_score(kw, judge_res["score"])
            per_case[cid] = {
                "lob": lob_name,
                "status": "pass" if score >= CASE_PASS else "fail",
                "score": round(score, 3),
                "keyword_score": round(kw, 3),
                "judge_score": judge_res["score"],
                "judge_reasoning": judge_res.get("reasoning", ""),
                "latency_ms": latency_ms,
                "response_preview": response[:240],
            }
            lob_scores[lob_name].append(score)
            all_scores.append(score)

    lob_avg = {
        lob: round(sum(s) / len(s), 3) if s else 0.0 for lob, s in lob_scores.items()
    }
    overall = round(sum(all_scores) / len(all_scores), 3) if all_scores else 0.0
    return {
        "per_case": per_case,
        "lob_scores": lob_avg,
        "overall": overall,
        "errors": errors,
        "case_count": len(all_scores),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Parity + confidence
# ─────────────────────────────────────────────────────────────────────────────
def compute_parity(baseline_run: dict, candidate_run: dict) -> dict:
    """Win/tie/loss per case + per-LOB deltas + confidence for one candidate."""
    b_cases = baseline_run["per_case"]
    c_cases = candidate_run["per_case"]

    wins = ties = losses = 0
    case_deltas = {}
    for cid, b in b_cases.items():
        c = c_cases.get(cid)
        if not c:
            continue
        d = round(c["score"] - b["score"], 3)
        case_deltas[cid] = d
        if d > CASE_MARGIN:
            wins += 1
        elif d < -CASE_MARGIN:
            losses += 1
        else:
            ties += 1

    lob_delta = {}
    lobs_at_parity = 0
    lobs_total = 0
    for lob, b_score in baseline_run["lob_scores"].items():
        c_score = candidate_run["lob_scores"].get(lob, 0.0)
        delta = round(c_score - b_score, 3)
        at_parity = (c_score >= LOB_GATE) and (delta >= -PARITY_TOLERANCE)
        lob_delta[lob] = {
            "baseline": b_score,
            "candidate": c_score,
            "delta": delta,
            "at_parity": at_parity,
            "meets_gate": c_score >= LOB_GATE,
        }
        lobs_total += 1
        if at_parity:
            lobs_at_parity += 1

    overall_delta = round(candidate_run["overall"] - baseline_run["overall"], 3)
    confidence, rubric = _confidence(
        candidate_run, baseline_run, wins, ties, losses,
        lobs_at_parity, lobs_total, overall_delta,
    )

    return {
        "overall_delta": overall_delta,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "case_deltas": case_deltas,
        "lob_delta": lob_delta,
        "lobs_at_parity": lobs_at_parity,
        "lobs_total": lobs_total,
        "cutover_confidence": confidence,
        "confidence_rubric": rubric,
    }


def _confidence(
    candidate_run, baseline_run, wins, ties, losses,
    lobs_at_parity, lobs_total, overall_delta,
) -> tuple[float, dict]:
    """
    Explicit, defensible cutover-confidence rubric (0-100%).

    Four weighted components:
      A. Parity coverage (40%): fraction of LOBs at parity with baseline.
      B. Non-regression  (30%): fraction of cases NOT lost vs baseline (win+tie).
      C. Absolute floor  (20%): candidate overall vs the LOB gate (0.85).
      D. Sample sufficiency (10%): penalizes tiny golden sets — you cannot be
         highly confident on very few cases regardless of scores.

    Sample sufficiency uses a soft ramp: full credit at >=200 cases, linear below.
    Errors (unreachable provider / failed generations) hard-cap confidence low.
    """
    n = max(1, candidate_run["case_count"])
    errors = candidate_run.get("errors", 0)

    # A — parity coverage
    a = (lobs_at_parity / lobs_total) if lobs_total else 0.0
    # B — non-regression
    total_cmp = wins + ties + losses
    b = ((wins + ties) / total_cmp) if total_cmp else 0.0
    # C — absolute floor
    c = min(1.0, candidate_run["overall"] / LOB_GATE) if LOB_GATE else 0.0
    # D — sample sufficiency
    d = min(1.0, n / 200.0)

    raw = (a * 0.40) + (b * 0.30) + (c * 0.20) + (d * 0.10)
    confidence = round(raw * 100, 1)

    # Hard caps: unresolved errors mean we literally couldn't measure the model.
    if errors > 0:
        error_frac = errors / n
        if error_frac >= 0.5:
            confidence = min(confidence, 10.0)
        elif error_frac >= 0.2:
            confidence = min(confidence, 30.0)

    rubric = {
        "A_parity_coverage": {"weight": 0.40, "value": round(a, 3),
                              "detail": f"{lobs_at_parity}/{lobs_total} LOBs at parity"},
        "B_non_regression": {"weight": 0.30, "value": round(b, 3),
                             "detail": f"{wins + ties}/{total_cmp} cases not regressed (w{wins}/t{ties}/l{losses})"},
        "C_absolute_floor": {"weight": 0.20, "value": round(c, 3),
                             "detail": f"overall {candidate_run['overall']:.3f} vs gate {LOB_GATE:.2f}"},
        "D_sample_sufficiency": {"weight": 0.10, "value": round(d, 3),
                                 "detail": f"{n} cases (full credit at 200)"},
        "errors": errors,
        "formula": "confidence = 100 * (0.40*A + 0.30*B + 0.20*C + 0.10*D), capped by error rate",
    }
    return confidence, rubric


def readiness_label(confidence: float, errors: int) -> str:
    if errors > 0 and confidence <= 30:
        return "NOT MEASURABLE (provider errors)"
    if confidence >= 96:
        return "CUTOVER-READY"
    if confidence >= 85:
        return "SHADOW-READY (route in parallel, verify)"
    if confidence >= 60:
        return "PROMISING (needs more data / tuning)"
    return "NOT READY"


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────
def print_console_report(report: dict) -> None:
    b = report["baseline"]
    print(f"\n{'=' * 68}")
    print("  DARIUS A/B MODEL PARITY — CUTOVER READINESS")
    print(f"  Baseline: {b['name']}  overall={b['run']['overall']:.1%}  "
          f"cases={b['run']['case_count']}  LOBs={len(b['run']['lob_scores'])}")
    print(f"  Judge: {report['judge']}   Mode: {report['mode']}")
    print(f"{'=' * 68}")

    for cand in report["candidates"]:
        if cand["status"] != "ran":
            print(f"\n  ⏭  {cand['name']:28s} SKIPPED — {cand['reason']}")
            continue
        run = cand["run"]
        par = cand["parity"]
        conf = par["cutover_confidence"]
        label = readiness_label(conf, run["errors"])
        print(f"\n  ── {cand['name']} ──")
        print(f"     overall {run['overall']:.1%}  (Δ vs baseline {par['overall_delta']:+.1%})")
        print(f"     win/tie/loss: {par['wins']}/{par['ties']}/{par['losses']}   "
              f"LOBs at parity: {par['lobs_at_parity']}/{par['lobs_total']}")
        for lob, ld in sorted(par["lob_delta"].items()):
            icon = "✓" if ld["at_parity"] else "✗"
            print(f"       {icon} {lob:16s} cand={ld['candidate']:.1%}  "
                  f"base={ld['baseline']:.1%}  Δ={ld['delta']:+.1%}")
        print(f"     >>> CUTOVER CONFIDENCE: {conf:.1f}%  [{label}]")

    print(f"\n{'=' * 68}")
    print("  RANKING (by cutover confidence)")
    ranked = sorted(
        [c for c in report["candidates"] if c["status"] == "ran"],
        key=lambda c: c["parity"]["cutover_confidence"],
        reverse=True,
    )
    for i, c in enumerate(ranked, 1):
        conf = c["parity"]["cutover_confidence"]
        print(f"    {i}. {c['name']:28s} {conf:5.1f}%  [{readiness_label(conf, c['run']['errors'])}]")
    if not ranked:
        print("    (no candidates ran — check provider availability above)")
    print(f"{'=' * 68}\n")


def write_markdown(report: dict, path: Path) -> None:
    b = report["baseline"]
    lines = [
        "# Darius A/B Model Parity — Cutover Readiness Report",
        "",
        f"- **Generated:** {report['generated_at']}",
        f"- **Mode:** {report['mode']}",
        (f"- **Baseline:** `{b['name']}` — overall {b['run']['overall']:.1%} "
        f"over {b['run']['case_count']} cases across {len(b['run']['lob_scores'])} LOBs"),
        f"- **Judge:** `{report['judge']}`",
        "",
        "## Cutover confidence rubric",
        "",
        "`confidence = 100 * (0.40·A + 0.30·B + 0.20·C + 0.10·D)`, capped by error rate.",
        "",
        "| Component | Weight | Meaning |",
        "|---|---|---|",
        "| A parity coverage | 40% | fraction of LOBs at/above the 0.85 gate AND within 3% of baseline |",
        "| B non-regression | 30% | fraction of cases that win or tie vs baseline (>5% margin = decisive) |",
        "| C absolute floor | 20% | candidate overall score ÷ 0.85 gate |",
        "| D sample sufficiency | 10% | ramps to full credit at 200 golden cases |",
        "",
        "Labels: ≥96% CUTOVER-READY · ≥85% SHADOW-READY · ≥60% PROMISING · else NOT READY.",
        "",
        "## Results",
        "",
        "| Candidate | Overall | Δ vs base | Win/Tie/Loss | LOBs@parity | Confidence | Readiness |",
        "|---|---|---|---|---|---|---|",
    ]
    ranked = sorted(
        report["candidates"],
        key=lambda c: (c["status"] == "ran", c.get("parity", {}).get("cutover_confidence", -1)),
        reverse=True,
    )
    for c in ranked:
        if c["status"] != "ran":
            lines.append(f"| {c['name']} | — | — | — | — | — | SKIPPED ({c['reason']}) |")
            continue
        run, par = c["run"], c["parity"]
        conf = par["cutover_confidence"]
        lines.append(
            f"| {c['name']} | {run['overall']:.1%} | {par['overall_delta']:+.1%} | "
            f"{par['wins']}/{par['ties']}/{par['losses']} | "
            f"{par['lobs_at_parity']}/{par['lobs_total']} | {conf:.1f}% | "
            f"{readiness_label(conf, run['errors'])} |"
        )

    lines += ["", "## Per-LOB detail", ""]
    for c in ranked:
        if c["status"] != "ran":
            continue
        lines.append(f"### {c['name']}")
        lines.append("")
        lines.append("| LOB | Candidate | Baseline | Δ | At parity |")
        lines.append("|---|---|---|---|---|")
        for lob, ld in sorted(c["parity"]["lob_delta"].items()):
            lines.append(
                f"| {lob} | {ld['candidate']:.1%} | {ld['baseline']:.1%} | "
                f"{ld['delta']:+.1%} | {'yes' if ld['at_parity'] else 'no'} |"
            )
        lines.append("")

    lines += [
        "## What raises confidence toward 96%",
        "",
        ("1. **Resolve hardware (#71):** GPU/Apple-Silicon so 24B–72B run at usable latency; "
        "until then local candidates carry a latency penalty regardless of quality."),
        ("2. **Grow golden sets:** component D caps confidence on small sets. "
        f"Current run scored {b['run']['case_count']} cases; target 200+ weighted to revenue-critical flows."),
        ("3. **Close per-LOB gaps:** any LOB marked *not at parity* above is a targeted fix "
        "(prompt tuning, few-shot, or model choice) before cutover."),
        ("4. **Shadow-run:** route production to Claude but score the top candidate in parallel; "
        "confirm sustained parity + drift < 0.15 before flipping."),
        "",
    ]
    path.write_text("\n".join(lines))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Darius A/B model-parity eval")
    parser.add_argument("--lob", default=None, help="Run a single LOB folder only")
    parser.add_argument("--candidates", default=None,
                        help="Comma-separated candidate names to include (default: all)")
    parser.add_argument("--fast", action="store_true", help="Keyword-only scoring (no judge)")
    parser.add_argument("--mock", action="store_true",
                        help="No-network deterministic self-test")
    parser.add_argument("--timeout", type=int, default=180, help="Per-call timeout (s)")
    parser.add_argument("--output-dir", default=str(REPORTS_DIR))
    args = parser.parse_args()

    cfg = load_candidate_config()
    lob_cases = load_golden_sets(lob=args.lob)
    if not lob_cases:
        logger.error(f"No golden cases found under {GOLDEN_SETS_DIR}")
        return 1
    total_cases = sum(len(v) for v in lob_cases.values())
    logger.info(f"Loaded {total_cases} cases across {len(lob_cases)} LOBs")

    use_judge = not args.fast
    mode = "mock" if args.mock else ("keyword-only" if args.fast else "live+judge")

    # Build clients
    b = cfg["baseline"]
    baseline_client = ModelClient(b["name"], b["provider"], b["model"],
                                  timeout=args.timeout, mock=args.mock)
    j = cfg["judge"]
    judge_client = ModelClient("judge", j["provider"], j["model"],
                               timeout=args.timeout, mock=args.mock)

    wanted = set(args.candidates.split(",")) if args.candidates else None
    candidate_clients: list[ModelClient] = []
    for c in cfg["candidates"]:
        if wanted and c["name"] not in wanted:
            continue
        candidate_clients.append(
            ModelClient(c["name"], c["provider"], c["model"],
                        timeout=args.timeout, mock=args.mock)
        )

    # Baseline must be available or nothing is comparable.
    ok, reason = baseline_client.preflight()
    if not ok:
        logger.error(f"Baseline '{baseline_client.name}' unavailable: {reason}. "
                     f"Set ANTHROPIC_API_KEY or run with --mock.")
        return 2

    logger.info(f"Running baseline: {baseline_client.name}")
    baseline_run = run_model_over_cases(baseline_client, lob_cases, judge_client, use_judge)

    candidates_report = []
    for client in candidate_clients:
        ok, reason = client.preflight()
        if not ok:
            logger.warning(f"Candidate '{client.name}' skipped: {reason}")
            candidates_report.append({"name": client.name, "status": "skipped", "reason": reason})
            continue
        logger.info(f"Running candidate: {client.name}")
        run = run_model_over_cases(client, lob_cases, judge_client, use_judge)
        parity = compute_parity(baseline_run, run)
        candidates_report.append({
            "name": client.name, "status": "ran", "run": run, "parity": parity,
        })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "judge": f"{j['provider']}/{j['model']}",
        "baseline": {"name": baseline_client.name, "run": baseline_run},
        "candidates": candidates_report,
    }

    print_console_report(report)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"ab_report_{ts}.json"
    md_path = out_dir / f"ab_report_{ts}.md"
    json_path.write_text(json.dumps(report, indent=2))
    write_markdown(report, md_path)
    logger.info(f"Wrote {json_path}")
    logger.info(f"Wrote {md_path}")

    # Exit 0 if at least one candidate is shadow-ready+, else 0 anyway (report is
    # the deliverable, not a gate). Non-zero only on hard failure to run baseline.
    return 0


if __name__ == "__main__":
    sys.exit(main())
