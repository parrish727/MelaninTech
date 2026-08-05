#!/usr/bin/env python3
"""
QA Eval Runner — Golden-set evaluation gate for Melanin Technologies.

Runs golden test cases against the agent pipeline and scores results using:
  1. Keyword matching (fast, deterministic)
  2. LLM-as-judge scoring (Claude Haiku, semantic correctness)

Pre-deploy gate: exits 1 if overall score < 85%.

Usage:
    # Run all golden sets
    python scripts/eval_runner.py

    # Run a specific category
    python scripts/eval_runner.py --category routing

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


def load_golden_sets(category: str = None) -> list[dict]:
    """Load test cases from YAML/JSON files."""
    cases = []

    try:
        import yaml
        loader = yaml.safe_load
    except ImportError:
        loader = None

    for f in sorted(GOLDEN_SETS_DIR.glob("*.yaml")) + sorted(GOLDEN_SETS_DIR.glob("*.yml")):
        if loader is None:
            logger.warning(f"PyYAML not installed, skipping {f.name}")
            continue
        with open(f) as fp:
            data = loader(fp)
            if isinstance(data, dict) and "cases" in data:
                cases.extend(data["cases"])
            elif isinstance(data, list):
                cases.extend(data)

    for f in GOLDEN_SETS_DIR.glob("*.json"):
        with open(f) as fp:
            data = json.load(fp)
            if isinstance(data, dict) and "cases" in data:
                cases.extend(data["cases"])
            elif isinstance(data, list):
                cases.extend(data)

    if category:
        cases = [c for c in cases if c.get("category") == category]

    return cases


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
        # Parse JSON from response
        data = json.loads(text)
        return {"score": float(data["score"]), "reasoning": data.get("reasoning", "")}
    except Exception as e:
        return {"score": None, "reasoning": f"judge error: {e}"}


def run_evaluation(cases: list[dict], use_judge: bool = True, threshold: float = None) -> dict:
    """Run all test cases and produce evaluation report."""
    threshold = threshold or EVAL_THRESHOLD
    results = []
    total_score = 0.0
    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"  QA Evaluation — {len(cases)} test cases")
    print(f"  Threshold: {threshold:.0%} | Judge: {'LLM' if use_judge else 'keyword-only'}")
    print(f"{'='*60}\n")

    for i, case in enumerate(cases, 1):
        case_id = case["id"]
        query = case["query"]
        project = case.get("project", "default")
        expected_behavior = case.get("expected_behavior", "")
        expected_keywords = case.get("expected_keywords", [])

        print(f"  [{i}/{len(cases)}] {case_id}...", end=" ", flush=True)

        # Run the query
        response = run_agent_query(query, project)

        if response.startswith("[ERROR"):
            results.append({
                "case_id": case_id,
                "status": "error",
                "score": 0.0,
                "response_preview": response[:200],
            })
            print("❌ ERROR")
            continue

        # Score: keyword matching
        kw_score = score_keyword(response, expected_keywords)

        # Score: LLM judge (if enabled)
        judge_result = {"score": None, "reasoning": "skipped"}
        if use_judge:
            judge_result = score_llm_judge(query, response, expected_behavior, expected_keywords)

        # Combined score: keyword 40%, judge 60% (or keyword 100% if no judge)
        if judge_result["score"] is not None:
            combined_score = (kw_score * 0.4) + (judge_result["score"] * 0.6)
        else:
            combined_score = kw_score

        total_score += combined_score
        passed = combined_score >= 0.6  # Per-case pass threshold

        results.append({
            "case_id": case_id,
            "category": case.get("category", ""),
            "status": "pass" if passed else "fail",
            "score": round(combined_score, 3),
            "keyword_score": round(kw_score, 3),
            "judge_score": judge_result["score"],
            "judge_reasoning": judge_result.get("reasoning", ""),
            "response_preview": response[:300],
        })

        status_icon = "✓" if passed else "✗"
        print(f"{status_icon} score={combined_score:.2f} (kw={kw_score:.2f}, judge={judge_result['score'] or 'n/a'})")

    elapsed = time.time() - start_time
    overall_score = total_score / len(results) if results else 0.0
    passed_count = sum(1 for r in results if r["status"] == "pass")
    failed_count = sum(1 for r in results if r["status"] == "fail")
    error_count = sum(1 for r in results if r["status"] == "error")

    report = {
        "status": "pass" if overall_score >= threshold else "fail",
        "overall_score": round(overall_score, 3),
        "threshold": threshold,
        "total_cases": len(results),
        "passed": passed_count,
        "failed": failed_count,
        "errors": error_count,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }

    # Print summary
    print(f"\n{'='*60}")
    print(f"  EVALUATION RESULT: {'✓ PASS' if report['status'] == 'pass' else '✗ FAIL'}")
    print(f"  Score: {overall_score:.1%} (threshold: {threshold:.0%})")
    print(f"  Cases: {passed_count} passed, {failed_count} failed, {error_count} errors")
    print(f"  Time: {elapsed:.1f}s")
    print(f"{'='*60}")

    if failed_count > 0:
        print(f"\n  Failed cases:")
        for r in results:
            if r["status"] == "fail":
                print(f"    ✗ {r['case_id']} (score={r['score']:.2f}): {r.get('judge_reasoning', '')[:80]}")

    return report


def main():
    parser = argparse.ArgumentParser(description="QA Eval Runner — golden-set evaluation gate")
    parser.add_argument("--category", type=str, default=None, help="Run only a specific category")
    parser.add_argument("--fast", action="store_true", help="Keyword-only scoring (no LLM judge)")
    parser.add_argument("--threshold", type=float, default=None, help="Pass threshold (default: 0.85)")
    parser.add_argument("--output", type=str, default=None, help="Save report to JSON file")
    args = parser.parse_args()

    cases = load_golden_sets(category=args.category)

    if not cases:
        logger.error("No golden test cases found in eval/golden_sets/")
        sys.exit(1)

    report = run_evaluation(
        cases,
        use_judge=not args.fast,
        threshold=args.threshold,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report saved to {args.output}")

    # Exit code for CI gating
    sys.exit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
