import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.chain_clients.ethereum_client import EthereumClient
from src.chain_clients.solana_client import SolanaClient
from src.config_manager import load_yaml
from src.safety_guard import SafetyGuard, SafetyError
from src.yield_protocols.aave_v3 import AaveV3Client
from src.yield_protocols.jupiter_solana import JupiterSwap
from src.yield_protocols.lido import LidoClient

HARVEST_LOG = "harvest_log.jsonl"
POSITIONS_FILE = "positions.json"


class YieldHarvester:
    """
    Auto-harvest accrued yield and optionally reinvest (compound).
    - Ethereum Aave: withdraw yield (aToken surplus)
    - Ethereum Lido: stETH rebases; harvest = swap excess stETH -> ETH
    - Solana JitoSOL: implicit rebase; harvest = swap yield portion -> SOL/USDC
    """

    def __init__(
        self,
        eth_rpc: Optional[str] = None,
        sol_rpc: Optional[str] = None,
        strategy_name: str = "conservative",
        wallet_name: str = "wallet_01",
        sol_wallet_name: Optional[str] = None,
        guard: Optional[SafetyGuard] = None,
    ):
        self.guard = guard or SafetyGuard()
        self.eth_client: Optional[EthereumClient] = None
        self.sol_client: Optional[SolanaClient] = None
        if eth_rpc:
            try:
                self.eth_client = EthereumClient(eth_rpc, wallet_name=wallet_name, guard=self.guard)
            except Exception as exc:
                print(f"Warning: Ethereum RPC connection failed: {exc}")
        if sol_rpc:
            try:
                sol_name = sol_wallet_name or wallet_name
                self.sol_client = SolanaClient(sol_rpc, wallet_name=sol_name, guard=self.guard)
            except Exception as exc:
                print(f"Warning: Solana RPC connection failed: {exc}")

        cfg = load_yaml("config/strategies.yaml")
        self.strategy = cfg.get("strategies", {}).get(strategy_name, {})
        self.protocols = cfg.get("protocols", {})
        self.scheduler: Optional[BackgroundScheduler] = None

    def _load_baseline(self) -> Dict[str, Any]:
        """Load last-known principal amounts to calculate yield accrued."""
        if not os.path.isfile(POSITIONS_FILE):
            return {}
        with open(POSITIONS_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save_baseline(self, data: Dict[str, Any]):
        with open(POSITIONS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _log(self, action: str, payload: Dict[str, Any]):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "payload": payload,
        }
        with open(HARVEST_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")

    def harvest_aave(self) -> Dict[str, Any]:
        """
        Compare current aToken balance to recorded principal.
        Withdraw the surplus yield to wallet.
        """
        if not self.eth_client:
            return {"ok": False, "error": "No Ethereum client"}

        baseline = self._load_baseline()
        results = []
        aave = AaveV3Client(self.eth_client, self.guard)

        for proto_name, cfg in self.protocols.items():
            if cfg.get("type") != "lending" or cfg.get("chain") != "ethereum":
                continue
            a_token = cfg.get("a_token")
            asset = cfg.get("asset")
            if not a_token:
                continue

            current = self.eth_client.get_token_balance(a_token)
            principal = baseline.get("ethereum", {}).get(proto_name, 0)
            yield_accrued = max(0, current - principal)

            if yield_accrued <= 0:
                results.append({"protocol": proto_name, "yield": 0, "harvested": False})
                continue

            print(f"  Aave yield on {asset}: {yield_accrued:.6f} (principal {principal:.6f})")
            try:
                # Withdraw only yield accrued
                tx = aave.withdraw(
                    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
                    if asset == "WETH"
                    else "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    yield_accrued,
                )
                results.append(
                    {"protocol": proto_name, "yield": yield_accrued, "harvested": True, "tx": tx}
                )
                self._log("harvest_aave", {"protocol": proto_name, "yield": yield_accrued, "tx": tx})
                # Update baseline after withdrawal
                new_principal = max(0, principal - yield_accrued)
                baseline.setdefault("ethereum", {})[proto_name] = new_principal
            except Exception as exc:
                results.append(
                    {"protocol": proto_name, "yield": yield_accrued, "harvested": False, "error": str(exc)}
                )

        self._save_baseline(baseline)
        return {"ok": True, "results": results}

    def harvest_lido(self) -> Dict[str, Any]:
        """
        stETH rebases automatically. To 'harvest' we would need to swap
        the excess stETH to ETH via DEX. For simplicity, this just reports
        the unrealized gain.
        """
        if not self.eth_client:
            return {"ok": False, "error": "No Ethereum client"}

        baseline = self._load_baseline()
        principal = baseline.get("ethereum", {}).get("lido_steth", 0)
        lido = LidoClient(self.eth_client, self.guard)
        current = lido.get_steth_balance()
        gain = max(0, current - principal)

        print(f"  Lido stETH: {current:.6f} (principal {principal:.6f}) unrealized gain {gain:.6f}")
        self._log("harvest_lido_report", {"principal": principal, "current": current, "gain": gain})

        if gain > 0.001:
            # Optionally swap via 1inch/Curve — not implemented to avoid complexity
            print("    Tip: Swap excess stETH to ETH on Curve/1inch to realize yield.")

        return {"ok": True, "gain": gain, "realized": False}

    def harvest_solana(self) -> Dict[str, Any]:
        """
        For Solana liquid staking, yield is implicit in token price.
        To harvest, swap a portion of the yield token back to SOL.
        We estimate yield by comparing token amount to recorded principal
        (this is approximate because price also fluctuates).
        """
        if not self.sol_client:
            return {"ok": False, "error": "No Solana client"}

        baseline = self._load_baseline()
        results = []
        jupiter = JupiterSwap(self.sol_client, self.guard)

        for proto_name, cfg in self.protocols.items():
            if cfg.get("chain") != "solana" or cfg.get("type") != "liquid_staking":
                continue
            mint = cfg.get("mint")
            if not mint:
                continue

            current = self.sol_client.get_token_balance(mint)
            principal = baseline.get("solana", {}).get(proto_name, 0)
            gain_tokens = max(0, current - principal)

            if gain_tokens < 0.001:
                results.append({"protocol": proto_name, "gain": 0, "harvested": False})
                continue

            print(f"  Solana {proto_name}: {current:.6f} tokens (principal {principal:.6f}) gain ~{gain_tokens:.6f}")
            try:
                # Swap yield portion back to SOL
                # Jupiter expects raw integer amounts
                # Note: decimals for JitoSOL is 9
                amount_raw = int(gain_tokens * 1e9)
                result = jupiter.swap_token_to_sol(mint, amount_raw)
                results.append(
                    {
                        "protocol": proto_name,
                        "gain_tokens": gain_tokens,
                        "harvested": True,
                        "tx": result["tx"],
                        "sol_received": result["output_sol"],
                    }
                )
                self._log("harvest_solana", {"protocol": proto_name, "gain": gain_tokens, "tx": result["tx"]})
                # Reset principal tracking (simplified)
                baseline.setdefault("solana", {})[proto_name] = current - gain_tokens
            except Exception as exc:
                results.append(
                    {"protocol": proto_name, "gain": gain_tokens, "harvested": False, "error": str(exc)}
                )

        self._save_baseline(baseline)
        return {"ok": True, "results": results}

    def run_harvest(self) -> Dict[str, Any]:
        """Run all harvest operations and return summary."""
        print("\n" + "=" * 60)
        print("YIELD HARVEST CYCLE")
        print("=" * 60)
        summary = {}
        summary["aave"] = self.harvest_aave()
        summary["lido"] = self.harvest_lido()
        summary["solana"] = self.harvest_solana()
        print("=" * 60)
        return summary

    def record_baselines(self):
        """
        Snapshot current position values as 'principal' so future
        harvests know how much is yield vs principal.
        Call this after every deposit.
        """
        baseline: Dict[str, Any] = {"ethereum": {}, "solana": {}}
        if self.eth_client:
            try:
                lido = LidoClient(self.eth_client, self.guard)
                baseline["ethereum"]["lido_steth"] = lido.get_steth_balance()
            except Exception:
                pass
            try:
                aave = AaveV3Client(self.eth_client, self.guard)
                # Track aToken balances as principal
                for proto_name, cfg in self.protocols.items():
                    if cfg.get("type") == "lending" and cfg.get("chain") == "ethereum":
                        a_tok = cfg.get("a_token")
                        if a_tok:
                            baseline["ethereum"][proto_name] = self.eth_client.get_token_balance(a_tok)
            except Exception:
                pass
        if self.sol_client:
            for proto_name, cfg in self.protocols.items():
                if cfg.get("chain") == "solana":
                    mint = cfg.get("mint")
                    if mint:
                        try:
                            baseline["solana"][proto_name] = self.sol_client.get_token_balance(mint)
                        except Exception:
                            pass
        self._save_baseline(baseline)
        print("  Baseline positions recorded for future harvest comparison.")
        return baseline

    def start_scheduler(self, interval_hours: int = 6):
        """
        Start a background APScheduler to run harvest every N hours.
        """
        if self.scheduler and self.scheduler.running:
            return
        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self.run_harvest,
            trigger=CronTrigger(hour=f"*/{interval_hours}"),
            id="yield_harvest",
            replace_existing=True,
        )
        self.scheduler.start()
        print(f"Harvest scheduler started (every {interval_hours} hours).")

    def stop_scheduler(self):
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            print("Harvest scheduler stopped.")
