import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.config_manager import load_yaml
from src.cryptorank_client import CryptoRankClient


def refresh_watchlist(
    client: CryptoRankClient,
    manual_path: str = "watchlist.yaml",
    output_path: str = "ranked_watchlist.json",
) -> None:
    """Pull fresh intelligence and rewrite the ranked watchlist."""
    manual: List[Dict[str, Any]] = load_yaml(manual_path) or []

    # Token-unlock data requires Pro tier; attempt gracefully.
    token_projects: set[str] = set()
    try:
        unlocks_data = client.get_token_unlocks(page=1)
        for item in unlocks_data.get("data", []):
            raw_name = item.get("name") or item.get("project", {}).get("name")
            if raw_name:
                token_projects.add(raw_name.lower())
    except Exception:
        pass

    # Funding data requires Advanced tier; attempt gracefully.
    funding_map: Dict[str, float] = {}
    try:
        page = 1
        while page <= 5:
            funds_data = client.get_funds(page=page)
            items = funds_data.get("data", [])
            if not items:
                break
            for item in items:
                name = item.get("name", "")
                if not name:
                    continue
                amount = item.get("raised") or 0
                funding_map[name.lower()] = float(amount) if amount else 0.0
            if not funds_data.get("meta", {}).get("hasNextPage"):
                break
            page += 1
    except Exception:
        pass

    output: List[Dict[str, Any]] = []
    for entry in manual:
        if not entry:
            continue
        name = entry.get("name", "")
        lowered = name.lower()
        if lowered in token_projects:
            continue
        signal = funding_map.get(lowered, 0.0)
        output.append(
            {
                "project": name,
                "funding_signal": signal,
                "actions": entry.get("actions", []),
                "frequency_days": entry.get("frequency_days", 1),
                "testnet_url": entry.get("testnet_url", ""),
                "priority_score": signal / 1e6 if signal else 0.5,
                "last_checked": datetime.now(timezone.utc).isoformat(),
            }
        )

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)