# Step: Collect Data

Pull the latest SEO data from Google Search Console and SearXNG SERP tracking.

## Actions
1. Call `gateway("google.gsc_query", {"domain": "{{domain}}", "days_back": 28})` to get recent performance data
2. Load tracked keywords and their current positions
3. Return a summary of: total impressions, top queries, position changes

## Output Format
Return a JSON object with:
- `top_queries`: Top 10 queries by impressions
- `position_changes`: Keywords that moved significantly
- `total_impressions`: Total impressions in period
