"""
SERP Position Tracker — monitors live rankings for tracked keywords.

Uses SearXNG to check where our site ranks for each tracked keyword.
Runs weekly, stores position history for trend analysis.

Detects:
  - Position improvements (rising keywords)
  - Position drops (declining keywords)
  - New rankings (keywords we just started ranking for)
  - Lost rankings (keywords we fell off page 1+)
"""
import os
import time
import logging
import httpx
from integrations.seo.models import (
    get_site,
    get_keywords,
    store_serp_position,
    get_position_history,
)

logger = logging.getLogger("seo.serp")

_SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng:8080")

# Delay between queries to avoid rate-limiting SearXNG sources
_QUERY_DELAY = 3  # seconds


class SERPTracker:
    """Tracks SERP positions for a domain's keyword list."""

    def __init__(self, domain: str = "melanin-tech.com"):
        self.domain = domain
        self.site = get_site(domain)
        if not self.site:
            raise ValueError(f"Site '{domain}' not registered.")

    def check_position(self, keyword: str, max_results: int = 20) -> dict:
        """
        Check where our domain ranks for a keyword.

        Returns:
            {
                "keyword": str,
                "position": int or None (if not found in top N),
                "url": str or None,
                "snippet": str or None,
                "total_checked": int,
            }
        """
        try:
            r = httpx.get(
                f"{_SEARXNG_URL}/search",
                params={
                    "q": keyword,
                    "format": "json",
                    "engines": "google,duckduckgo,brave",
                    "pageno": 1,
                },
                timeout=15,
            )
            r.raise_for_status()
            results = r.json().get("results", [])[:max_results]
        except Exception as e:
            logger.error(f"SERP check failed for '{keyword}': {e}")
            return {
                "keyword": keyword,
                "position": None,
                "url": None,
                "snippet": None,
                "total_checked": 0,
            }

        # Find our domain in results
        for i, result in enumerate(results):
            url = result.get("url", "")
            if self.domain in url:
                return {
                    "keyword": keyword,
                    "position": i + 1,
                    "url": url,
                    "snippet": result.get("content", "")[:500],
                    "total_checked": len(results),
                }

        return {
            "keyword": keyword,
            "position": None,  # Not found in top N
            "url": None,
            "snippet": None,
            "total_checked": len(results),
        }

    def run_weekly_check(self) -> dict:
        """
        Check positions for all active keywords and store results.
        Compares with previous positions to detect changes.

        Returns summary of the check run.
        """
        site_id = self.site["id"]
        keywords = get_keywords(site_id, active_only=True)

        if not keywords:
            logger.warning(f"No active keywords to track for {self.domain}")
            return {"checked": 0, "ranked": 0, "improved": 0, "declined": 0}

        results = {
            "checked": 0,
            "ranked": 0,
            "not_found": 0,
            "improved": 0,
            "declined": 0,
            "new_rankings": 0,
            "lost_rankings": 0,
            "details": [],
        }

        for kw in keywords:
            keyword_id = kw["id"]
            keyword_text = kw["keyword"]
            prev_position = kw.get("current_position")

            # Check live SERP position
            check = self.check_position(keyword_text)
            new_position = check["position"]
            results["checked"] += 1

            # Store the result (even if not found — stores NULL position)
            position_to_store = new_position if new_position else 0
            store_serp_position(
                keyword_id=keyword_id,
                position=position_to_store,
                url=check["url"],
                snippet=check["snippet"],
            )

            # Classify the change
            change = _classify_change(prev_position, new_position)
            results[change] += 1

            # Track notable changes for summary
            if change in ("improved", "declined", "new_rankings", "lost_rankings"):
                results["details"].append({
                    "keyword": keyword_text,
                    "change": change,
                    "prev_position": prev_position,
                    "new_position": new_position,
                    "url": check["url"],
                })

            if new_position:
                results["ranked"] += 1
            else:
                results["not_found"] += 1

            # Rate limit
            time.sleep(_QUERY_DELAY)

        logger.info(
            f"SERP check complete for {self.domain}: "
            f"{results['checked']} checked, {results['ranked']} ranking, "
            f"{results['improved']} improved, {results['declined']} declined"
        )
        return results

    def get_movers(self, direction: str = "both", min_change: int = 3) -> list[dict]:
        """
        Get keywords with significant position changes.

        Args:
            direction: "up", "down", or "both"
            min_change: Minimum position change to report

        Returns list of keywords with their position delta.
        """
        site_id = self.site["id"]
        keywords = get_keywords(site_id, active_only=True)
        movers = []

        for kw in keywords:
            history = get_position_history(kw["id"], limit=2)
            if len(history) < 2:
                continue

            current = history[0]["position"]
            previous = history[1]["position"]

            if current == 0 or previous == 0:
                continue  # Skip if either check didn't find us

            delta = previous - current  # Positive = improved (lower rank number = better)

            if abs(delta) >= min_change:
                if direction == "up" and delta > 0:
                    movers.append({"keyword": kw["keyword"], "delta": delta, "current": current, "previous": previous})
                elif direction == "down" and delta < 0:
                    movers.append({"keyword": kw["keyword"], "delta": delta, "current": current, "previous": previous})
                elif direction == "both":
                    movers.append({"keyword": kw["keyword"], "delta": delta, "current": current, "previous": previous})

        return sorted(movers, key=lambda x: abs(x["delta"]), reverse=True)


def _classify_change(prev_position, new_position) -> str:
    """Classify a position change into a category."""
    if prev_position is None and new_position is not None:
        return "new_rankings"
    if prev_position is not None and new_position is None:
        return "lost_rankings"
    if prev_position is None and new_position is None:
        return "not_found"
    if new_position is not None and prev_position is not None:
        if new_position < prev_position:
            return "improved"
        elif new_position > prev_position:
            return "declined"
    return "ranked"
