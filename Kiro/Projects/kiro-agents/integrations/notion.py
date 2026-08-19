"""Notion Connector — create pages, query databases, update properties."""
from integrations import BaseConnector, IntegrationRegistry


@IntegrationRegistry.register
class NotionConnector(BaseConnector):
    name = "notion"
    scopes = []  # Notion uses internal integration tokens, not OAuth scopes

    BASE_URL = "https://api.notion.com/v1"
    NOTION_VERSION = "2022-06-28"

    def _request(self, method: str, url: str, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.credentials.get('access_token', '')}"
        headers["Notion-Version"] = self.NOTION_VERSION
        headers["Content-Type"] = "application/json"
        kwargs["headers"] = headers
        r = self._http.request(method, url, **kwargs)
        r.raise_for_status()
        return r.json() if r.content else {}

    def health_check(self) -> bool:
        try:
            r = self._request("GET", f"{self.BASE_URL}/users/me")
            return "id" in r
        except Exception:
            return False

    def list_actions(self) -> list[dict]:
        return [
            {"name": "notion_create_page", "description": "Create a new page in a database", "params": ["database_id", "title", "properties"]},
            {"name": "notion_query_db", "description": "Query a Notion database", "params": ["database_id", "filter"]},
            {"name": "notion_update_page", "description": "Update page properties", "params": ["page_id", "properties"]},
            {"name": "notion_search", "description": "Search across all pages", "params": ["query"]},
        ]

    def create_page(self, database_id: str, title: str, properties: dict = None) -> dict:
        """Create a page in a Notion database."""
        page = {
            "parent": {"database_id": database_id},
            "properties": {"Name": {"title": [{"text": {"content": title}}]}},
        }
        if properties:
            page["properties"].update(properties)
        r = self._request("POST", f"{self.BASE_URL}/pages", json=page)
        return {"id": r.get("id"), "url": r.get("url")}

    def query_database(self, database_id: str, filter_obj: dict = None) -> list[dict]:
        """Query a Notion database."""
        body = {}
        if filter_obj:
            body["filter"] = filter_obj
        r = self._request("POST", f"{self.BASE_URL}/databases/{database_id}/query", json=body)
        return [{"id": p["id"], "properties": p.get("properties", {})} for p in r.get("results", [])]

    def search(self, query: str) -> list[dict]:
        """Search all pages."""
        r = self._request("POST", f"{self.BASE_URL}/search", json={"query": query})
        return [{"id": p["id"], "title": p.get("properties", {}).get("title", {}).get("title", [{}])[0].get("text", {}).get("content", "") if p.get("properties") else ""} for p in r.get("results", [])[:10]]
