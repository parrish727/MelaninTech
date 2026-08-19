"""Gmail Connector — read, send, label, search emails."""
import base64
from email.mime.text import MIMEText
from integrations import BaseConnector, IntegrationRegistry


@IntegrationRegistry.register
class GmailConnector(BaseConnector):
    name = "gmail"
    scopes = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"

    def _refresh_token(self):
        """Refresh Google OAuth token."""
        r = self._http.post("https://oauth2.googleapis.com/token", data={
            "client_id": self.credentials.get("client_id"),
            "client_secret": self.credentials.get("client_secret"),
            "refresh_token": self.credentials.get("refresh_token"),
            "grant_type": "refresh_token",
        })
        if r.status_code == 200:
            data = r.json()
            self.credentials["access_token"] = data["access_token"]
            self.credentials["expires_at"] = data.get("expires_in", 3600) + __import__("time").time()

    def health_check(self) -> bool:
        try:
            r = self._request("GET", f"{self.BASE_URL}/profile")
            return "emailAddress" in r
        except Exception:
            return False

    def list_actions(self) -> list[dict]:
        return [
            {"name": "gmail_read_inbox", "description": "Read recent emails from inbox", "params": ["max_results", "query"]},
            {"name": "gmail_send", "description": "Send an email", "params": ["to", "subject", "body"]},
            {"name": "gmail_search", "description": "Search emails by query", "params": ["query", "max_results"]},
            {"name": "gmail_label", "description": "Add label to a message", "params": ["message_id", "label"]},
        ]

    def read_inbox(self, max_results: int = 10, query: str = "") -> list[dict]:
        """Read recent emails."""
        params = {"maxResults": max_results, "labelIds": "INBOX"}
        if query:
            params["q"] = query
        r = self._request("GET", f"{self.BASE_URL}/messages", params=params)
        messages = []
        for msg in r.get("messages", [])[:max_results]:
            detail = self._request("GET", f"{self.BASE_URL}/messages/{msg['id']}", params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]})
            headers = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            messages.append({
                "id": msg["id"],
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", ""),
                "date": headers.get("Date", ""),
                "snippet": detail.get("snippet", ""),
            })
        return messages

    def send(self, to: str, subject: str, body: str) -> dict:
        """Send an email."""
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        r = self._request("POST", f"{self.BASE_URL}/messages/send", json={"raw": raw})
        return {"id": r.get("id"), "status": "sent"}

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        """Search emails."""
        return self.read_inbox(max_results=max_results, query=query)

    def label(self, message_id: str, label: str) -> dict:
        """Add label to message."""
        r = self._request("POST", f"{self.BASE_URL}/messages/{message_id}/modify", json={"addLabelIds": [label]})
        return {"id": message_id, "labeled": label}
