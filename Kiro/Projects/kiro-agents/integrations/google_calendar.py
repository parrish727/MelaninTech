"""Google Calendar Connector — create, list, update events."""
from integrations import BaseConnector, IntegrationRegistry


@IntegrationRegistry.register
class GoogleCalendarConnector(BaseConnector):
    name = "google_calendar"
    scopes = ["https://www.googleapis.com/auth/calendar"]

    BASE_URL = "https://www.googleapis.com/calendar/v3"

    def _refresh_token(self):
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
            r = self._request("GET", f"{self.BASE_URL}/calendars/primary")
            return "id" in r
        except Exception:
            return False

    def list_actions(self) -> list[dict]:
        return [
            {"name": "calendar_list_events", "description": "List upcoming events", "params": ["max_results", "days_ahead"]},
            {"name": "calendar_create_event", "description": "Create a calendar event", "params": ["summary", "start", "end", "description", "attendees"]},
            {"name": "calendar_find_free_time", "description": "Find available time slots", "params": ["date", "duration_minutes"]},
        ]

    def list_events(self, max_results: int = 10, days_ahead: int = 7) -> list[dict]:
        """List upcoming events."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()
        r = self._request("GET", f"{self.BASE_URL}/calendars/primary/events", params={
            "timeMin": now, "timeMax": end, "maxResults": max_results, "singleEvents": True, "orderBy": "startTime"
        })
        return [{"summary": e.get("summary", ""), "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")), "end": e.get("end", {}).get("dateTime", "")} for e in r.get("items", [])]

    def create_event(self, summary: str, start: str, end: str, description: str = "", attendees: list[str] = None) -> dict:
        """Create a calendar event."""
        event = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start, "timeZone": "America/New_York"},
            "end": {"dateTime": end, "timeZone": "America/New_York"},
        }
        if attendees:
            event["attendees"] = [{"email": a} for a in attendees]
        r = self._request("POST", f"{self.BASE_URL}/calendars/primary/events", json=event)
        return {"id": r.get("id"), "link": r.get("htmlLink")}
