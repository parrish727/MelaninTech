import json
import os
from datetime import datetime, timezone

CONTRACTS_PATH = os.path.join(os.path.dirname(__file__), "../config/support_contracts.json")


def _load() -> dict:
    if not os.path.exists(CONTRACTS_PATH):
        return {}
    with open(CONTRACTS_PATH) as f:
        return json.load(f)


def _save(data: dict):
    with open(CONTRACTS_PATH, "w") as f:
        json.dump(data, f, indent=2)


def check(client: str) -> dict:
    """Returns {"allowed": bool, "reason": str, "type": str}"""
    contracts = _load()
    contract = contracts.get(client)

    if not contract:
        return {"allowed": False, "reason": "No support contract found.", "type": None}

    kind = contract.get("type")  # "post_launch" or "usage"
    now = datetime.now(timezone.utc).isoformat()

    if kind == "post_launch":
        expires = contract.get("expires_at")
        if now > expires:
            return {"allowed": False, "reason": f"90-day post-launch support expired on {expires}.", "type": kind}
        return {"allowed": True, "reason": f"Active post-launch support until {expires}.", "type": kind}

    if kind == "usage":
        used = contract.get("tickets_used", 0)
        limit = contract.get("tickets_limit", 0)
        if used >= limit:
            return {"allowed": False, "reason": f"Usage limit reached ({used}/{limit} tickets).", "type": kind}
        return {"allowed": True, "reason": f"Usage support: {used}/{limit} tickets used.", "type": kind}

    return {"allowed": False, "reason": "Unknown contract type.", "type": None}


def consume_ticket(client: str):
    """Increments usage ticket count for usage-based contracts."""
    contracts = _load()
    if client in contracts and contracts[client].get("type") == "usage":
        contracts[client]["tickets_used"] = contracts[client].get("tickets_used", 0) + 1
        _save(contracts)


def register(client: str, kind: str, launch_date: str = None, tickets_limit: int = None):
    """Register or update a support contract."""
    contracts = _load()
    if kind == "post_launch":
        from datetime import timedelta
        launch = datetime.fromisoformat(launch_date)
        expires = (launch + timedelta(days=90)).isoformat()
        contracts[client] = {"type": "post_launch", "launch_date": launch_date, "expires_at": expires}
    elif kind == "usage":
        contracts[client] = {"type": "usage", "tickets_limit": tickets_limit, "tickets_used": 0}
    _save(contracts)
