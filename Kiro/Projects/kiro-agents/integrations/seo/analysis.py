"""
SEO Analysis Agent — interprets collected data and identifies improvement opportunities.

Runs weekly after data collection. Uses Darius (Claude) to analyze patterns
and generate actionable recommendations.

Analysis types:
  1. Declining pages — pages losing position or CTR
  2. Near-page-1 keywords — positions 11-20 (quick wins)
  3. FAQ gaps — search queries with no matching content
  4. Internal link opportunities — orphaned pages or weak link structure
  5. CTA effectiveness — high impressions but low CTR (title/meta issues)
  6. Content freshness — pages not generating engagement
"""
import os
import json
import logging
from datetime import datetime
from integrations.seo.models import (
    get_site,
    get_gsc_data,
    get_keywords,
    get_findings,
    store_finding,
)
from integrations.seo.serp import SERPTracker

logger = logging.getLogger("seo.analysis")


class SEOAnalysisAgent:
    """Analyzes SEO data and produces actionable findings."""

    def __init__(self, domain: str = "melanin-tech.com"):
        self.domain = domain
        self.site = get_site(domain)
        if not self.site:
            raise ValueError(f"Site '{domain}' not registered.")
        self.site_id = self.site["id"]

    def run_full_analysis(self) -> list[dict]:
        """
        Run all analysis passes and store findings.
        Returns list of new findings.
        """
        findings = []

        logger.info(f"Running full SEO analysis for {self.domain}")

        findings.extend(self._analyze_declining_pages())
        findings.extend(self._analyze_near_page_1())
        findings.extend(self._analyze_low_ctr_high_impressions())
        findings.extend(self._analyze_faq_gaps())
        findings.extend(self._analyze_position_movers())

        logger.info(f"Analysis complete: {len(findings)} findings for {self.domain}")
        return findings

    def _analyze_declining_pages(self) -> list[dict]:
        """Find pages with declining positions or CTR."""
        findings = []
        gsc_data = get_gsc_data(self.site_id, limit=500, days_back=28)

        if not gsc_data:
            return findings

        # Group by page and track aggregate metrics
        page_metrics = {}
        for row in gsc_data:
            page = row.get("page", "")
            if not page:
                continue
            if page not in page_metrics:
                page_metrics[page] = {"clicks": 0, "impressions": 0, "positions": []}
            page_metrics[page]["clicks"] += row.get("clicks", 0)
            page_metrics[page]["impressions"] += row.get("impressions", 0)
            page_metrics[page]["positions"].append(row.get("position", 0))

        # Pages with high impressions but very low clicks = potential title/meta issue
        for page, metrics in page_metrics.items():
            if metrics["impressions"] > 50 and metrics["clicks"] < 3:
                avg_pos = sum(metrics["positions"]) / len(metrics["positions"]) if metrics["positions"] else 0
                finding = store_finding(
                    site_id=self.site_id,
                    finding_type="declining_page",
                    title=f"Page getting views but no clicks: {_short_path(page)}",
                    description=(
                        f"Page '{_short_path(page)}' has {metrics['impressions']} impressions "
                        f"but only {metrics['clicks']} clicks (avg position: {avg_pos:.1f}). "
                        f"Title tag and meta description likely need improvement."
                    ),
                    severity="high" if metrics["impressions"] > 200 else "medium",
                    data={"page": page, "impressions": metrics["impressions"], "clicks": metrics["clicks"], "avg_position": avg_pos},
                )
                findings.append(finding)

        return findings

    def _analyze_near_page_1(self) -> list[dict]:
        """Find keywords at positions 11-20 — quick wins to push to page 1."""
        findings = []
        keywords = get_keywords(self.site_id, active_only=True)

        near_page_1 = [
            kw for kw in keywords
            if kw.get("current_position") and 11 <= kw["current_position"] <= 20
        ]

        if near_page_1:
            # Group into a single finding with all near-page-1 keywords
            keyword_list = sorted(near_page_1, key=lambda x: x["current_position"])
            details = "\n".join(
                f"  • \"{kw['keyword']}\" at position {kw['current_position']:.0f} → {kw.get('target_page', 'unknown page')}"
                for kw in keyword_list[:15]
            )
            finding = store_finding(
                site_id=self.site_id,
                finding_type="near_page_1",
                title=f"{len(near_page_1)} keywords almost on page 1 (positions 11-20)",
                description=(
                    f"These keywords are close to page 1 — small content/link improvements could push them up:\n{details}"
                ),
                severity="high",
                data={"keywords": [{"keyword": kw["keyword"], "position": kw["current_position"], "page": kw.get("target_page")} for kw in keyword_list[:15]]},
            )
            findings.append(finding)

        return findings

    def _analyze_low_ctr_high_impressions(self) -> list[dict]:
        """Find queries with high impressions but below-average CTR."""
        findings = []
        gsc_data = get_gsc_data(self.site_id, limit=200, days_back=28)

        if not gsc_data:
            return findings

        # Find queries with good position but bad CTR
        bad_ctr = [
            row for row in gsc_data
            if row.get("impressions", 0) > 30
            and row.get("position", 0) <= 10
            and row.get("ctr", 0) < 0.03  # Less than 3% CTR in top 10 is bad
        ]

        if bad_ctr:
            sorted_bad = sorted(bad_ctr, key=lambda x: x.get("impressions", 0), reverse=True)[:10]
            details = "\n".join(
                f"  • \"{row['query']}\" — pos {row['position']:.1f}, {row['impressions']} impressions, CTR {row['ctr']*100:.1f}%"
                for row in sorted_bad
            )
            finding = store_finding(
                site_id=self.site_id,
                finding_type="low_ctr",
                title=f"{len(bad_ctr)} queries with poor CTR despite good ranking",
                description=(
                    f"These queries rank on page 1 but have CTR below 3% — title tags and meta descriptions need to be more compelling:\n{details}"
                ),
                severity="high",
                data={"queries": [{"query": r["query"], "position": r["position"], "impressions": r["impressions"], "ctr": r["ctr"]} for r in sorted_bad]},
            )
            findings.append(finding)

        return findings

    def _analyze_faq_gaps(self) -> list[dict]:
        """Find question-type queries we're not adequately addressing."""
        findings = []
        gsc_data = get_gsc_data(self.site_id, limit=500, days_back=28)

        if not gsc_data:
            return findings

        # Find question queries (how, what, why, can, etc.)
        question_keywords = ["how", "what", "why", "when", "where", "which", "can", "does", "is"]
        questions = [
            row for row in gsc_data
            if any(row.get("query", "").lower().startswith(q) for q in question_keywords)
            and row.get("position", 0) > 5  # We're not ranking well for these
            and row.get("impressions", 0) > 10
        ]

        if questions:
            sorted_q = sorted(questions, key=lambda x: x.get("impressions", 0), reverse=True)[:10]
            details = "\n".join(
                f"  • \"{row['query']}\" — pos {row['position']:.1f}, {row['impressions']} impressions"
                for row in sorted_q
            )
            finding = store_finding(
                site_id=self.site_id,
                finding_type="faq_gap",
                title=f"{len(questions)} FAQ-style queries without dedicated content",
                description=(
                    f"People are searching for these questions and we're not answering them well. "
                    f"Adding FAQ sections or dedicated pages would capture this traffic:\n{details}"
                ),
                severity="medium",
                data={"questions": [{"query": r["query"], "position": r["position"], "impressions": r["impressions"]} for r in sorted_q]},
            )
            findings.append(finding)

        return findings

    def _analyze_position_movers(self) -> list[dict]:
        """Report significant position changes (both up and down)."""
        findings = []

        try:
            tracker = SERPTracker(self.domain)
            decliners = tracker.get_movers(direction="down", min_change=5)
            improvers = tracker.get_movers(direction="up", min_change=5)
        except Exception as e:
            logger.error(f"Position mover analysis failed: {e}")
            return findings

        if decliners:
            details = "\n".join(
                f"  • \"{m['keyword']}\" dropped from {m['previous']} → {m['current']} (Δ{m['delta']})"
                for m in decliners[:10]
            )
            finding = store_finding(
                site_id=self.site_id,
                finding_type="position_decline",
                title=f"{len(decliners)} keywords with significant ranking drops",
                description=f"These keywords lost 5+ positions this week — investigate and fix:\n{details}",
                severity="high",
                data={"decliners": decliners[:10]},
            )
            findings.append(finding)

        if improvers:
            details = "\n".join(
                f"  • \"{m['keyword']}\" improved from {m['previous']} → {m['current']} (Δ+{m['delta']})"
                for m in improvers[:10]
            )
            finding = store_finding(
                site_id=self.site_id,
                finding_type="position_improvement",
                title=f"{len(improvers)} keywords with significant ranking improvements",
                description=f"These keywords gained 5+ positions — double down on what's working:\n{details}",
                severity="low",
                data={"improvers": improvers[:10]},
            )
            findings.append(finding)

        return findings


def _short_path(url: str) -> str:
    """Shorten a URL to just the path."""
    from urllib.parse import urlparse
    try:
        path = urlparse(url).path
        return path if path and path != "/" else url
    except Exception:
        return url
