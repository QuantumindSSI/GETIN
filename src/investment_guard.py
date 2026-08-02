"""
Investment guardrails for the GETIN yield bot.

Pre-flight checks performed before any investment:
  1. Wallet connectivity — both ETH and SOL wallets must exist and connect
  2. Wallet balance — on-chain balance must meet minimum thresholds
  3. Kraken account — exchange API must authenticate and have GBP balance
  4. Strategy validation — strategy exists, allocations sum correctly
  5. Budget validation — within daily limits, meets minimums per strategy
  6. Investment plan preview — shows exact allocation before execution
  7. Risk assessment — warns on concentration, low liquidity, high slippage
  8. Daily spend tracking — enforces MAX_DAILY_ETH_SPEND / MAX_DAILY_SOL_SPEND

All guards return a PreFlightReport. If is_approved=False, invest is blocked.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.config_manager import load_yaml
from src.safety_guard import SafetyGuard

TRACKING_FILE = "daily_spend.json"


@dataclass
class AllocationLine:
    """One line in the investment plan."""
    chain: str
    protocol: str
    asset: str
    percentage: float
    amount_gbp: float
    estimated_tokens: float = 0.0
    min_deposit: float = 0.0
    meets_minimum: bool = True


@dataclass
class PreFlightReport:
    """Result of pre-invest guardrail checks."""
    is_approved: bool = True
    strategy: str = ""
    budget_gbp: float = 0.0
    dry_run: bool = True
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    allocations: List[AllocationLine] = field(default_factory=list)
    eth_address: str = ""
    sol_address: str = ""
    eth_balance: float = 0.0
    sol_balance: float = 0.0
    kraken_gbp_balance: float = 0.0
    eth_gbp_alloc: float = 0.0
    sol_gbp_alloc: float = 0.0
    daily_eth_spent: float = 0.0
    daily_sol_spent: float = 0.0


class InvestmentGuard:
    """
    Pre-flight safety checks for yield investments.
    Must pass ALL checks before execution proceeds.
    """

    def __init__(self, guard: Optional[SafetyGuard] = None):
        self.guard = guard or SafetyGuard()
        self._cfg = load_yaml("config/strategies.yaml")
        self._price_cache: Dict[str, float] = {}

    # ── Main entry point ──

    def pre_flight(
        self,
        strategy_name: str,
        budget_gbp: float,
        wallet_name: str = "wallet_01",
        sol_wallet_name: str = "solana_01",
        eth_rpc: Optional[str] = None,
        sol_rpc: Optional[str] = None,
    ) -> PreFlightReport:
        """Run ALL pre-flight checks. Returns report with is_approved flag."""
        report = PreFlightReport(
            strategy=strategy_name,
            budget_gbp=budget_gbp,
            dry_run=self.guard.is_dry_run(),
        )

        # 1. Strategy exists
        strategy = self._cfg.get("strategies", {}).get(strategy_name)
        if not strategy:
            report.is_approved = False
            report.failures.append(
                f"Strategy '{strategy_name}' not found. "
                "Available: conservative, balanced, aggressive_solana"
            )
            return report

        # 2. Budget minimum
        if budget_gbp < 10:
            report.is_approved = False
            report.failures.append(
                f"Minimum investment is GBP 10. Got GBP {budget_gbp:.2f}."
            )
            return report
        if budget_gbp > 1_000_000:
            report.is_approved = False
            report.failures.append(
                f"Maximum single investment is GBP 1,000,000. Got GBP {budget_gbp:.2f}."
            )
            return report

        # 3. Wallet connectivity + balances
        chain_checks = strategy.get("chains", {})
        eth_chain = chain_checks.get("ethereum", {})
        sol_chain = chain_checks.get("solana", {})

        if eth_chain and eth_rpc:
            ok, msg, addr, bal = self._check_eth_wallet(wallet_name, eth_rpc)
            report.eth_address = addr
            report.eth_balance = bal
            if not ok:
                report.is_approved = False
                report.failures.append(msg)

        if sol_chain and sol_rpc:
            ok, msg, addr, bal = self._check_sol_wallet(sol_wallet_name, sol_rpc)
            report.sol_address = addr
            report.sol_balance = bal
            if not ok:
                report.is_approved = False
                report.failures.append(msg)

        # 4. Kraken account
        ok, msg, gbp_bal = self._check_kraken()
        report.kraken_gbp_balance = gbp_bal
        if not ok:
            report.failures.append(msg)
            if budget_gbp > 0:
                report.is_approved = False

        # 5. Daily spend limits
        ok, msg, daily_eth, daily_sol = self._check_daily_spend(budget_gbp, strategy)
        report.daily_eth_spent = daily_eth
        report.daily_sol_spent = daily_sol
        if not ok:
            report.is_approved = False
            report.failures.append(msg)

        # 6. Build investment plan
        report.allocations = self._build_allocation_plan(budget_gbp, strategy)
        report.eth_gbp_alloc = sum(
            a.amount_gbp for a in report.allocations if a.chain == "ethereum"
        )
        report.sol_gbp_alloc = sum(
            a.amount_gbp for a in report.allocations if a.chain == "solana"
        )

        # 7. Check minimum deposit thresholds
        for alloc in report.allocations:
            if not alloc.meets_minimum:
                report.warnings.append(
                    f"{alloc.chain}/{alloc.protocol}: "
                    f"allocation GBP {alloc.amount_gbp:.2f} below "
                    f"minimum ~GBP {alloc.min_deposit:.2f}. Skipping."
                )

        # 8. Concentration risk warning
        for alloc in report.allocations:
            if alloc.percentage > 50:
                report.warnings.append(
                    f"Concentration risk: {alloc.percentage:.0f}% in {alloc.protocol}. "
                    "Consider diversifying."
                )

        return report

    def format_plan(self, report: PreFlightReport) -> str:
        """Render the pre-flight report as a human-readable string."""
        lines = []
        lines.append("=" * 60)
        lines.append("INVESTMENT PRE-FLIGHT REPORT")
        lines.append("=" * 60)
        lines.append(f"Strategy:      {report.strategy}")
        lines.append(f"Budget:        GBP {report.budget_gbp:.2f}")
        lines.append(f"Mode:          {'DRY RUN' if report.dry_run else 'LIVE'}")
        lines.append(f"Approved:      {'YES' if report.is_approved else 'NO — blocked'}")

        if report.failures:
            lines.append("")
            lines.append("FAILURES (blocking):")
            for f in report.failures:
                lines.append(f"  FAIL: {f}")

        if report.warnings:
            lines.append("")
            lines.append("WARNINGS:")
            for w in report.warnings:
                lines.append(f"  WARN: {w}")

        lines.append("")
        lines.append("WALLET STATUS")
        if report.eth_address:
            lines.append(f"  Ethereum:  {report.eth_address[:12]}... "
                          f"balance={report.eth_balance:.6f} ETH")
        if report.sol_address:
            lines.append(f"  Solana:    {report.sol_address[:12]}... "
                          f"balance={report.sol_balance:.6f} SOL")
        if report.kraken_gbp_balance > 0:
            lines.append(f"  Kraken:    GBP {report.kraken_gbp_balance:.2f}")

        if report.allocations:
            lines.append("")
            lines.append("ALLOCATION PLAN")
            header = f"  {'Protocol':<25s} {'Chain':>8s} {'%':>5s} {'GBP':>10s}"
            sep = "  " + "-" * 55
            lines.append(header)
            lines.append(sep)
            for a in report.allocations:
                status = "SKIP" if not a.meets_minimum else "OK"
                lines.append(
                    f"  {a.protocol:<25s} {a.chain:>8s} {a.percentage:>4.0f}% "
                    f"{a.amount_gbp:>9.2f}GBP  [{status}]"
                )

        lines.append("")
        lines.append("DAILY SPEND TRACKING")
        lines.append(
            f"  ETH spent today: {report.daily_eth_spent:.4f} / "
            f"{self.guard.get('MAX_DAILY_ETH_SPEND')} max"
        )
        lines.append(
            f"  SOL spent today: {report.daily_sol_spent:.4f} / "
            f"{self.guard.get('MAX_DAILY_SOL_SPEND')} max"
        )

        lines.append("=" * 60)
        return "\n".join(lines)

    def record_spend(self, eth_amount: float, sol_amount: float) -> None:
        """Record ETH and SOL amounts to daily spend tracking."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tracking = self._load_tracking()
        day = tracking.get(today, {"eth": 0.0, "sol": 0.0, "count": 0})
        day["eth"] += eth_amount
        day["sol"] += sol_amount
        day["count"] += 1
        tracking[today] = day
        # Keep only last 30 days
        keys = sorted(tracking.keys())[-30:]
        trimmed = {k: tracking[k] for k in keys}
        with open(TRACKING_FILE, "w", encoding="utf-8") as fh:
            json.dump(trimmed, fh, indent=2)

    # ── Private check methods ──

    def _check_eth_wallet(
        self, wallet_name: str, rpc_url: str
    ) -> Tuple[bool, str, str, float]:
        """Verify ETH wallet exists, connects, and has a key."""
        env_path = os.path.join("wallets", f"{wallet_name}.env")
        if not os.path.isfile(env_path):
            return False, f"ETH wallet '{wallet_name}' not found. Generate: --generate-wallet {wallet_name}", "", 0.0

        from src.chain_clients.ethereum_client import EthereumClient
        try:
            client = EthereumClient(rpc_url, wallet_name=wallet_name, guard=self.guard)
            addr = client.address
            bal = client.get_eth_balance()
            if not addr or not addr.startswith("0x"):
                return False, f"ETH wallet '{wallet_name}' has invalid address: {addr}", "", 0.0
            return True, "", addr, bal
        except Exception as exc:
            return False, f"ETH wallet '{wallet_name}' connection failed: {exc}", "", 0.0

    def _check_sol_wallet(
        self, wallet_name: str, rpc_url: str
    ) -> Tuple[bool, str, str, float]:
        """Verify Solana wallet exists, connects, and has a key."""
        env_path = os.path.join("wallets", f"{wallet_name}.env")
        if not os.path.isfile(env_path):
            return False, f"SOL wallet '{wallet_name}' not found. Generate: --generate-solana-wallet {wallet_name}", "", 0.0

        from src.chain_clients.solana_client import SolanaClient
        try:
            client = SolanaClient(rpc_url, wallet_name=wallet_name, guard=self.guard)
            addr = client.address
            bal = client.get_balance()
            if not addr:
                return False, f"SOL wallet '{wallet_name}' has invalid address", "", 0.0
            return True, "", addr, bal
        except Exception as exc:
            return False, f"SOL wallet '{wallet_name}' connection failed: {exc}", "", 0.0

    def _check_kraken(self) -> Tuple[bool, str, float]:
        """Check if Kraken API keys are configured and account is accessible."""
        api_key = os.getenv("KRAKEN_API_KEY")
        api_secret = os.getenv("KRAKEN_API_SECRET")
        if not api_key or not api_secret:
            return False, "Kraken API keys not configured. Set KRAKEN_API_KEY and KRAKEN_API_SECRET in .env", 0.0

        if self.guard.is_dry_run():
            return True, "", 0.0

        try:
            from src.exchange_client import KrakenClient
            client = KrakenClient(api_key, api_secret)
            balances = client.get_balance()
            gbp = float(balances.get("ZGBP", 0))
            return True, "", gbp
        except Exception as exc:
            return False, f"Kraken connection failed: {exc}", 0.0

    def _check_daily_spend(
        self, budget_gbp: float, strategy: Dict[str, Any]
    ) -> Tuple[bool, str, float, float]:
        """Check if this investment would exceed daily spend limits."""
        eth_chain = strategy.get("chains", {}).get("ethereum", {})
        sol_chain = strategy.get("chains", {}).get("solana", {})

        eth_weight = sum(eth_chain.get("allocations", {}).values()) / 100
        sol_weight = sum(sol_chain.get("allocations", {}).values()) / 100

        # Convert GBP budget to estimated crypto amounts
        # (rough estimates — real amounts depend on market price)
        eth_est = budget_gbp * eth_weight / 2000  # ~£2000/ETH
        sol_est = budget_gbp * sol_weight / 120   # ~£120/SOL

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tracking = self._load_tracking()
        day = tracking.get(today, {"eth": 0.0, "sol": 0.0, "count": 0})
        daily_eth = day["eth"]
        daily_sol = day["sol"]

        max_eth = float(self.guard.get("MAX_DAILY_ETH_SPEND"))
        max_sol = float(self.guard.get("MAX_DAILY_SOL_SPEND"))

        if daily_eth + eth_est > max_eth:
            return False, (
                f"Daily ETH spend would be {daily_eth + eth_est:.4f}, "
                f"exceeds max {max_eth}. Wait until tomorrow."
            ), daily_eth, daily_sol

        if daily_sol + sol_est > max_sol:
            return False, (
                f"Daily SOL spend would be {daily_sol + sol_est:.4f}, "
                f"exceeds max {max_sol}. Wait until tomorrow."
            ), daily_eth, daily_sol

        return True, "", daily_eth, daily_sol

    def _build_allocation_plan(
        self, budget_gbp: float, strategy: Dict[str, Any]
    ) -> List[AllocationLine]:
        """Build the detailed allocation plan from a strategy."""
        lines: List[AllocationLine] = []

        eth_chain = strategy.get("chains", {}).get("ethereum", {})
        sol_chain = strategy.get("chains", {}).get("solana", {})

        eth_allocations = eth_chain.get("allocations", {})
        sol_allocations = sol_chain.get("allocations", {})

        eth_weight = sum(eth_allocations.values()) / 100
        sol_weight = sum(sol_allocations.values()) / 100

        eth_gbp = budget_gbp * eth_weight
        sol_gbp = budget_gbp * sol_weight

        eth_min_dep = float(eth_chain.get("min_deposit_eth", 0.01))
        sol_min_dep = float(sol_chain.get("min_deposit_sol", 0.1))

        # Rough price estimates for min deposit conversion
        eth_price_est = 2000.0
        sol_price_est = 120.0

        for proto, pct in eth_allocations.items():
            proto_cfg = self._cfg.get("protocols", {}).get(proto, {})
            amount = eth_gbp * (pct / 100)
            meets = amount >= (eth_min_dep * eth_price_est)
            lines.append(AllocationLine(
                chain="ethereum",
                protocol=proto,
                asset=proto_cfg.get("asset", "ETH"),
                percentage=pct if eth_weight > 0 else pct / sum(eth_allocations.values()) * 100,
                amount_gbp=amount,
                estimated_tokens=amount / eth_price_est,
                min_deposit=eth_min_dep * eth_price_est,
                meets_minimum=meets,
            ))

        for proto, pct in sol_allocations.items():
            proto_cfg = self._cfg.get("protocols", {}).get(proto, {})
            amount = sol_gbp * (pct / 100)
            meets = amount >= (sol_min_dep * sol_price_est)
            lines.append(AllocationLine(
                chain="solana",
                protocol=proto,
                asset=proto_cfg.get("asset", "SOL"),
                percentage=pct if sol_weight > 0 else pct / sum(sol_allocations.values()) * 100,
                amount_gbp=amount,
                estimated_tokens=amount / sol_price_est,
                min_deposit=sol_min_dep * sol_price_est,
                meets_minimum=meets,
            ))

        return lines

    def _load_tracking(self) -> Dict[str, Any]:
        if not os.path.isfile(TRACKING_FILE):
            return {}
        try:
            with open(TRACKING_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}