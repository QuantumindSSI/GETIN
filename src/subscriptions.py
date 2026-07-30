import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SUBS_FILE = "subscribers.json"


def _load_subscribers() -> Dict[str, Any]:
    """Load subscriber data from disk."""
    try:
        with open(SUBS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {"users": {}, "free_limit": 3, "premium_price_usd": 9.99}


def _save_subscribers(data: Dict[str, Any]) -> None:
    """Persist subscriber data to disk."""
    with open(SUBS_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def get_tier(user_id: int, username: str = "") -> str:
    """Return 'free', 'premium', or 'admin' for a given user."""
    data = _load_subscribers()
    uid = str(user_id)
    if uid in data["users"]:
        return data["users"][uid].get("tier", "free")
    return "free"


def register_user(user_id: int, username: str = "") -> None:
    """Record a new user if not already known."""
    data = _load_subscribers()
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "username": username,
            "tier": "free",
            "joined": datetime.now(timezone.utc).isoformat(),
            "report_count": 0,
        }
        _save_subscribers(data)


def increment_counter(user_id: int) -> None:
    """Increment the usage counter for a free-tier user."""
    data = _load_subscribers()
    uid = str(user_id)
    if uid in data["users"]:
        data["users"][uid]["report_count"] = data["users"][uid].get("report_count", 0) + 1
        _save_subscribers(data)


def get_usage_count(user_id: int) -> int:
    """Return how many reports this user has consumed."""
    data = _load_subscribers()
    uid = str(user_id)
    return data.get("users", {}).get(uid, {}).get("report_count", 0)


def get_premium_price() -> float:
    """Return the current premium subscription price."""
    data = _load_subscribers()
    return data.get("premium_price_usd", 9.99)


def set_premium(user_id: int) -> None:
    """Upgrade a user to premium tier."""
    data = _load_subscribers()
    uid = str(user_id)
    if uid in data["users"]:
        data["users"][uid]["tier"] = "premium"
    else:
        data["users"][uid] = {
            "username": "",
            "tier": "premium",
            "joined": datetime.now(timezone.utc).isoformat(),
            "report_count": 0,
        }
    _save_subscribers(data)