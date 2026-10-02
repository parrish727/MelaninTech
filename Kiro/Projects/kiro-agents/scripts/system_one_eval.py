#!/usr/bin/env python3
"""
System One Eval — typed-decision parity + calibration for the model migration.

Runs the System One golden set (eval/system_one_golden/*.yaml) through the Claude
baseline plus every A/B candidate (local Ollama + self-hosted LLMGateway), using each model as
the System One PROVIDER (via LiteLLMProvider.from_candidate). For each candidate it
scores, per decision shape and overall:

  - decision accuracy   — did the model's winner/value match ground_truth?
  - Brier score          — mean squared error of the probability assigned to the
                           correct answer (lower = better calibrated + accurate)
  - ECE (Expected Calibration Error) — gap between confidence and correctness,
                           bucketed over the winner probability (lower = better)

Why this matters: System One (Claim/Choice/Score) is the bounded, machine-consumed
judgement layer — exactly where open-weight models can most plausibly replace
Anthropic. Free-text A/B quality alone doesn't tell you whether a model makes the
same *typed decisions* with trustworthy probabilities. This runner does.

Runs fully offline with --mock (MockProvider + deterministic golden set) so the
pipeline is provable without keys or hardware.

Usage:
    python scripts/system_one_eval.py --mock
    python scripts/system_one_eval.py                 # needs ANTHROPIC_API_KEY (baseline)
    python scripts/system_one_eval.py --candidates qwen-2.5-72b-gateway,kimi-k2-gateway

Artifacts: eval/reports/system_one_report_<ts>.{json,md}
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from AI.darius.system_one import (
    Choice,
    Claim,
    LiteLLMProvider,
    MockProvider,
    Score,
    get_engine,
)
from AI.darius.system_one.types import SystemOneRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("system_one_eval")

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = ROOT / "eval" / "system_one_golden"
CANDIDATES_FILE = ROOT / "eval" / "ab_candidates.yaml"
REPORTS_DIR = ROOT / "eval" / "reports"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLMGATEWAY_URL = os.environ.get("LLMGATEWAY_URL", "http://llmgateway:4001/v1")
LLMGATEWAY_API_KEY = os.environ.get("LLMGATEWAY_API_KEY", "")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")

ECE_BUCKETS = 5


# ── YAML loading (reuse ab_eval's tolerant loader if present, else PyYAML) ─────
def _load_yaml(path: Path):
    try:
        import yaml
        with open(path) as fp:
            return yaml.safe_load(fp)
    except ModuleNotFoundError:
        # Reuse ab_eval's mini parser so we don't duplicate it.
        from scripts.ab_eval import _mini_yaml
        with open(path) as fp:
            return _mini_yaml(fp.read())


def load_golden() -> list[dict]:
    cases = []
    for f in sorted(GOLDEN_DIR.glob("*.yaml")) + sorted(GOLDEN_DIR.glob("*.yml")):
        data = _load_yaml(f)
        if isinstance(data, dict):
            lob = data.get("lob", f.stem)
            for c in data.get("cases", []):
                c.setdefault("lob", lob)
                cases.append(c)
    return cases


def load_candidates() -> dict:
    return _load_yaml(CANDIDATES_FILE)


# ── Build a typed question + ground-truth vector from a golden case ────────────
def build_question(case: dict):
    qtype = case["type"].lower()
    qid = case["id"]
    text = case["question"]
    if qtype == "claim":
        return Claim(qid, text)
    if qtype == "choice":
        return Choice(qid, text, tuple(case["options"]))
    if qtype == "score":
        return Score.from_labels(qid, text, list(case["levels"]))
    raise ValueError(f"unknown type {qtype} in case {qid}")


def truth_vector(case: dict, question) -> tuple[list[float], int]:
    """
    Return (onehot_truth_distribution, correct_index) for scoring.

    For Claim the 'distribution' is [P(true)] and correct index is 0 with target
    1.0 if ground_truth is True else 0.0 (handled specially by the scorer).
    """
    gt = case["ground_truth"]
    if isinstance(question, Claim):
        return ([1.0 if gt else 0.0], 0)
    if isinstance(question, Choice):
        idx = list(question.options).index(gt)
        vec = [0.0] * len(question.options)
        vec[idx] = 1.0
        return (vec, idx)
    if isinstance(question, Score):
        idx = int(gt)
        vec = [0.0] * len(question.levels)
        vec[idx] = 1.0
        return (vec, idx)
    raise TypeError(type(question))


# ── Per-case scoring ───────────────────────────────────────────────────────────
def score_case(result, case: dict, question) -> dict:
    """Compare a System One result to ground truth: accuracy, Brier, winner prob."""
    gt = case["ground_truth"]
    kind = case["type"].lower()

    if kind == "claim":
        p_true = result.probability
        correct = (result.value is bool(gt))
        # Brier for a binary event: (p - y)^2 with y in {0,1}
        y = 1.0 if gt else 0.0
        brier = (p_true - y) ** 2
        winner_conf = max(p_true, 1.0 - p_true)
        p_correct = p_true if gt else (1.0 - p_true)
    elif kind == "choice":
        correct = (result.winner == gt)
        probs = result.distribution
        # Brier = sum over options (p_i - y_i)^2
        brier = sum(
            (probs.get(opt, 0.0) - (1.0 if opt == gt else 0.0)) ** 2
            for opt in probs
        )
        winner_conf = probs[result.winner]
        p_correct = probs.get(gt, 0.0)
    elif kind == "score":
        correct = (result.winner_level == int(gt))
        dist = result.distribution  # {level_idx: prob}
        brier = sum(
            (dist.get(i, 0.0) - (1.0 if i == int(gt) else 0.0)) ** 2
            for i in dist
        )
        winner_conf = dist[result.winner_level]
        p_correct = dist.get(int(gt), 0.0)
    else:
        raise ValueError(kind)

    return {
        "id": case["id"],
        "lob": case.get("lob", "core"),
        "type": kind,
        "correct": bool(correct),
        "brier": round(brier, 4),
        "winner_confidence": round(winner_conf, 4),
        "p_correct": round(p_correct, 4),
    }


def expected_calibration_error(rows: list[dict], buckets: int = ECE_BUCKETS) -> float:
    """
    ECE over the winner confidence: partition cases into confidence buckets,
    compare mean confidence to empirical accuracy in each, weight by bucket size.
    """
    if not rows:
        return 0.0
    edges = [i / buckets for i in range(buckets + 1)]
    total = len(rows)
    ece = 0.0
    for b in range(buckets):
        lo, hi = edges[b], edges[b + 1]
        # last bucket is inclusive of 1.0
        in_b = [r for r in rows
                if (r["winner_confidence"] >= lo and
                    (r["winner_confidence"] < hi or (b == buckets - 1 and r["winner_confidence"] <= hi)))]
        if not in_b:
            continue
        avg_conf = sum(r["winner_confidence"] for r in in_b) / len(in_b)
        acc = sum(1 for r in in_b if r["correct"]) / len(in_b)
        ece += (len(in_b) / total) * abs(avg_conf - acc)
    return round(ece, 4)


# ── Run one model over the golden set ──────────────────────────────────────────
def run_model(provider, cases: list[dict]) -> dict:
    engine = get_engine(provider=provider)
    rows = []
    errors = 0
    for case in cases:
        q = build_question(case)
        try:
            resp = engine.judge(SystemOneRequest(state=case["state"], questions=(q,)))
            result = resp[q.id]
            rows.append(score_case(result, case, q))
        except Exception as e:
            errors += 1
            rows.append({
                "id": case["id"], "lob": case.get("lob", "core"), "type": case["type"],
                "correct": False, "brier": 1.0, "winner_confidence": 0.0,
                "p_correct": 0.0, "error": str(e),
            })

    n = len(rows)
    accuracy = sum(1 for r in rows if r["correct"]) / n if n else 0.0
    brier = sum(r["brier"] for r in rows) / n if n else 1.0
    ece = expected_calibration_error(rows)

    # Per-type breakdown
    by_type = {}
    for t in ("claim", "choice", "score"):
        trows = [r for r in rows if r["type"] == t]
        if trows:
            by_type[t] = {
                "n": len(trows),
                "accuracy": round(sum(1 for r in trows if r["correct"]) / len(trows), 4),
                "brier": round(sum(r["brier"] for r in trows) / len(trows), 4),
            }

    return {
        "n": n, "errors": errors,
        "accuracy": round(accuracy, 4),
        "brier": round(brier, 4),
        "ece": ece,
        "by_type": by_type,
        "rows": rows,
    }


# ── System One cutover confidence (typed-decision specific) ─────────────────────
def system_one_confidence(run: dict, baseline: dict) -> tuple[float, dict]:
    """
    Confidence that a candidate makes typed decisions as well as the baseline.

      A. accuracy parity (45%)  — candidate accuracy / baseline accuracy (capped 1)
      B. calibration (30%)      — 1 - min(1, candidate_ece / 0.25) (ECE<=0 => 1)
      C. absolute accuracy (15%)— candidate accuracy (raw)
      D. sample sufficiency(10%)— ramps to full at 100 typed cases

    Errors hard-cap confidence.
    """
    n = max(1, run["n"])
    base_acc = max(1e-9, baseline["accuracy"])
    a = min(1.0, run["accuracy"] / base_acc)
    b = 1.0 - min(1.0, run["ece"] / 0.25)
    c = run["accuracy"]
    d = min(1.0, n / 100.0)
    raw = 0.45 * a + 0.30 * b + 0.15 * c + 0.10 * d
    conf = round(raw * 100, 1)
    if run["errors"]:
        frac = run["errors"] / n
        if frac >= 0.5:
            conf = min(conf, 10.0)
        elif frac >= 0.2:
            conf = min(conf, 30.0)
    rubric = {
        "A_accuracy_parity": {"weight": 0.45, "value": round(a, 3),
                              "detail": f"acc {run['accuracy']:.2f} vs base {baseline['accuracy']:.2f}"},
        "B_calibration": {"weight": 0.30, "value": round(b, 3), "detail": f"ECE {run['ece']:.3f} (0 best)"},
        "C_absolute_accuracy": {"weight": 0.15, "value": round(c, 3)},
        "D_sample_sufficiency": {"weight": 0.10, "value": round(d, 3), "detail": f"{n} cases (full at 100)"},
        "errors": run["errors"],
        "formula": "100*(0.45*A+0.30*B+0.15*C+0.10*D), capped by error rate",
    }
    return conf, rubric


def readiness(conf: float, errors: int) -> str:
    if errors and conf <= 30:
        return "NOT MEASURABLE"
    if conf >= 96:
        return "CUTOVER-READY"
    if conf >= 85:
        return "SHADOW-READY"
    if conf >= 60:
        return "PROMISING"
    return "NOT READY"


# ── Provider construction with graceful skip ───────────────────────────────────
def make_provider(name, provider, model, mock: bool, timeout: int):
    if mock:
        return MockProvider(), "ok"
    if provider == "anthropic" and not ANTHROPIC_API_KEY:
        return None, "ANTHROPIC_API_KEY not set"
    if provider == "llmgateway":
        if not LLMGATEWAY_API_KEY:
            return None, "LLMGATEWAY_API_KEY not set"
        import httpx
        base = LLMGATEWAY_URL.rstrip("/")
        base = base.removesuffix("/v1")
        try:
            if httpx.get(f"{base}/health", timeout=3).status_code != 200:
                return None, f"LLMGateway unreachable at {LLMGATEWAY_URL}"
        except Exception:
            return None, f"LLMGateway unreachable at {LLMGATEWAY_URL}"
    if provider == "ollama":
        import httpx
        try:
            if httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3).status_code != 200:
                return None, f"Ollama unreachable at {OLLAMA_URL}"
        except Exception:
            return None, f"Ollama unreachable at {OLLAMA_URL}"
    return LiteLLMProvider.from_candidate(provider, model, timeout=timeout), "ok"


# ── Reporting ───────────────────────────────────────────────────────────────────
def print_report(report: dict):
    b = report["baseline"]
    print(f"\n{'=' * 68}")
    print("  SYSTEM ONE — TYPED-DECISION PARITY & CALIBRATION")
    print(f"  Baseline: {b['name']}  acc={b['run']['accuracy']:.1%}  "
          f"Brier={b['run']['brier']:.3f}  ECE={b['run']['ece']:.3f}  n={b['run']['n']}")
    print(f"  Mode: {report['mode']}")
    print(f"{'=' * 68}")
    for c in report["candidates"]:
        if c["status"] != "ran":
            print(f"\n  ⏭  {c['name']:28s} SKIPPED — {c['reason']}")
            continue
        r = c["run"]
        conf = c["confidence"]
        d_acc = r["accuracy"] - b["run"]["accuracy"]
        print(f"\n  ── {c['name']} ──")
        print(f"     accuracy {r['accuracy']:.1%} (Δ {d_acc:+.1%})  Brier {r['brier']:.3f}  ECE {r['ece']:.3f}")
        bt = "  ".join(f"{t}:{v['accuracy']:.0%}({v['n']})" for t, v in r["by_type"].items())
        print(f"     by-type: {bt}")
        print(f"     >>> SYSTEM ONE CONFIDENCE: {conf:.1f}%  [{readiness(conf, r['errors'])}]")
    print(f"\n{'=' * 68}")
    ranked = sorted([c for c in report["candidates"] if c["status"] == "ran"],
                    key=lambda c: c["confidence"], reverse=True)
    print("  RANKING (typed-decision confidence)")
    for i, c in enumerate(ranked, 1):
        print(f"    {i}. {c['name']:28s} {c['confidence']:5.1f}%  [{readiness(c['confidence'], c['run']['errors'])}]")
    if not ranked:
        print("    (no candidates ran)")
    print(f"{'=' * 68}\n")


def write_markdown(report: dict, path: Path):
    b = report["baseline"]
    L = [
        "# System One — Typed-Decision Parity & Calibration",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Mode: {report['mode']}",
        (f"- Baseline: `{b['name']}` — accuracy {b['run']['accuracy']:.1%}, "
        f"Brier {b['run']['brier']:.3f}, ECE {b['run']['ece']:.3f}, n={b['run']['n']}"),
        "",
        ("Metrics: **accuracy** (winner matches ground truth), **Brier** (prob error, "
        "lower better), **ECE** (calibration gap, lower better)."),
        "",
        "| Candidate | Accuracy | Δ acc | Brier | ECE | Confidence | Readiness |",
        "|---|---|---|---|---|---|---|",
    ]
    ranked = sorted(report["candidates"],
                    key=lambda c: (c["status"] == "ran", c.get("confidence", -1)), reverse=True)
    for c in ranked:
        if c["status"] != "ran":
            L.append(f"| {c['name']} | — | — | — | — | — | SKIPPED ({c['reason']}) |")
            continue
        r = c["run"]
        L.append(f"| {c['name']} | {r['accuracy']:.1%} | {r['accuracy'] - b['run']['accuracy']:+.1%} | "
                 f"{r['brier']:.3f} | {r['ece']:.3f} | {c['confidence']:.1f}% | "
                 f"{readiness(c['confidence'], r['errors'])} |")
    L += ["", ("Confidence rubric: 100·(0.45·accuracy-parity + 0.30·calibration + "
          "0.15·absolute-accuracy + 0.10·sample-sufficiency), capped by error rate."),
          "Labels: ≥96% CUTOVER-READY · ≥85% SHADOW-READY · ≥60% PROMISING · else NOT READY.", ""]
    path.write_text("\n".join(L))


def main() -> int:
    ap = argparse.ArgumentParser(description="System One typed-decision eval")
    ap.add_argument("--candidates", default=None, help="Comma-separated candidate names")
    ap.add_argument("--mock", action="store_true", help="Offline deterministic self-test")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--output-dir", default=str(REPORTS_DIR))
    args = ap.parse_args()

    cases = load_golden()
    if not cases:
        logger.error(f"No golden cases under {GOLDEN_DIR}")
        return 1
    logger.info(f"Loaded {len(cases)} typed-decision golden cases")

    cfg = load_candidates()
    bspec = cfg["baseline"]
    mode = "mock" if args.mock else "live"

    b_provider, reason = make_provider(bspec["name"], bspec["provider"], bspec["model"], args.mock, args.timeout)
    if b_provider is None:
        logger.error(f"Baseline unavailable: {reason}. Set ANTHROPIC_API_KEY or use --mock.")
        return 2
    logger.info(f"Baseline: {bspec['name']}")
    baseline_run = run_model(b_provider, cases)

    wanted = set(args.candidates.split(",")) if args.candidates else None
    cand_reports = []
    for cand in cfg["candidates"]:
        if wanted and cand["name"] not in wanted:
            continue
        prov, reason = make_provider(cand["name"], cand["provider"], cand["model"], args.mock, args.timeout)
        if prov is None:
            logger.warning(f"Skip {cand['name']}: {reason}")
            cand_reports.append({"name": cand["name"], "status": "skipped", "reason": reason})
            continue
        logger.info(f"Candidate: {cand['name']}")
        run = run_model(prov, cases)
        conf, rubric = system_one_confidence(run, baseline_run)
        cand_reports.append({"name": cand["name"], "status": "ran", "run": run,
                             "confidence": conf, "rubric": rubric})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "baseline": {"name": bspec["name"], "run": baseline_run},
        "candidates": cand_reports,
    }
    print_report(report)

    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (out / f"system_one_report_{ts}.json").write_text(json.dumps(report, indent=2))
    write_markdown(report, out / f"system_one_report_{ts}.md")
    logger.info(f"Wrote {out}/system_one_report_{ts}.json and .md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
