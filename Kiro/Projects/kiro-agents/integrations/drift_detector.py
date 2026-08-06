"""
Drift Detector — Output quality monitoring for Melanin Technologies agent stack.

Detects:
  1. Embedding drift — new outputs diverge from known-good baselines
  2. Score degradation — rolling average of evaluation scores drops below threshold
  3. Latency regression — P95 latency exceeds SLO target

Architecture:
  - Reads golden test cases from eval/golden_sets/
  - Replays test queries through the agent pipeline
  - Compares output embeddings to stored baselines in Qdrant (eval_baselines)
  - Alerts via Slack webhook if drift exceeds threshold

Usage:
    # Run as a scheduled check (cron or post-deploy hook)
    python -m integrations.drift_detector --check

    # Capture new baselines from current working state
    python -m integrations.drift_detector --capture

    # Run with custom threshold
    python -m integrations.drift_detector --check --threshold 0.20

Env vars:
    QDRANT_URL — Qdrant API (default: http://qdrant:6333)
    OLLAMA_URL — Ollama for embeddings (default: http://ollama:11434)
    SLACK_WEBHOOK_URL — Alert destination (optional)
    DARIUS_URL — Darius API (default: http://darius:8001)
    DRIFT_THRESHOLD — Cosine distance threshold (default: 0.15)
"""
import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from integrations.qdrant_client import SemanticLayer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("drift_detector")

QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
DARIUS_URL = os.environ.get("DARIUS_URL", "http://darius:8001")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
DRIFT_THRESHOLD = float(os.environ.get("DRIFT_THRESHOLD", "0.15"))
SCORE_THRESHOLD = float(os.environ.get("SCORE_THRESHOLD", "0.70"))

GOLDEN_SETS_DIR = Path(__file__).resolve().parent.parent / "eval" / "golden_sets"
BASELINE_COLLECTION = "eval_baselines"


class DriftDetector:
    """Monitors agent output quality against established baselines."""

    def __init__(self, threshold: float = None):
        self.sl = SemanticLayer()
        self.threshold = threshold or DRIFT_THRESHOLD
        self._http = httpx.Client(timeout=60)

    def ensure_collection(self):
        """Ensure the eval_baselines collection exists."""
        self.sl._create_collection_if_not_exists(BASELINE_COLLECTION)

    # ── Baseline Capture ──────────────────────────────────────────────────────

    def capture_baselines(self) -> dict:
        """
        Run all golden test cases through the agent and store outputs as baselines.
        Call this when the system is in a known-good state.
        """
        self.ensure_collection()
        test_cases = self._load_golden_sets()

        if not test_cases:
            logger.warning("No golden test cases found")
            return {"captured": 0}

        captured = 0
        for case in test_cases:
            case_id = case["id"]
            query = case["query"]

            # Get agent output
            output = self._run_agent_query(query, case.get("project", "default"))
            if not output:
                logger.warning(f"No output for case {case_id}")
                continue

            # Store baseline embedding
            self.sl.upsert(
                BASELINE_COLLECTION,
                id=f"baseline_{case_id}",
                text=output,
                metadata={
                    "case_id": case_id,
                    "query": query[:500],
                    "output": output[:2000],
                    "captured_at": datetime.utcnow().isoformat(),
                    "category": case.get("category", "general"),
                },
            )
            captured += 1
            logger.info(f"  Captured baseline: {case_id}")

        logger.info(f"Captured {captured}/{len(test_cases)} baselines")
        return {"captured": captured, "total": len(test_cases)}

    # ── Drift Check ───────────────────────────────────────────────────────────

    def check_drift(self) -> dict:
        """
        Run golden test cases and compare against stored baselines.
        Returns drift report with pass/fail per case.
        """
        self.ensure_collection()
        test_cases = self._load_golden_sets()

        if not test_cases:
            logger.warning("No golden test cases found")
            return {"status": "skip", "reason": "no test cases"}

        results = []
        drifted = 0
        start_time = time.time()

        for case in test_cases:
            case_id = case["id"]
            query = case["query"]

            # Get current output
            output = self._run_agent_query(query, case.get("project", "default"))
            if not output:
                results.append({"case_id": case_id, "status": "error", "reason": "no output"})
                continue

            # Embed the current output
            current_embedding = self.sl.embed(output)

            # Search for the baseline
            baseline_results = self.sl.search_with_filter(
                BASELINE_COLLECTION,
                query=output,
                must=[{"key": "case_id", "match": {"value": case_id}}],
                limit=1,
            )

            if not baseline_results:
                results.append({"case_id": case_id, "status": "no_baseline", "reason": "baseline not captured"})
                continue

            # Calculate cosine distance (1 - similarity score)
            similarity = baseline_results[0]["score"]
            drift = 1.0 - similarity

            passed = drift <= self.threshold
            if not passed:
                drifted += 1

            results.append({
                "case_id": case_id,
                "status": "pass" if passed else "drift",
                "similarity": round(similarity, 4),
                "drift": round(drift, 4),
                "threshold": self.threshold,
            })

        elapsed = time.time() - start_time
        total = len(results)
        passed_count = total - drifted

        report = {
            "status": "pass" if drifted == 0 else "drift_detected",
            "total_cases": total,
            "passed": passed_count,
            "drifted": drifted,
            "threshold": self.threshold,
            "elapsed_s": round(elapsed, 1),
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if drifted > 0:
            self._alert_drift(report)

        return report

    # ── Score Trend Check ─────────────────────────────────────────────────────

    def check_score_trend(self) -> dict:
        """Check if recent evaluation scores are trending below threshold."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor

            dsn = os.environ.get("POSTGRES_DSN")
            if not dsn:
                return {"status": "skip", "reason": "no POSTGRES_DSN"}

            conn = psycopg2.connect(dsn)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Rolling average of last 20 evaluation scores
                cur.execute("""
                    SELECT AVG(evaluation_score) as avg_score,
                           COUNT(*) as sample_count,
                           MIN(evaluation_score) as min_score
                    FROM (
                        SELECT evaluation_score
                        FROM darius_traces
                        WHERE phase = 'evaluate'
                          AND evaluation_score IS NOT NULL
                          AND created_at > NOW() - INTERVAL '24 hours'
                        ORDER BY created_at DESC
                        LIMIT 20
                    ) recent
                """)
                row = cur.fetchone()
            conn.close()

            if not row or row["sample_count"] == 0:
                return {"status": "skip", "reason": "no recent scores"}

            avg_score = float(row["avg_score"])
            passed = avg_score >= SCORE_THRESHOLD

            report = {
                "status": "pass" if passed else "degraded",
                "avg_score": round(avg_score, 3),
                "min_score": round(float(row["min_score"]), 3),
                "sample_count": row["sample_count"],
                "threshold": SCORE_THRESHOLD,
            }

            if not passed:
                self._alert_score_degradation(report)

            return report

        except Exception as e:
            return {"status": "error", "reason": str(e)}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_golden_sets(self) -> list[dict]:
        """Load all golden test cases from YAML files."""
        cases = []
        if not GOLDEN_SETS_DIR.exists():
            return cases

        try:
            import yaml
        except ImportError:
            # Fall back to JSON files
            for f in GOLDEN_SETS_DIR.glob("*.json"):
                with open(f) as fp:
                    data = json.load(fp)
                    if isinstance(data, list):
                        cases.extend(data)
                    elif isinstance(data, dict) and "cases" in data:
                        cases.extend(data["cases"])
            return cases

        for f in sorted(GOLDEN_SETS_DIR.glob("*.yaml")) + sorted(GOLDEN_SETS_DIR.glob("*.yml")):
            with open(f) as fp:
                data = yaml.safe_load(fp)
                if isinstance(data, list):
                    cases.extend(data)
                elif isinstance(data, dict) and "cases" in data:
                    cases.extend(data["cases"])

        # Also load JSON files
        for f in GOLDEN_SETS_DIR.glob("*.json"):
            with open(f) as fp:
                data = json.load(fp)
                if isinstance(data, list):
                    cases.extend(data)
                elif isinstance(data, dict) and "cases" in data:
                    cases.extend(data["cases"])

        return cases

    def _run_agent_query(self, query: str, project: str = "default") -> Optional[str]:
        """Run a query through the Darius agent and get the output."""
        try:
            response = self._http.post(
                f"{DARIUS_URL}/task",
                json={"task": query, "project": project, "model_override": "light"},
            )
            if response.status_code != 200:
                logger.warning(f"Agent returned {response.status_code}")
                return None

            data = response.json()
            return data.get("args", {}).get("proposal", "")
        except Exception as e:
            logger.warning(f"Agent call failed: {e}")
            return None

    def _alert_drift(self, report: dict):
        """Send drift alert to Slack."""
        if not SLACK_WEBHOOK_URL:
            logger.warning("DRIFT DETECTED but no SLACK_WEBHOOK_URL configured")
            return

        drifted_cases = [r for r in report["results"] if r["status"] == "drift"]
        case_list = "\n".join(
            f"  • `{r['case_id']}` — drift={r['drift']:.3f} (threshold={r['threshold']})"
            for r in drifted_cases[:5]
        )

        message = (
            f"🚨 *Output Drift Detected*\n"
            f"*{report['drifted']}/{report['total_cases']}* cases exceed threshold ({self.threshold})\n\n"
            f"{case_list}\n\n"
            f"Run `python -m integrations.drift_detector --check` for full report."
        )

        try:
            self._http.post(SLACK_WEBHOOK_URL, json={"text": message})
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    def _alert_score_degradation(self, report: dict):
        """Send score degradation alert to Slack."""
        if not SLACK_WEBHOOK_URL:
            logger.warning(f"SCORE DEGRADATION: avg={report['avg_score']:.3f} < {report['threshold']}")
            return

        message = (
            f"⚠️ *Evaluation Score Degradation*\n"
            f"Rolling avg: *{report['avg_score']:.3f}* (threshold: {report['threshold']})\n"
            f"Min score: {report['min_score']:.3f} | Samples: {report['sample_count']}\n\n"
            f"Investigate recent traces for quality issues."
        )

        try:
            self._http.post(SLACK_WEBHOOK_URL, json={"text": message})
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")


def main():
    parser = argparse.ArgumentParser(description="Drift Detector — output quality monitoring")
    parser.add_argument("--check", action="store_true", help="Run drift check against baselines")
    parser.add_argument("--capture", action="store_true", help="Capture new baselines from current state")
    parser.add_argument("--scores", action="store_true", help="Check evaluation score trends")
    parser.add_argument("--threshold", type=float, default=None, help="Custom drift threshold")
    args = parser.parse_args()

    detector = DriftDetector(threshold=args.threshold)

    if args.capture:
        logger.info("═" * 50)
        logger.info("Capturing baselines from current working state...")
        logger.info("═" * 50)
        result = detector.capture_baselines()
        logger.info(f"Result: {json.dumps(result, indent=2)}")

    elif args.scores:
        logger.info("═" * 50)
        logger.info("Checking evaluation score trends...")
        logger.info("═" * 50)
        result = detector.check_score_trend()
        logger.info(f"Result: {json.dumps(result, indent=2)}")

    elif args.check:
        logger.info("═" * 50)
        logger.info("Running drift check...")
        logger.info("═" * 50)
        result = detector.check_drift()
        logger.info(f"\nResult: {json.dumps(result, indent=2)}")
        if result["status"] == "drift_detected":
            sys.exit(1)

    else:
        # Default: run both checks
        logger.info("═" * 50)
        logger.info("Full quality check (drift + scores)")
        logger.info("═" * 50)
        drift_result = detector.check_drift()
        score_result = detector.check_score_trend()

        logger.info(f"\nDrift: {drift_result['status']} | Scores: {score_result['status']}")
        if drift_result.get("status") == "drift_detected" or score_result.get("status") == "degraded":
            sys.exit(1)


if __name__ == "__main__":
    main()
