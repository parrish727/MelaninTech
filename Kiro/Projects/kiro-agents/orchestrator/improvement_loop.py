"""
Self-Improvement Loop — connects SEO findings to the frontend agent with visual validation.

Flow:
  1. SEO finding arrives (from pipeline or manual /task-internal)
  2. Load design system manifest for consistency
  3. Dispatch to frontend agent with SEO context + design constraints
  4. Deploy code to preview environment (preview.melanin-tech.com)
  5. Screenshot before/after via Playwright MCP
  6. Run Lighthouse audit on preview
  7. Compare scores — reject if regression detected
  8. Post visual diff + scores to Slack for CEO approval
  9. On approval → deploy to production

This module is called by the orchestrator when an SEO-originated internal ticket is approved.
"""
import os
import json
import time
import logging
import httpx
from pathlib import Path

logger = logging.getLogger("improvement_loop")

_PLAYWRIGHT_URL = os.environ.get("PLAYWRIGHT_MCP_URL", "http://playwright-mcp:9001")
_FRONTEND_AGENT_URL = os.environ.get("FRONTEND_AGENT_URL", "http://frontend-agent:8000")
_SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
_SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")

_PRODUCTION_URL = "https://melanin-tech.com"
_PREVIEW_URL = "http://preview:3001"

_DESIGN_SYSTEM_PATH = "/app/melanin-tech-website/design-system.json"

# Lighthouse score thresholds — reject if any category drops below these
_SCORE_THRESHOLDS = {
    "performance": 70,
    "accessibility": 85,
    "seo": 80,
    "best-practices": 75,
}


def load_design_system() -> dict:
    """Load the design system manifest for the frontend agent."""
    try:
        with open(_DESIGN_SYSTEM_PATH) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load design system: {e}")
        return {}


def build_frontend_task(finding: dict, design_system: dict) -> str:
    """
    Build a rich task prompt for the frontend agent using SEO findings + design system.
    """
    finding_type = finding.get("finding_type", "unknown")
    title = finding.get("title", "")
    description = finding.get("description", "")
    data = finding.get("data", {})

    # Design system context
    colors = design_system.get("colors", {})
    typography = design_system.get("typography", {})
    patterns = design_system.get("patterns", {})

    design_context = (
        f"DESIGN SYSTEM CONSTRAINTS:\n"
        f"- Colors: Primary {colors.get('primary', {}).get('blue', '#3D5A99')}, "
        f"Accent {colors.get('accent', {}).get('gold', '#B5A84B')}, "
        f"Deep {colors.get('primary', {}).get('blue-deep', '#1E2E52')}\n"
        f"- Fonts: Headings=Syne (800), Body=Inter (300/400/600)\n"
        f"- Icons: lucide-react only\n"
        f"- Animation: framer-motion (fade-up on scroll, 0.6s)\n"
        f"- Buttons: btn-primary (gold bg, deep text) or btn-secondary (transparent, border)\n"
        f"- Layout: container-max (80rem), section-padding responsive\n"
    )

    # Build task based on finding type
    if finding_type == "low_ctr":
        queries = data.get("queries", [])
        query_list = ", ".join(f'"{q["query"]}"' for q in queries[:5])
        task = (
            f"SEO IMPROVEMENT: Fix low click-through rate on high-ranking pages.\n\n"
            f"PROBLEM: These queries rank in top 10 but have CTR below 3%: {query_list}\n"
            f"The title tags and meta descriptions need to be more compelling and action-oriented.\n\n"
            f"ACTIONS:\n"
            f"1. Update the page's metadata in layout.tsx or page.tsx\n"
            f"2. Ensure the H1 heading matches the primary keyword intent\n"
            f"3. Add a clear value proposition in the first viewport\n\n"
            f"{design_context}"
        )
    elif finding_type == "faq_gap":
        questions = data.get("questions", [])
        q_list = "\n".join(f'  - "{q["query"]}"' for q in questions[:8])
        task = (
            f"SEO IMPROVEMENT: Create FAQ content for unanswered search queries.\n\n"
            f"PROBLEM: Users search for these questions but we have no dedicated content:\n{q_list}\n\n"
            f"ACTIONS:\n"
            f"1. Create a FAQ section component or add to existing page\n"
            f"2. Use proper HTML semantics (details/summary or structured heading + answer)\n"
            f"3. Add FAQPage JSON-LD schema markup\n"
            f"4. Keep answers concise (2-3 sentences), direct, and authoritative\n\n"
            f"{design_context}"
        )
    elif finding_type == "near_page_1":
        keywords = data.get("keywords", [])
        kw_list = "\n".join(f'  - "{kw["keyword"]}" (pos {kw.get("position", "?")}) → {kw.get("page", "?")}' for kw in keywords[:8])
        task = (
            f"SEO IMPROVEMENT: Strengthen content for near-page-1 keywords.\n\n"
            f"PROBLEM: These keywords are positions 11-20 — small improvements push them to page 1:\n{kw_list}\n\n"
            f"ACTIONS:\n"
            f"1. Add internal links to the target pages from other relevant pages\n"
            f"2. Expand content depth on target pages (add subsections, examples)\n"
            f"3. Optimize heading hierarchy to include keyword variants\n"
            f"4. Ensure target pages have strong CTAs\n\n"
            f"{design_context}"
        )
    elif finding_type == "declining_page":
        page = data.get("page", "unknown")
        task = (
            f"SEO IMPROVEMENT: Fix underperforming page {page}.\n\n"
            f"PROBLEM: {description}\n\n"
            f"ACTIONS:\n"
            f"1. Rewrite the title tag to be more compelling (include primary keyword + value prop)\n"
            f"2. Update meta description with a clear CTA\n"
            f"3. Ensure the page has proper heading structure (H1 → H2 → H3)\n"
            f"4. Add or improve the above-the-fold content\n\n"
            f"{design_context}"
        )
    else:
        task = (
            f"SEO IMPROVEMENT: {title}\n\n"
            f"DETAILS: {description}\n\n"
            f"ACTIONS: Implement the improvement while maintaining design consistency.\n\n"
            f"{design_context}"
        )

    return task


def screenshot_before() -> dict | None:
    """Take baseline screenshots of production site."""
    try:
        r = httpx.post(
            f"{_PLAYWRIGHT_URL}/audit/visual",
            json={"url": _PRODUCTION_URL},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Baseline screenshot failed: {e}")
        return None


def screenshot_after() -> dict | None:
    """Take screenshots of preview deployment."""
    try:
        r = httpx.post(
            f"{_PLAYWRIGHT_URL}/audit/visual",
            json={"url": _PREVIEW_URL},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Preview screenshot failed: {e}")
        return None


def run_lighthouse(url: str = None) -> dict | None:
    """Run Lighthouse audit on the preview deployment."""
    target = url or _PREVIEW_URL
    try:
        r = httpx.post(
            f"{_PLAYWRIGHT_URL}/audit/lighthouse",
            json={"url": target, "categories": ["performance", "accessibility", "seo", "best-practices"]},
            timeout=180,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Lighthouse audit failed: {e}")
        return None


def check_regressions(lighthouse_result: dict) -> list[str]:
    """Check if Lighthouse scores dropped below thresholds."""
    regressions = []
    scores = lighthouse_result.get("scores", {})

    for category, threshold in _SCORE_THRESHOLDS.items():
        score_data = scores.get(category, {})
        score = score_data.get("score", 0)
        if score < threshold:
            regressions.append(
                f"{category}: {score}/100 (threshold: {threshold})"
            )

    return regressions


def visual_diff(before_path: str, after_path: str) -> dict | None:
    """Compare before/after screenshots for visual regression."""
    try:
        r = httpx.post(
            f"{_PLAYWRIGHT_URL}/diff",
            json={"baseline": before_path, "current": after_path},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Visual diff failed: {e}")
        return None


def post_improvement_summary(
    finding: dict,
    lighthouse: dict,
    regressions: list[str],
    diff_score: float = None,
    callback_id: str = None,
) -> bool:
    """Post improvement results to Slack for approval."""
    if not _SLACK_TOKEN or not _SLACK_CHANNEL:
        return False

    scores = lighthouse.get("scores", {})
    score_text = " | ".join(
        f"{cat}: {data.get('score', '?')}" for cat, data in scores.items()
    )

    status = "✅ Ready for review" if not regressions else "⚠️ Regressions detected"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🔄 Website Self-Improvement Complete"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Finding:* {finding.get('title', 'Unknown')[:100]}\n"
                    f"*Status:* {status}\n"
                    f"*Lighthouse:* {score_text}\n"
                    f"*Visual Diff:* {diff_score:.1f}% changed" if diff_score else ""
                ),
            },
        },
    ]

    if regressions:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "⚠️ *Regressions:*\n" + "\n".join(f"  • {r}" for r in regressions),
            },
        })

    # Add approval buttons
    if callback_id:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Deploy to Production"},
                    "style": "primary",
                    "action_id": "deploy_production",
                    "value": callback_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject Changes"},
                    "action_id": "reject",
                    "value": callback_id,
                },
            ],
        })

    try:
        httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {_SLACK_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "channel": _SLACK_CHANNEL,
                "text": f"🔄 Self-improvement complete: {finding.get('title', '')[:80]}",
                "blocks": blocks,
            },
            timeout=10,
        )
        return True
    except Exception as e:
        logger.error(f"Slack post failed: {e}")
        return False


def run_improvement_loop(finding: dict, callback_id: str = None) -> dict:
    """
    Execute the full self-improvement loop for an SEO finding.

    Steps:
      1. Load design system
      2. Screenshot production (before)
      3. Build enriched task for frontend agent
      4. Dispatch to frontend agent
      5. Deploy to preview (handled by deploy agent)
      6. Screenshot preview (after)
      7. Run Lighthouse on preview
      8. Check for regressions
      9. Post results to Slack
      10. Return results for orchestrator

    Returns dict with status, scores, regressions, proposal.
    """
    result = {
        "status": "started",
        "finding": finding.get("title"),
        "steps": {},
    }

    # 1. Load design system
    design_system = load_design_system()
    result["steps"]["design_system"] = "loaded" if design_system else "missing"

    # 2. Screenshot production (before)
    before = screenshot_before()
    result["steps"]["screenshot_before"] = "success" if before else "failed"

    # 3. Build enriched task
    task = build_frontend_task(finding, design_system)
    result["steps"]["task_built"] = True

    # 4. Dispatch to frontend agent
    try:
        r = httpx.post(
            f"{_FRONTEND_AGENT_URL}/task",
            json={"task": task, "project": "melanin-tech-website"},
            timeout=180,
        )
        r.raise_for_status()
        proposal = r.json()
        result["proposal"] = proposal.get("args", {}).get("proposal", "")[:5000]
        result["steps"]["frontend_agent"] = "success"
    except Exception as e:
        result["steps"]["frontend_agent"] = f"error: {e}"
        result["status"] = "failed"
        return result

    # 5. Deploy to preview (the orchestrator handles this via the deploy pipeline)
    # For now, we signal that the proposal is ready for preview deployment
    result["steps"]["preview_deploy"] = "pending_approval"

    # 6. Screenshot preview (after) — runs after preview is deployed
    # This is triggered by the orchestrator after preview deploy completes

    # 7. Run Lighthouse on preview
    lighthouse = run_lighthouse(_PREVIEW_URL)
    if lighthouse:
        result["lighthouse"] = lighthouse.get("scores", {})
        result["steps"]["lighthouse"] = "success"

        # 8. Check regressions
        regressions = check_regressions(lighthouse)
        result["regressions"] = regressions

        if regressions:
            result["status"] = "regressions_detected"
        else:
            result["status"] = "ready_for_approval"
    else:
        result["steps"]["lighthouse"] = "failed"
        result["status"] = "partial"

    # 9. Post to Slack
    if lighthouse:
        diff_score = None
        if before:
            after = screenshot_after()
            if after and before.get("desktop", {}).get("path"):
                diff_result = visual_diff(
                    before["desktop"]["path"],
                    after.get("desktop", {}).get("path", ""),
                )
                if diff_result:
                    diff_score = diff_result.get("diff_score_pct", 0)

        posted = post_improvement_summary(
            finding=finding,
            lighthouse=lighthouse,
            regressions=regressions if lighthouse else [],
            diff_score=diff_score,
            callback_id=callback_id,
        )
        result["steps"]["slack"] = "posted" if posted else "failed"

    return result


def run_visual_validation(url: str = None) -> dict:
    """
    Standalone visual validation — screenshot + lighthouse a URL.
    Useful for manual checks or post-deploy verification.
    """
    target = url or _PRODUCTION_URL

    result = {"url": target}

    # Screenshot all breakpoints
    try:
        r = httpx.post(
            f"{_PLAYWRIGHT_URL}/audit/visual",
            json={"url": target},
            timeout=60,
        )
        r.raise_for_status()
        result["screenshots"] = {k: v.get("path") for k, v in r.json().items()}
    except Exception as e:
        result["screenshots"] = f"error: {e}"

    # Lighthouse
    lighthouse = run_lighthouse(target)
    if lighthouse:
        result["lighthouse"] = lighthouse
    else:
        result["lighthouse"] = "failed"

    return result
