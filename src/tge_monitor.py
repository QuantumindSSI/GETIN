import json
from datetime import datetime, timezone
from typing import List

from src.cryptorank_client import CryptoRankClient


class TGEMonitor:
    """Alert when a watched project gets a token listing or unlock event."""

    def __init__(
        self,
        client: CryptoRankClient,
        watchlist_path: str = "ranked_watchlist.json",
    ):
        self.client = client
        self.watchlist_path = watchlist_path
        self.alerted_path = "tge_alerted.json"

    def _load_projects(self) -> List[str]:
        """Read the ranked watchlist and return project names."""
        try:
            with open(self.watchlist_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return [p["project"] for p in data]
        except FileNotFoundError:
            return []

    def _load_alerted(self) -> List[str]:
        """Load the already-alerted project list."""
        try:
            with open(self.alerted_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            return []

    def _save_alerted(self, names: List[str]) -> None:
        """Persist the alerted project list."""
        with open(self.alerted_path, "w", encoding="utf-8") as fh:
            json.dump(names, fh)

    def check(self) -> List[str]:
        """Poll for token unlocks that match a watched project."""
        projects = self._load_projects()
        if not projects:
            return []
        lowered = {p.lower() for p in projects}
        alerted = set(self._load_alerted())
        try:
            unlocks = self.client.get_token_unlocks(page=1)
        except Exception:
            return []
        new_alerts: List[str] = []
        for item in unlocks.get("data", []):
            raw_name = item.get("name") or item.get("project", {}).get("name", "")
            name_lower = raw_name.lower()
            if name_lower in lowered and name_lower not in alerted:
                msg = f"TGE or unlock detected for {raw_name}. Review claim manually."
                new_alerts.append(msg)
                alerted.add(name_lower)
        self._save_alerted(list(alerted))
        return new_alerts