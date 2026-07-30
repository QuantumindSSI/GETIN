import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.galxe_client import GalxeClient
from src.onchain_auto_farmer import OnchainAutoFarmer
from src.quest_engine import QuestTracker

AUTO_LOG_FILE = "auto_quest_log.json"


class AIQuestRunner:
    """
    Orchestrate automated quest completion across multiple platforms.
    Combines Galxe GraphQL, on-chain auto-farming, and curated quests.
    """

    def __init__(self, user_id: int):
        self.user_id = str(user_id)
        self.tracker = QuestTracker(user_id)
        self.farmer: Optional[OnchainAutoFarmer] = None
        self.galxe: Optional[GalxeClient] = None
        try:
            self.farmer = OnchainAutoFarmer()
        except Exception:
            pass
        try:
            self.galxe = GalxeClient()
        except Exception:
            pass

    def _log_action(self, action: str, result: Dict) -> None:
        """Append an action result to the auto-quest log."""
        entry = {
            "user_id": self.user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "result": result,
        }
        try:
            with open(AUTO_LOG_FILE, "r") as f:
                log = json.load(f)
        except FileNotFoundError:
            log = []
        log.append(entry)
        with open(AUTO_LOG_FILE, "w") as f:
            json.dump(log, f, indent=2)

    def run_testnet_rotation(self, actions: int = 3) -> Dict[str, Any]:
        """Run a testnet farming rotation across all chains."""
        if self.farmer is None:
            return {"ok": False, "error": "No private key configured. Set PRIVATE_KEY in .env."}

        results = {"monad": [], "berachain": [], "somnia": [], "total_txns": 0, "ok": True}
        for network in ["monad", "berachain", "somnia"]:
            try:
                net_results = self.farmer.run_rotation(network, actions)
                results[network] = net_results
                results["total_txns"] += sum(1 for r in net_results if r.get("ok"))
            except Exception as e:
                results[network] = [{"error": str(e), "ok": False}]

        self._log_action("testnet_rotation", {"networks": list(results.keys()), "total_txns": results["total_txns"]})
        return results

    def run_galxe_scan(self, space_id: str, address: str) -> Dict[str, Any]:
        """Scan a Galxe space for completable quests."""
        if self.galxe is None:
            return {"ok": False, "error": "Galxe access token not configured. Set GALXE_ACCESS_TOKEN in .env."}

        try:
            quests = self.galxe.list_active_quests(space_id)
            completable = self.galxe.find_automatable_quests(space_id, address)
            result = {
                "ok": True,
                "total_active_quests": len(quests),
                "automatable": len(completable),
                "quests": completable[:10],
            }
            self._log_action("galxe_scan", result)
            return result
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def run_curated_quest_batch(self) -> Dict[str, Any]:
        """Auto-complete all uncompleted curated quests."""
        quests = self.tracker.get_quests()
        completed = 0
        for q in quests:
            if q["completed"]:
                continue
            result = self.tracker.complete_quest(q["id"])
            if result["ok"]:
                completed += 1
                time.sleep(0.1)

        earnings = self.tracker.get_earnings()
        return {
            "ok": True,
            "quests_just_completed": completed,
            "total_completed": earnings["quests_completed"],
            "total_earned": earnings["total_usd"],
            "by_token": earnings.get("by_token", {}),
        }

    def run_full_cycle(self, galxe_space: str = "solana", evm_address: str = "") -> Dict[str, Any]:
        """Run a complete auto-quest cycle: testnets + Galxe + curated quests."""
        output = {"timestamp": datetime.now(timezone.utc).isoformat()}

        output["curated"] = self.run_curated_quest_batch()

        if self.farmer:
            output["testnets"] = self.run_testnet_rotation(3)

        if self.galxe and evm_address:
            output["galxe"] = self.run_galxe_scan(galxe_space, evm_address)

        return output