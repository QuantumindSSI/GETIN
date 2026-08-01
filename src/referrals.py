import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

REFERRALS_FILE = "referrals.json"


def _load() -> Dict[str, Any]:
    try:
        with open(REFERRALS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"referrers": {}, "rewards": {}}


def _save(data: Dict[str, Any]) -> None:
    with open(REFERRALS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_referral(referrer_id: int, new_user_id: int, new_username: str = "") -> None:
    data = _load()
    rid = str(referrer_id)
    nid = str(new_user_id)

    if rid not in data["referrers"]:
        data["referrers"][rid] = {"total": 0, "referred_users": [], "earned_credits": 0}

    if nid not in data["referrers"][rid]["referred_users"]:
        data["referrers"][rid]["referred_users"].append(nid)
        data["referrers"][rid]["total"] = len(data["referrers"][rid]["referred_users"])
        data["referrers"][rid]["earned_credits"] += 1
        _save(data)


def get_referral_stats(user_id: int) -> Dict[str, Any]:
    data = _load()
    rid = str(user_id)
    return data.get("referrers", {}).get(rid, {"total": 0, "referred_users": [], "earned_credits": 0})


def get_referral_link(user_id: int) -> str:
    return f"https://t.me/Yieldabot?start=ref_{user_id}"


REFERRAL_REWARD_TEXT = (
    "Share GETIN with your network. Each new user who joins helps grow the community.\n"
    "Referred users are credited in your account for leaderboard purposes.\n"
    "Premium benefits are provided at the operator's discretion.\n\n"
    "Share your link: https://t.me/Yieldabot?start=ref_{user_id}\n\n"
    "Your stats: {total} referrals, {credits} credits earned.\n\n"
    "Note: Referral credits are community metrics only. No monetary value. "
    "Premium access is granted at operator discretion, not automatically."
)