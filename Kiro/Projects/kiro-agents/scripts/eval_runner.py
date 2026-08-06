#!/usr/bin/env python3
"""
QA Eval Runner — Golden-set evaluation gate for Melanin Technologies.

Runs golden test cases against the agent pipeline and scores results using:
  1. Keyword matching (fast, deterministic)
  2. LLM-as-judge scoring (Claude Haiku, semantic correctness)

Pre-deploy gate: exits 1 if overall score < 85%.

Structure:
  eval/golden_sets/
    core/           — routing, operations, governance
    orthoflow/      — OrthoFlow LOB-specific
    parcelpro/      — ParcelPro LOB-specific
    artistos/       — ArtistOS LOB-specific
    htc/            — HTC LOB-specific
    melanin-core/   — Melanin Tech internal

Usage:
    # Run all golden sets (all LOBs)
    python scripts/eval_runner.py

    # Run a specific LOB only
    python scripts/eval_runner.py --lob orthoflow

    # Run without LLM judge (keyword-only, faster)
    python scripts/eval_runner.py --fast

    # Set custom pass threshold
    python scripts/eval_runner.py --threshold 0.90

Env vars:
    DARIUS_URL — Darius API (default: http://darius:8001)
    ANTHROPIC_API_KEY — For LLM-as-judge scoring
    EVAL_THRESHOLD — Pass threshold (default: 0.85)
"""
import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("eval_runner")

DARIUS_URL = os.environ.get("DARIUS_URL", "http://darius:8001")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
EVAL_THRESHOLD = float(os.environ.get("EVAL_THRESHOLD", "0.85"))

GOLDEN_SETS_DIR = Path(__file__).resolve().parent.parent / "eval" / "golden_sets"

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


def load_golden_sets(lob: str = None) -> dict[str, list[dict]]:
    """
    Load test cases organized by LOB folder.
    Returns: {"core": [...cases], "orthoflow": [...cases], ...}
    """
    try:
        import yaml
        loader = yaml.safe_load
    except ImportError:
        loader = None

    lob_cases = {}

    # Get LOB folders
    if lob:
        folders = [GOLDEN_SETS_DIR / lob]
    else:
        folders = sorted([d for d in GOLDEN_SETS_DIR.iterdir() if d.is_dir()])

    for folder in folders:
        if not folder.exists():
            logger.warning(f"LOB folder not found: {folder}")
            continue

        lob_name = folder.name
        cases = []

        # Load YAML files
        for f in sorted(folder.glob("*.yaml")) + sorted(folder.glob("*.yml")):
            if loader is None:
                logger.warning(f"PyYAML not installed, skipping {f.name}")
                continue
            with open(f) as fp:
                data = loader(fp)
                if isinstance(data, dict):
                    file_project = data.get("project", lob_name)
                    file_lob = data.get("lob", lob_name)
                    for case in data.get("cases", []):
                        case.setdefault("project", file_project)
                        case.setdefault("lob", file_lob)
                        cases.append(case)
                elif isinstance(data, list):
                    cases.extend(data)

        # Load JSON files
        for f in folder.glob("*.json"):
            with open(f) as fp:
                data = json.load(fp)
                if isinstance(data, dict) and "cases" in data:
                    cases.extend(data["cases"])
                elif isinstance(data, list):
                    cases.extend(data)

        if cases:
            lob_cases[lob_name] = cases

    return lob_cases


def run_agent_query(query: str, project: str = "default") -> str:
    """Run a query through Darius and return the proposal text."""
    try:
        http = httpx.Client(timeout=90)
        response = http.post(
            f"{DARIUS_URL}/task",
            json={"task": query, "project": project, "model_override": "light"},
        )
        if response.status_code != 200:
            return f"[ERROR: HTTP {response.status_code}]"
        data = response.json()
        return data.get("args", {}).get("proposal", "[no proposal]")
    except Exception as e:
        return f"[ERROR: {e}]"


def score_keyword(response: str, expected_keywords: list[str]) -> float:
    """Score based on keyword presence (0.0-1.0)."""
    if not expected_keywords:
        return 1.0
    response_lower = response.lower()
    found = sum(1 for kw in expected_keywords if kw.lower() in response_lower)
    return found / len(expected_keywords)


def score_llm_judge(query: str, response: str, expected_behavior: str, expected_keywords: list[str]) -> dict:
    """Score using Claude Haiku as judge."""
    if not ANTHROPIC_API_KEY:
        return {"score": None, "reasoning": "no API key"}

    try:
        from litellm import completion

        prompt = JUDGE_PROMPT.format(
            query=query,
            expected_behavior=expected_behavior,
            expected_keywords=", ".join(expected_keywords),
            response=response[:3000],
        )

        result = completion(
            model="anthropic/claude-haiku-4-5-20251001",
            api_key=ANTHROPIC_API_KEY,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.0,
        )

        text = result.choices[0].message.content.strip()
        data = json.loads(text)
        return {"score": float(data["score"]), "reasoning": data.get("reasoning", "")}
    except Exception as e:
        return {"score": None, "reasoning": f"judge error: {e}"}


def run_evaluation(lob_cases: dict[str, list[dict]], use_judge: bool = True, threshold: float = None) -> dict:
    """Run all test cases organized by LOB and produce per-LOB scores."""
    threshold = threshold or EVAL_THRESHOLD
    start_time = time.time()

    total_cases = sum(len(cases) for cases in lob_cases.values())
    print(f"\n{'='*60}")
    print(f"  QA Evaluation — {total_cases} test cases across {len(lob_cases)} LOBs")
    print(f"  Threshold: {threshold:.0%} | Judge: {'LLM' if use_judge else 'keyword-only'}")
    print(f"{'='*60}")

    lob_reports = {}
    overall_scores = []
    case_index = 0

    for lob_name, cases in sorted(lob_cases.items()):
        print(f"\n  ┌── LOB: {lob_name} ({len(cases)} cases) ──")

        lob_results = []
        lob_total_score = 0.0

        for case in cases:
            case_index += 1
            case_id = case["id"]
            query = case["query"]
            project = case.get("project", "default")
            expected_behavior = case.get("expected_behavior", "")
            expected_keywords = case.get("expected_keywords", [])

            print(f"  │ [{case_index}/{total_cases}] {case_id}...", end=" ", flush=True)

            # Run the query
            response = run_agent_query(query, project)

            if response.startswith("[ERROR"):
                lob_results.append({
                    "case_id": case_id, "status": "error", "score": 0.0,
                    "response_preview": response[:200],
                })
                print("❌ ERROR")
                continue

            # Score
            kw_score = score_keyword(response, expected_keywords)
            judge_result = {"score": None, "reasoning": "skipped"}
            if use_judge:
                judge_result = score_llm_judge(query, response, expected_behavior, expected_keywords)

            if judge_result["score"] is not None:
                combined_score = (kw_score * 0.4) + (judge_result["score"] * 0.6)
            else:
                combined_score = kw_score

            lob_total_score += combined_score
            overall_scores.append(combined_score)
            passed = combined_score >= 0.6

            lob_results.append({
                "case_id": case_id,
                "status": "pass" if passed else "fail",
                "score": round(combined_score, 3),
                "keyword_score": round(kw_score, 3),
                "judge_score": judge_result["score"],
                "judge_reasoning": judge_result.get("reasoning", ""),
                "response_preview": response[:300],
            })

            status_icon = "✓" if passed else "✗"
            judge_display = f"{judge_result['score']:.2f}" if judge_result["score"] is not None else "n/a"
            print(f"{status_icon} score={combined_score:.2f} (kw={kw_score:.2f}, judge={judge_display})")

        # LOB summary
        lob_avg = lob_total_score / len(cases) if cases else 0.0
        lob_passed = sum(1 for r in lob_results if r["status"] == "pass")
        lob_status = "pass" if lob_avg >= threshold else "fail"

        print(f"  └── {lob_name}: {'✓ PASS' if lob_status == 'pass' else '✗ FAIL'} — {lob_avg:.1%} ({lob_passed}/{len(cases)} cases)")

        lob_reports[lob_name] = {
            "status": lob_status,
            "score": round(lob_avg, 3),
            "passed": lob_passed,
            "failed": len(cases) - lob_passed,
            "total": len(cases),
            "results": lob_results,
        }

    # Overall
    elapsed = time.time() - start_time
    overall_score = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0
    overall_status = "pass" if overall_score >= threshold else "fail"
    total_passed = sum(r["passed"] for r in lob_reports.values())
    total_failed = sum(r["failed"] for r in lob_reports.values())

    report = {
        "status": overall_status,
        "overall_score": round(overall_score, 3),
        "threshold": threshold,
        "total_cases": total_cases,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "elapsed_s": round(elapsed, 1),
        "lobs": lob_reports,
    }

    # Print final summary
    print(f"\n{'='*60}")
    print(f"  OVERALL: {'✓ PASS' if overall_status == 'pass' else '✗ FAIL'} — {overall_score:.1%}")
    print(f"  Threshold: {threshold:.0%} | Time: {elapsed:.1f}s")
    print(f"  Cases: {total_passed} passed, {total_failed} failed")
    print(f"{'─'*60}")
    print(f"  Per-LOB Scores:")
    for name, lr in sorted(lob_reports.items()):
        icon = "✓" if lr["status"] == "pass" else "✗"
        print(f"    {icon} {name:20s} {lr['score']:.1%}  ({lr['passed']}/{lr['total']})")
    print(f"{'='*60}")

    return report


def main():
    parser = argparse.ArgumentParser(description="QA Eval Runner — golden-set evaluation gate")
    parser.add_argument("--lob", type=str, default=None, help="Run only a specific LOB folder")
    parser.add_argument("--fast", action="store_true", help="Keyword-only scoring (no LLM judge)")
    parser.add_argument("--threshold", type=float, default=None, help="Pass threshold (default: 0.85)")
    parser.add_argument("--output", type=str, default=None, help="Save report to JSON file")
    args = parser.parse_args()

    lob_cases = load_golden_sets(lob=args.lob)

    if not lob_cases:
        logger.error(f"No golden test cases found in eval/golden_sets/")
        sys.exit(1)

    report = run_evaluation(
        lob_cases,
        use_judge=not args.fast,
        threshold=args.threshold,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report saved to {args.output}")

    sys.exit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
