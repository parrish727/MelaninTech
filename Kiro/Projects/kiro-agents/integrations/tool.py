"""
Integration Tool for Darius — wraps all connectors into a single tool interface.
Darius can call any connector action through this unified tool.
"""
import os
import json
from smolagents import Tool

# Import connectors (they auto-register)
from integrations import IntegrationRegistry
from integrations.gmail import GmailConnector
from integrations.google_calendar import GoogleCalendarConnector
from integrations.notion import NotionConnector


class IntegrationTool(Tool):
    name = "integrate"
    description = (
        "Execute actions on client business tools (Gmail, Calendar, Notion). "
        "Available connectors: gmail, google_calendar, notion. "
        "Actions: gmail_read_inbox, gmail_send, gmail_search, calendar_list_events, "
        "calendar_create_event, notion_create_page, notion_query_db, notion_search."
    )
    inputs = {
        "connector": {"type": "string", "description": "Connector name: gmail, google_calendar, notion"},
        "action": {"type": "string", "description": "Action to perform (e.g., gmail_send, calendar_create_event)"},
        "params": {"type": "object", "description": "Action parameters as a dict"},
        "client_id": {"type": "string", "description": "Client identifier for credential lookup", "nullable": True},
    }
    output_type = "string"

    def forward(self, connector: str, action: str, params: dict, client_id: str = "default") -> str:
        connector_cls = IntegrationRegistry.get(connector)
        if not connector_cls:
            return f"Unknown connector: {connector}. Available: {IntegrationRegistry.list_all()}"

        # Load credentials from environment or Vaultwarden
        creds = self._load_credentials(connector, client_id)
        if not creds:
            return f"No credentials found for {connector} (client: {client_id}). Set up OAuth first."

        instance = connector_cls(client_id=client_id, credentials=creds)

        # Route to the correct method
        action_map = {
            # Gmail
            "gmail_read_inbox": lambda: instance.read_inbox(**params),
            "gmail_send": lambda: instance.send(**params),
            "gmail_search": lambda: instance.search(**params),
            "gmail_label": lambda: instance.label(**params),
            # Calendar
            "calendar_list_events": lambda: instance.list_events(**params),
            "calendar_create_event": lambda: instance.create_event(**params),
            # Notion
            "notion_create_page": lambda: instance.create_page(**params),
            "notion_query_db": lambda: instance.query_database(**params),
            "notion_search": lambda: instance.search(**params),
        }

        handler = action_map.get(action)
        if not handler:
            return f"Unknown action: {action}. Available: {list(action_map.keys())}"

        try:
            result = handler()
            return json.dumps(result, indent=2, default=str)[:5000]
        except Exception as e:
            return f"Integration error ({connector}.{action}): {e}"

    def _load_credentials(self, connector: str, client_id: str) -> dict | None:
        """Load OAuth credentials. Priority: env var → file → None."""
        # Check env var (e.g., GMAIL_CREDENTIALS_default)
        env_key = f"{connector.upper()}_CREDENTIALS_{client_id}"
        env_val = os.environ.get(env_key)
        if env_val:
            try:
                return json.loads(env_val)
            except json.JSONDecodeError:
                pass

        # Check credentials file
        cred_path = f"/app/data/credentials/{client_id}/{connector}.json"
        if os.path.isfile(cred_path):
            with open(cred_path) as f:
                return json.load(f)

        return None
