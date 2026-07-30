import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from src.logger import ActivityLogger
from src.wallet_manager import WalletManager


class TaskScheduler:
    """Run actions for each project according to frequency and human-like delays."""

    def __init__(self, watchlist_path: str, logger: ActivityLogger):
        self.watchlist_path = watchlist_path
        self.logger = logger
        self.last_run_file = "last_run.json"

    def _load_watchlist(self) -> List[Dict[str, Any]]:
        """Load the ranked watchlist from disk."""
        with open(self.watchlist_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _load_last_runs(self) -> Dict[str, str]:
        """Load the last-run timestamps."""
        try:
            with open(self.last_run_file, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            return {}

    def _save_last_runs(self, data: Dict[str, str]) -> None:
        """Persist the last-run timestamps."""
        with open(self.last_run_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def _should_run(self, project: str, freq_days: int, last_runs: Dict[str, str]) -> bool:
        """Check if enough days passed since the last run."""
        last = last_runs.get(project)
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
        except Exception:
            return True
        return datetime.now(timezone.utc) >= last_dt + timedelta(days=freq_days)

    def run(self, wallet: WalletManager) -> None:
        """Execute the main loop over the watchlist."""
        watchlist = self._load_watchlist()
        last_runs = self._load_last_runs()
        for entry in watchlist:
            name = entry["project"]
            freq = entry.get("frequency_days", 1)
            if not self._should_run(name, freq, last_runs):
                continue
            for action in entry.get("actions", []):
                try:
                    # Real contract calls go through WalletManager.
                    tx_hash = wallet.execute(name, action)
                    self.logger.log(name, action, tx_hash or "0xunknown", {})
                    delay = random.randint(45, 180)
                    time.sleep(delay)
                except Exception as exc:
                    print(f"Action failed: {name}/{action} -> {exc}")
            last_runs[name] = datetime.now(timezone.utc).isoformat()
            self._save_last_runs(last_runs)
