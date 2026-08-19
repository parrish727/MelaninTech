"""
Google Search Console Connector — pulls query and page performance data.

Uses the same Google OAuth tokens as Gmail/Calendar.
Requires scope: https://www.googleapis.com/auth/webmasters.readonly

Data pulled:
  - Query performance (clicks, impressions, CTR, position)
  - Page performance (which pages rank for which queries)
  - 28-day rolling window (GSC standard)
"""
import os
import json
import time
import logging
import httpx
from datetime import datetime, timedelta
from integrations.seo.models import store_gsc_data, get_site, upsert_keyword

logger = logging.getLogger("seo.gsc")

_GSC_API_BASE = "https://searchconsole.googleapis.com/webmasters/v3"
_CREDS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials")

# GSC requires this scope (add to GOOGLE_SCOPES in auth_flow.py)
GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


class GSCConnector:
    """Google Search Console API connector."""

    def __init__(self, client_id: str = "melanin-tech"):
        self.client_id = client_id
        self._tokens = self._load_tokens()

    def _load_tokens(self) -> dict:
        """Load OAuth tokens from credentials directory."""
        # GSC uses the same Google tokens as Gmail
        token_path = os.path.join(_CREDS_DIR, self.client_id, "gmail.json")
        if not os.path.exists(token_path):
            raise FileNotFoundError(
                f"No Google tokens found at {token_path}. "
                f"Run: python3 integrations/auth_flow.py --provider google --client {self.client_id}"
            )
        with open(token_path) as f:
            return json.load(f)

    @property
    def access_token(self) -> str:
        """Get valid access token, refreshing if expired."""
        if time.time() > self._tokens.get("expires_at", 0) - 60:
            self._refresh()
        return self._tokens["access_token"]

    def _refresh(self):
        """Refresh the OAuth access token."""
        r = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": self._tokens["client_id"],
                "client_secret": self._tokens["client_secret"],
                "refresh_token": self._tokens["refresh_token"],
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        self._tokens["access_token"] = data["access_token"]
        self._tokens["expires_at"] = time.time() + data.get("expires_in", 3600)

        # Persist refreshed tokens
        token_path = os.path.join(_CREDS_DIR, self.client_id, "gmail.json")
        with open(token_path, "w") as f:
            json.dump(self._tokens, f, indent=2)

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make authenticated API request."""
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        kwargs["headers"] = headers

        r = httpx.request(method, f"{_GSC_API_BASE}{path}", timeout=30, **kwargs)

        if r.status_code == 401:
            self._refresh()
            headers["Authorization"] = f"Bearer {self.access_token}"
            r = httpx.request(method, f"{_GSC_API_BASE}{path}", timeout=30, headers=headers, **{k: v for k, v in kwargs.items() if k != "headers"})

        r.raise_for_status()
        return r.json() if r.content else {}

    def list_sites(self) -> list[dict]:
        """List all verified sites/properties in GSC."""
        data = self._request("GET", "/sites")
        return data.get("siteEntry", [])

    def query_analytics(
        self,
        site_url: str,
        start_date: str = None,
        end_date: str = None,
        dimensions: list[str] = None,
        row_limit: int = 1000,
        start_row: int = 0,
    ) -> list[dict]:
        """
        Query Search Analytics API.

        Args:
            site_url: The GSC property URL (e.g., "sc-domain:melanin-tech.com")
            start_date: YYYY-MM-DD (default: 28 days ago)
            end_date: YYYY-MM-DD (default: today)
            dimensions: List of dimensions (query, page, country, device, date)
            row_limit: Max rows to return (max 25000)
            start_row: Pagination offset

        Returns:
            List of row dicts with keys, clicks, impressions, ctr, position
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if not dimensions:
            dimensions = ["query", "page"]

        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions,
            "rowLimit": min(row_limit, 25000),
            "startRow": start_row,
        }

        # URL-encode the site URL for the path
        import urllib.parse
        encoded_site = urllib.parse.quote(site_url, safe="")

        data = self._request(
            "POST",
            f"/sites/{encoded_site}/searchAnalytics/query",
            json=body,
        )

        rows = []
        for row in data.get("rows", []):
            keys = row.get("keys", [])
            entry = {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0.0),
                "position": row.get("position", 0.0),
            }
            # Map keys to dimension names
            for i, dim in enumerate(dimensions):
                if i < len(keys):
                    entry[dim] = keys[i]
            rows.append(entry)

        return rows

    def collect_weekly_data(self, domain: str) -> int:
        """
        Collect the last 28 days of GSC data for a domain and store it.
        Also auto-discovers keywords from GSC queries.

        Returns: number of rows collected
        """
        site = get_site(domain)
        if not site:
            raise ValueError(f"Site '{domain}' not registered. Call register_site() first.")

        site_id = site["id"]
        gsc_property = site["gsc_property"]

        start_date = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d")
        end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        logger.info(f"Collecting GSC data for {domain} ({start_date} to {end_date})")

        # Pull query + page data (paginate if needed)
        all_rows = []
        start_row = 0
        while True:
            rows = self.query_analytics(
                site_url=gsc_property,
                start_date=start_date,
                end_date=end_date,
                dimensions=["query", "page"],
                row_limit=5000,
                start_row=start_row,
            )
            if not rows:
                break
            all_rows.extend(rows)
            start_row += len(rows)
            if len(rows) < 5000:
                break

        if all_rows:
            # Store raw GSC data
            store_gsc_data(site_id, all_rows, start_date, end_date)

            # Auto-discover keywords from GSC queries
            seen_keywords = set()
            for row in all_rows:
                query = row.get("query", "")
                if query and query not in seen_keywords:
                    seen_keywords.add(query)
                    upsert_keyword(
                        site_id=site_id,
                        keyword=query,
                        source="gsc",
                        current_position=row.get("position"),
                        target_page=row.get("page"),
                    )

            logger.info(f"Stored {len(all_rows)} GSC rows, discovered {len(seen_keywords)} keywords")

        return len(all_rows)

    def health_check(self) -> bool:
        """Verify GSC connection is working."""
        try:
            sites = self.list_sites()
            return len(sites) > 0
        except Exception as e:
            logger.error(f"GSC health check failed: {e}")
            return False
