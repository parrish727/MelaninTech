#!/usr/bin/env python3
"""
SEO Pipeline — Weekly Cron Runner

Runs every Sunday at 11pm ET via Docker container.
Executes the full pipeline: GSC → Keywords → SERP → Analysis → Tickets → Slack

Usage (manual):
    python3 scripts/seo_cron.py

Docker (scheduled via compose):
    Runs as a one-shot container triggered by the orchestrator watchdog.
"""
import sys
import json
import logging
from datetime import datetime

sys.path.insert(0, "/app")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("seo.cron")


def main():
    logger.info("=" * 60)
    logger.info("SEO Weekly Pipeline — Starting")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    from integrations.seo.pipeline import run_full_pipeline

    # Run for all registered active sites
    sites = ["melanin-tech.com", "orthoflowsolutions.com"]

    for domain in sites:
        logger.info(f"\n{'─' * 40}")
        logger.info(f"Processing: {domain}")
        logger.info(f"{'─' * 40}")

        results = run_full_pipeline(domain)

        for step, data in results.get("steps", {}).items():
            status = data.get("status", "unknown")
            emoji = "✅" if status == "success" else "⚠️" if status == "skipped" else "❌"
            detail = {k: v for k, v in data.items() if k != "status"}
            logger.info(f"  {emoji} {step}: {status} {detail if detail else ''}")

    logger.info("")
    logger.info("=" * 60)
    logger.info("All sites processed.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
