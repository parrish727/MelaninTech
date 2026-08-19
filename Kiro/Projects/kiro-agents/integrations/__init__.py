"""
Integration Engine — Base connector class.
All connectors (Gmail, Notion, Calendar, CRM) inherit from this.
Handles: OAuth token management, rate limiting, error handling, retry.
"""
import os
import time
import json
import httpx
from typing import Any
from abc import ABC, abstractmethod


class BaseConnector(ABC):
    """Base class for all integration connectors."""

    name: str = "base"
    scopes: list[str] = []

    def __init__(self, client_id: str, credentials: dict):
        """
        Args:
            client_id: Unique client identifier (maps to Vaultwarden folder)
            credentials: OAuth tokens (access_token, refresh_token, expires_at)
        """
        self.client_id = client_id
        self.credentials = credentials
        self._http = httpx.Client(timeout=30)

    @property
    def access_token(self) -> str:
        if self._token_expired():
            self._refresh_token()
        return self.credentials.get("access_token", "")

    def _token_expired(self) -> bool:
        expires_at = self.credentials.get("expires_at", 0)
        return time.time() > expires_at - 60  # refresh 60s before expiry

    def _refresh_token(self):
        """Override per provider (Google, Microsoft, etc.)"""
        pass

    def _request(self, method: str, url: str, **kwargs) -> dict:
        """Make authenticated HTTP request with retry."""
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        kwargs["headers"] = headers

        for attempt in range(3):
            try:
                r = self._http.request(method, url, **kwargs)
                if r.status_code == 429:
                    # Rate limited — wait and retry
                    wait = int(r.headers.get("Retry-After", 5))
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                return r.json() if r.content else {}
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    self._refresh_token()
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    continue
                raise
        return {}

    @abstractmethod
    def health_check(self) -> bool:
        """Verify the connection is working."""
        ...

    @abstractmethod
    def list_actions(self) -> list[dict]:
        """Return available actions for this connector (for LLM tool definitions)."""
        ...


class IntegrationRegistry:
    """Central registry of all available connectors."""

    _connectors: dict[str, type[BaseConnector]] = {}

    @classmethod
    def register(cls, connector_class: type[BaseConnector]):
        cls._connectors[connector_class.name] = connector_class
        return connector_class

    @classmethod
    def get(cls, name: str) -> type[BaseConnector] | None:
        return cls._connectors.get(name)

    @classmethod
    def list_all(cls) -> list[str]:
        return list(cls._connectors.keys())

    @classmethod
    def get_all_actions(cls) -> list[dict]:
        """Get all available actions across all connectors (for Darius tool registry)."""
        actions = []
        for name, connector_cls in cls._connectors.items():
            # Instantiate with dummy creds to get action list
            try:
                instance = connector_cls.__new__(connector_cls)
                instance.name = connector_cls.name
                for action in instance.list_actions():
                    action["connector"] = name
                    actions.append(action)
            except Exception:
                pass
        return actions
