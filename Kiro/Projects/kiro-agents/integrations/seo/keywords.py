"""
Keyword Research Tool — discovers keywords and competitive intelligence via SearXNG.

No paid APIs. Uses the self-hosted SearXNG instance for:
  - Related keyword discovery (search suggest + related searches)
  - Competitor page analysis (who ranks for our target terms)
  - Content gap identification (queries where we don't appear in top 20)

Keyword categories:
  - brand: "melanin technologies", "melanin tech"
  - service: "custom software development charlotte", "ai consulting"
  - problem: "how to automate business processes", "best software agency"
  - competitor: terms competitors rank for that we don't
"""
import os
import json
import logging
import httpx
from integrations.seo.models import get_site, upsert_keyword, get_keywords

logger = logging.getLogger("seo.keywords")

_SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://searxng:8080")


class KeywordResearcher:
    """Discovers keywords and competitive intelligence via SearXNG."""

    def __init__(self, domain: str = "melanin-tech.com"):
        self.domain = domain
        self.site = get_site(domain)
        if not self.site:
            raise ValueError(f"Site '{domain}' not registered. Call register_site() first.")

    def _search(self, query: str, num_results: int = 10, engines: str = "google,duckduckgo,brave") -> list[dict]:
        """Execute a SearXNG search and return results."""
        try:
            r = httpx.get(
                f"{_SEARXNG_URL}/search",
                params={
                    "q": query,
                    "format": "json",
                    "engines": engines,
                    "pageno": 1,
                },
                timeout=15,
            )
            r.raise_for_status()
            return r.json().get("results", [])[:num_results]
        except Exception as e:
            logger.error(f"SearXNG search failed for '{query}': {e}")
            return []

    def _get_suggestions(self, seed_keyword: str) -> list[str]:
        """Get search suggestions/autocomplete for a keyword."""
        try:
            r = httpx.get(
                f"{_SEARXNG_URL}/autocompleter",
                params={"q": seed_keyword},
                timeout=10,
            )
            r.raise_for_status()
            suggestions = r.json()
            if isinstance(suggestions, list):
                # Some formats return list of strings, others list of dicts
                return [s if isinstance(s, str) else s.get("phrase", "") for s in suggestions[:20]]
            return []
        except Exception as e:
            logger.debug(f"Autocomplete failed for '{seed_keyword}': {e}")
            return []

    def discover_related_keywords(self, seed_keywords: list[str]) -> list[dict]:
        """
        Discover related keywords from a set of seed keywords.
        Uses autocomplete suggestions and search result patterns.

        Returns list of discovered keywords with metadata.
        """
        discovered = {}

        for seed in seed_keywords:
            # Get autocomplete suggestions
            suggestions = self._get_suggestions(seed)
            for suggestion in suggestions:
                if suggestion and suggestion != seed:
                    discovered[suggestion.lower()] = {
                        "keyword": suggestion.lower(),
                        "source": "suggest",
                        "seed": seed,
                    }

            # Expand with question variants
            for prefix in ["how to", "what is", "best", "why"]:
                question = f"{prefix} {seed}"
                q_suggestions = self._get_suggestions(question)
                for s in q_suggestions:
                    if s and s.lower() != question.lower():
                        discovered[s.lower()] = {
                            "keyword": s.lower(),
                            "source": "question_expand",
                            "seed": seed,
                        }

        logger.info(f"Discovered {len(discovered)} related keywords from {len(seed_keywords)} seeds")
        return list(discovered.values())

    def analyze_competitors(self, keywords: list[str], top_n: int = 5) -> list[dict]:
        """
        For each keyword, find which competitor pages rank in top positions.
        Returns competitor intelligence.
        """
        competitors = {}

        for keyword in keywords[:20]:  # Limit to avoid hammering SearXNG
            results = self._search(keyword, num_results=top_n)
            for i, result in enumerate(results):
                url = result.get("url", "")
                # Skip our own domain
                if self.domain in url:
                    continue

                domain = _extract_domain(url)
                if domain not in competitors:
                    competitors[domain] = {
                        "domain": domain,
                        "keywords_ranking": [],
                        "avg_position": 0,
                        "appearances": 0,
                    }
                competitors[domain]["keywords_ranking"].append({
                    "keyword": keyword,
                    "position": i + 1,
                    "url": url,
                    "title": result.get("title", ""),
                })
                competitors[domain]["appearances"] += 1

        # Calculate avg position
        for domain, data in competitors.items():
            positions = [k["position"] for k in data["keywords_ranking"]]
            data["avg_position"] = sum(positions) / len(positions) if positions else 0

        # Sort by frequency of appearance
        sorted_competitors = sorted(competitors.values(), key=lambda x: x["appearances"], reverse=True)
        logger.info(f"Found {len(sorted_competitors)} competing domains across {len(keywords)} keywords")
        return sorted_competitors[:10]

    def find_content_gaps(self, keywords: list[str]) -> list[dict]:
        """
        Find keywords where our site doesn't appear in the top 20 results.
        These are content gap opportunities.
        """
        gaps = []

        for keyword in keywords[:30]:  # Rate limit
            results = self._search(keyword, num_results=20)
            our_position = None

            for i, result in enumerate(results):
                if self.domain in result.get("url", ""):
                    our_position = i + 1
                    break

            if our_position is None:
                gaps.append({
                    "keyword": keyword,
                    "gap_type": "not_ranking",
                    "top_competitor": results[0].get("url", "") if results else "",
                    "top_title": results[0].get("title", "") if results else "",
                })
            elif our_position > 10:
                gaps.append({
                    "keyword": keyword,
                    "gap_type": "page_2_plus",
                    "current_position": our_position,
                    "our_url": next(
                        (r["url"] for r in results if self.domain in r.get("url", "")), ""
                    ),
                })

        logger.info(f"Found {len(gaps)} content gaps from {len(keywords)} keywords checked")
        return gaps

    def run_full_discovery(self, seed_keywords: list[str] = None) -> dict:
        """
        Run a full keyword discovery session.

        If no seeds provided, uses existing keywords from GSC data.

        Returns summary of discoveries.
        """
        site_id = self.site["id"]

        # Get seeds from existing keywords if not provided
        if not seed_keywords:
            existing = get_keywords(site_id)
            # Use top-performing keywords as seeds
            seed_keywords = [k["keyword"] for k in existing[:20]]

        if not seed_keywords:
            # Fallback to domain-based seeds
            seed_keywords = [
                "custom software development",
                "ai consulting",
                "technology consulting charlotte",
                "software agency",
                "infrastructure hosting",
            ]

        # 1. Discover related keywords
        related = self.discover_related_keywords(seed_keywords)

        # 2. Store discovered keywords
        new_count = 0
        for kw in related:
            upsert_keyword(
                site_id=site_id,
                keyword=kw["keyword"],
                source=kw["source"],
                category=_classify_keyword(kw["keyword"]),
            )
            new_count += 1

        # 3. Analyze competitors
        competitors = self.analyze_competitors(seed_keywords[:10])

        # 4. Find content gaps
        gaps = self.find_content_gaps(seed_keywords[:15])

        return {
            "seeds_used": len(seed_keywords),
            "keywords_discovered": new_count,
            "competitors_found": len(competitors),
            "content_gaps": len(gaps),
            "top_competitors": [c["domain"] for c in competitors[:5]],
            "gap_keywords": [g["keyword"] for g in gaps[:10]],
        }


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    from urllib.parse import urlparse
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url


def _classify_keyword(keyword: str) -> str:
    """Auto-classify a keyword into a category."""
    kw = keyword.lower()
    if any(t in kw for t in ["melanin", "kiro"]):
        return "brand"
    if any(t in kw for t in ["how to", "what is", "why", "can i", "should i"]):
        return "informational"
    if any(t in kw for t in ["best", "top", "vs", "compare", "review", "alternative"]):
        return "comparison"
    if any(t in kw for t in ["buy", "pricing", "cost", "hire", "agency", "company", "service"]):
        return "commercial"
    return "informational"
