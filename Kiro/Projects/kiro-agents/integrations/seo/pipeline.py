"""
SEO Auto-Ticket System — converts analysis findings into actionable tickets.

Flow:
  1. Reads new findings from seo_analysis (status='new')
  2. Generates specific task descriptions for each finding
  3. Creates /task-internal tickets via orchestrator/tickets.py
  4. Posts a weekly summary to Slack for CEO review
  5. Marks findings as 'ticketed'

Task routing:
  - Title/meta issues → SEO agent (frontend)
  - Content gaps / FAQ → SEO agent (frontend)
  - Technical issues → SRE agent
  - Link structure → SEO agent (frontend)
  - Position analysis → informational only (Slack summary)
"""
import os
import uuid
import json
import logging
import httpx
from integrations.seo.models import get_site, get_findings, update_finding_status

logger = logging.getLogger("seo.tickets")

_SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
_SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")

# Severity → priority mapping
_SEVERITY_TO_PRIORITY = {
    "critical": "urgent",
    "high": "high",
    "medium": "normal",
    "low": "low",
}

# Finding type → task template
_TASK_TEMPLATES = {
    "declining_page": (
        "SEO: Improve title tag and meta description for {page}. "
        "Current metrics: {impressions} impressions, {clicks} clicks, avg position {avg_position:.1f}. "
        "The page is visible in search but not getting clicks — make the title and description more compelling."
    ),
    "near_page_1": (
        "SEO: Push near-page-1 keywords to page 1. "
        "These keywords are at positions 11-20 — add internal links, "
        "improve content depth, and optimize heading structure for: {keyword_list}"
    ),
    "low_ctr": (
        "SEO: Fix low CTR on high-ranking pages. "
        "These queries rank in top 10 but have CTR below 3%. "
        "Rewrite title tags and meta descriptions to be more click-worthy: {query_list}"
    ),
    "faq_gap": (
        "SEO: Create FAQ content for unanswered search queries. "
        "Users are searching for these questions but we don't have dedicated content: {question_list}. "
        "Add an FAQ section or dedicated page addressing these queries."
    ),
    "position_decline": (
        "SEO: Investigate and fix keyword ranking drops. "
        "These keywords lost 5+ positions this week: {decline_list}. "
        "Check for content staleness, broken links, or competitor improvements."
    ),
    "position_improvement": None,  # Informational only — no ticket needed
}


def generate_tickets(domain: str = "melanin-tech.com") -> list[dict]:
    """
    Generate tickets from new SEO findings.

    Returns list of created ticket dicts.
    """
    site = get_site(domain)
    if not site:
        raise ValueError(f"Site '{domain}' not registered.")

    findings = get_findings(site["id"], status="new")
    if not findings:
        logger.info(f"No new SEO findings for {domain}")
        return []

    created_tickets = []

    for finding in findings:
        finding_type = finding["finding_type"]
        template = _TASK_TEMPLATES.get(finding_type)

        # Skip informational findings (no ticket needed)
        if template is None:
            update_finding_status(finding["id"], "acknowledged")
            continue

        # Build task description from template + finding data
        task_text = _build_task(template, finding)
        if not task_text:
            continue

        # Create the ticket
        priority = _SEVERITY_TO_PRIORITY.get(finding.get("severity", "medium"), "normal")
        callback_id = str(uuid.uuid4())

        try:
            from orchestrator.tickets import open_ticket
            ticket_id = open_ticket(
                client="melanin-tech-website",
                task=task_text,
                agent="FrontendAgent",  # SEO tasks route to frontend
                proposal=finding.get("description", ""),
                callback_id=callback_id,
                ticket_type="internal",
                priority=priority,
            )

            update_finding_status(finding["id"], "ticketed", ticket_id=str(ticket_id))

            created_tickets.append({
                "ticket_id": ticket_id,
                "finding_type": finding_type,
                "severity": finding.get("severity"),
                "title": finding.get("title"),
                "task": task_text[:200],
            })

            logger.info(f"Created ticket #{ticket_id} from SEO finding: {finding['title'][:80]}")

        except Exception as e:
            logger.error(f"Failed to create ticket for finding {finding['id']}: {e}")

    return created_tickets


def _build_task(template: str, finding: dict) -> str:
    """Build a task description from a template and finding data."""
    data = finding.get("data") or {}
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}

    try:
        # Build substitution values
        subs = {
            "page": data.get("page", "unknown page"),
            "impressions": data.get("impressions", 0),
            "clicks": data.get("clicks", 0),
            "avg_position": data.get("avg_position", 0),
        }

        # Build keyword/query lists for multi-item findings
        if "keywords" in data:
            subs["keyword_list"] = ", ".join(
                f'"{kw["keyword"]}" (pos {kw.get("position", "?")})'
                for kw in data["keywords"][:5]
            )
        if "queries" in data:
            subs["query_list"] = ", ".join(
                f'"{q["query"]}"' for q in data["queries"][:5]
            )
        if "questions" in data:
            subs["question_list"] = ", ".join(
                f'"{q["query"]}"' for q in data["questions"][:5]
            )
        if "decliners" in data:
            subs["decline_list"] = ", ".join(
                f'"{d["keyword"]}" ({d["previous"]}→{d["current"]})'
                for d in data["decliners"][:5]
            )

        return template.format(**subs)
    except (KeyError, TypeError) as e:
        logger.warning(f"Template formatting failed: {e}")
        return f"SEO improvement: {finding.get('title', 'Unknown finding')}"


def post_weekly_summary(domain: str = "melanin-tech.com") -> bool:
    """
    Post a Slack summary of the week's SEO findings and created tickets.
    Called at the end of the weekly pipeline run.
    """
    if not _SLACK_TOKEN or not _SLACK_CHANNEL:
        logger.warning("No Slack credentials — cannot post SEO summary")
        return False

    site = get_site(domain)
    if not site:
        return False

    # Get all findings from this run (ticketed + acknowledged)
    from integrations.seo.models import _get_conn
    from psycopg2.extras import RealDictCursor
    conn = _get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT finding_type, severity, title, status, ticket_id
               FROM seo_analysis
               WHERE site_id = %s AND created_at > NOW() - INTERVAL '1 day'
               ORDER BY severity DESC""",
            (site["id"],),
        )
        findings = [dict(r) for r in cur.fetchall()]

    if not findings:
        return False

    # Build Slack message
    ticketed = [f for f in findings if f["status"] == "ticketed"]
    informational = [f for f in findings if f["status"] == "acknowledged"]

    sections = []
    sections.append({
        "type": "header",
        "text": {"type": "plain_text", "text": f"📊 Weekly SEO Report — {domain}"},
    })

    # Summary stats
    severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢", "critical": "⚫"}
    summary_lines = [f"*{len(findings)} findings this week:*"]
    for f in findings[:8]:
        emoji = severity_emoji.get(f["severity"], "⚪")
        status = "🎫" if f["status"] == "ticketed" else "ℹ️"
        summary_lines.append(f"{emoji} {status} {f['title'][:80]}")

    sections.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "\n".join(summary_lines)},
    })

    if ticketed:
        sections.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"🎫 *{len(ticketed)} tickets created* — awaiting approval in `/tickets`"}],
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
                "text": f"📊 Weekly SEO Report: {len(findings)} findings for {domain}",
                "blocks": sections,
            },
            timeout=10,
        )
        logger.info(f"SEO summary posted to Slack: {len(findings)} findings")
        return True
    except Exception as e:
        logger.error(f"Failed to post SEO summary: {e}")
        return False


def run_full_pipeline(domain: str = "melanin-tech.com") -> dict:
    """
    Execute the complete SEO pipeline end-to-end.

    Steps:
      1. Collect GSC data
      2. Run keyword discovery
      3. Run SERP tracking
      4. Run analysis
      5. Generate tickets
      6. Post Slack summary

    Returns pipeline execution summary.
    """
    from integrations.seo.models import register_site
    from integrations.seo.gsc import GSCConnector
    from integrations.seo.keywords import KeywordResearcher
    from integrations.seo.serp import SERPTracker
    from integrations.seo.analysis import SEOAnalysisAgent

    results = {"domain": domain, "steps": {}}

    # Ensure site is registered
    register_site(domain)

    # Step 1: GSC data collection
    try:
        gsc = GSCConnector()
        rows = gsc.collect_weekly_data(domain)
        results["steps"]["gsc"] = {"status": "success", "rows": rows}
    except Exception as e:
        results["steps"]["gsc"] = {"status": "error", "error": str(e)}
        logger.error(f"GSC collection failed: {e}")

    # Step 2: Keyword discovery
    try:
        researcher = KeywordResearcher(domain)
        discovery = researcher.run_full_discovery()
        results["steps"]["keywords"] = {"status": "success", **discovery}
    except Exception as e:
        results["steps"]["keywords"] = {"status": "error", "error": str(e)}
        logger.error(f"Keyword discovery failed: {e}")

    # Step 3: SERP tracking
    try:
        tracker = SERPTracker(domain)
        serp_results = tracker.run_weekly_check()
        results["steps"]["serp"] = {"status": "success", **{k: v for k, v in serp_results.items() if k != "details"}}
    except Exception as e:
        results["steps"]["serp"] = {"status": "error", "error": str(e)}
        logger.error(f"SERP tracking failed: {e}")

    # Step 4: Analysis
    try:
        analyst = SEOAnalysisAgent(domain)
        findings = analyst.run_full_analysis()
        results["steps"]["analysis"] = {"status": "success", "findings": len(findings)}
    except Exception as e:
        results["steps"]["analysis"] = {"status": "error", "error": str(e)}
        logger.error(f"Analysis failed: {e}")

    # Step 5: Ticket generation
    try:
        tickets = generate_tickets(domain)
        results["steps"]["tickets"] = {"status": "success", "created": len(tickets)}
    except Exception as e:
        results["steps"]["tickets"] = {"status": "error", "error": str(e)}
        logger.error(f"Ticket generation failed: {e}")

    # Step 6: Slack summary
    try:
        posted = post_weekly_summary(domain)
        results["steps"]["slack"] = {"status": "success" if posted else "skipped"}
    except Exception as e:
        results["steps"]["slack"] = {"status": "error", "error": str(e)}

    return results
