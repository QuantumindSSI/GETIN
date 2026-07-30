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
    funds_data = client.get_funds(limit=200)
    unlocks_data = client.get_token_unlocks(limit=500)

    manual: List[Dict[str, Any]] = load_yaml(manual_path) or []

    token_projects: set[str] = set()
    for item in unlocks_data.get("data", []):
        raw_name = item.get("name") or item.get("project", {}).get("name")
        if raw_name:
            token_projects.add(raw_name.lower())

    funding_map: Dict[str, float] = {}
    for item in funds_data.get("data", []):
        project_block = item.get("project") or item
        name = project_block.get("name", "")
        if not name:
            continue
        amount = item.get("raised") or item.get("amount") or 0
        funding_map[name.lower()] = float(amount) if amount else 0.0

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
