import json
from datetime import datetime, timezone
from typing import Any, Dict


class ActivityLogger:
    """Log every on-chain action to a local JSON Lines file."""

    def __init__(self, out_path: str = "activity_log.jsonl"):
        self.out_path = out_path

    def log(
        self, project: str, action: str, tx_hash: str, metadata: Dict[str, Any]
    ) -> None:
        """Append one structured record to the log file."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "project": project,
            "action": action,
            "tx_hash": tx_hash,
            "metadata": metadata,
        }
        with open(self.out_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
