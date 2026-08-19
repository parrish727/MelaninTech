# Step: Analyze

Analyze the collected data and identify the highest-impact improvement opportunity.

## Actions
1. Review the data from step 01-collect-data
2. Identify: declining pages, near-page-1 keywords, low CTR queries, FAQ gaps
3. Rank opportunities by potential impact (impressions × improvement potential)
4. Select the single highest-impact opportunity to fix

## Output Format
Return a JSON object with:
- `finding_type`: one of (declining_page, near_page_1, low_ctr, faq_gap)
- `title`: Human-readable finding title
- `description`: What's wrong and why it matters
- `data`: Supporting data (queries, pages, positions)
- `recommended_action`: Specific fix to implement
