import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml

from src.chain_clients.ethereum_client import EthereumClient
from src.chain_clients.solana_client import SolanaClient
from src.config_manager import load_yaml
from src.exchange_client import ExchangeClient
from src.investment_guard import InvestmentGuard, PreFlightReport
from src.safety_guard import SafetyGuard, SafetyError
from src.yield_protocols.aave_v3 import AaveV3Client
from src.yield_protocols.jupiter_solana import JupiterSwap
from src.yield_protocols.lido import LidoClient

LOG_FILE = "portfolio_actions.jsonl"

verbose = True


def _log(action: str, payload: Dict[str, Any]):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "payload": payload,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


class PortfolioManager:
    """
    End-to-end capital deployment: exchange → wallet → yield protocol.
    """

    def __init__(
        self,
        strategy_name: str = "conservative",
        eth_rpc: Optional[str] = None,
        sol_rpc: Optional[str] = None,
        wallet_name: str = "wallet_01",
        sol_wallet_name: str = "solana_01",
        guard: Optional[SafetyGuard] = None,
    ):
        self.guard = guard or SafetyGuard()
        self.investment_guard = InvestmentGuard(self.guard)
        self.exchange: Optional[ExchangeClient] = None
        cfg = load_yaml("config/strategies.yaml")
        self.strategy = cfg.get("strategies", {}).get(strategy_name)
        if not self.strategy:
            raise ValueError(f"Strategy '{strategy_name}' not found in config/strategies.yaml")
        self.protocols = cfg.get("protocols", {})
        self.strategy_name = strategy_name
        self.wallet_name = wallet_name
        self.sol_wallet_name = sol_wallet_name

        self.eth_client: Optional[EthereumClient] = None
        self.sol_client: Optional[SolanaClient] = None

        if eth_rpc:
            try:
                self.eth_client = EthereumClient(eth_rpc, wallet_name=wallet_name, guard=self.guard)
            except Exception as exc:
                print(f"Warning: Ethereum RPC connection failed: {exc}")
        if sol_rpc:
            try:
                self.sol_client = SolanaClient(sol_rpc, wallet_name=sol_wallet_name, guard=self.guard)
            except Exception as exc:
                print(f"Warning: Solana RPC connection failed: {exc}")

    def _get_exchange(self) -> ExchangeClient:
        if self.exchange is None:
            self.exchange = ExchangeClient()
        return self.exchange

    def _get_protocol_cfg(self, name: str) -> Dict[str, Any]:
        return self.protocols.get(name, {})

    def buy_and_withdraw(self, pair: str, volume_gbp: float, withdraw_key: str):
        """
        Market-buy crypto with GBP on Kraken, then withdraw to
        the whitelisted wallet address key.
        """
        if self.guard.is_dry_run():
            print(f"[DRY RUN] Would buy {volume_gbp} GBP worth on {pair} and withdraw to {withdraw_key}")
            return {"dry_run": True}

        ex = self._get_exchange()

        # 1. Market buy
        print(f"Placing market buy: {pair} for ~{volume_gbp} GBP...")
        order = ex.buy_market(pair, volume_gbp)
        _log("market_buy", {"pair": pair, "volume_gbp": volume_gbp, "order": order})
        print(f"  Order placed: {order.get('txid', order)}")

        # Wait briefly for balance to settle (Kraken needs a moment)
        import time
        time.sleep(2)

        # 2. Withdraw
        asset = pair.replace("ZGBP", "").replace("X", "")
        if asset == "ETH":
            asset = "ETH"
        elif asset == "SOL":
            asset = "SOL"

        bal = ex.get_balance()
        avail = bal.get(asset, 0)
        if avail <= 0:
            print(f"  No {asset} available to withdraw.")
            return order

        print(f"  Withdrawing {avail} {asset} to key '{withdraw_key}'...")
        result = ex.withdraw(asset, avail, withdraw_key)
        _log("withdraw", {"asset": asset, "amount": avail, "key": withdraw_key, "result": result})
        print(f"  Withdrawal ref: {result}")
        return {"order": order, "withdrawal": result}

    def deploy_ethereum(self, wallet_address: str, available_eth: float):
        """
        Deploy ETH holdings into Ethereum yield protocols per strategy.
        """
        if not self.eth_client:
            raise SafetyError("Ethereum RPC not configured.")
        if available_eth <= 0:
            print("No ETH available to deploy.")
            return

        chain_cfg = self.strategy.get("chains", {}).get("ethereum", {})
        allocations = chain_cfg.get("allocations", {})
        min_dep = float(chain_cfg.get("min_deposit_eth", 0.01))

        for protocol_name, pct in allocations.items():
            amount = available_eth * (pct / 100)
            if amount < min_dep:
                print(f"  Skip {protocol_name}: {amount:.4f} ETH < min {min_dep}")
                continue

            print(f"Deploying {amount:.4f} ETH to {protocol_name}...")
            try:
                if protocol_name == "lido_steth":
                    lido = LidoClient(self.eth_client, self.guard)
                    tx = lido.submit(amount)
                    _log("deposit", {"protocol": protocol_name, "amount": amount, "tx": tx})
                    print(f"  Staked via Lido: {tx}")
                elif protocol_name == "aave_v3_weth":
                    aave = AaveV3Client(self.eth_client, self.guard)
                    # For raw ETH we need to wrap first, but for simplicity assume WETH held
                    # or deposit via Aave WETH gateway. For now deposit WETH if present.
                    weth = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
                    tx = aave.supply(weth, amount)
                    _log("deposit", {"protocol": protocol_name, "amount": amount, "tx": tx})
                    print(f"  Supplied to Aave: {tx}")
                else:
                    print(f"  Protocol handler not implemented: {protocol_name}")
            except Exception as exc:
                print(f"  FAILED to deploy to {protocol_name}: {exc}")
                _log("deposit_failed", {"protocol": protocol_name, "error": str(exc)})

    def deploy_solana(self, wallet_address: str, available_sol: float):
        """
        Deploy SOL holdings into Solana yield protocols per strategy.
        """
        if not self.sol_client:
            raise SafetyError("Solana RPC not configured.")
        if available_sol <= 0:
            print("No SOL available to deploy.")
            return

        chain_cfg = self.strategy.get("chains", {}).get("solana", {})
        allocations = chain_cfg.get("allocations", {})
        min_dep = float(chain_cfg.get("min_deposit_sol", 0.1))
        jupiter = JupiterSwap(self.sol_client, self.guard)

        for protocol_name, pct in allocations.items():
            amount = available_sol * (pct / 100)
            if amount < min_dep:
                print(f"  Skip {protocol_name}: {amount:.4f} SOL < min {min_dep}")
                continue

            print(f"Deploying {amount:.4f} SOL to {protocol_name} via Jupiter...")
            try:
                cfg = self._get_protocol_cfg(protocol_name)
                mint = cfg.get("mint")
                if not mint:
                    print(f"  No mint configured for {protocol_name}")
                    continue
                result = jupiter.swap_sol_to_token(mint, amount)
                _log("deposit", {"protocol": protocol_name, "amount": amount, "result": result})
                print(f"  Swapped to yield token: {result['tx']}")
            except Exception as exc:
                print(f"  FAILED to deploy to {protocol_name}: {exc}")
                _log("deposit_failed", {"protocol": protocol_name, "error": str(exc)})

    def run_full_deployment(self, gbp_budget: float):
        """
        End-to-end flow with full guardrails:
          0. Pre-flight checks (wallet, Kraken, daily limits, plan)
          1. Buy ETH + SOL on Kraken
          2. Withdraw to self-custody wallets
          3. Deposit into yield protocols
        """
        print("=" * 60)
        print("PORTFOLIO DEPLOYMENT START")
        print("=" * 60)

        # ── Run pre-flight guardrails ──
        report = self.investment_guard.pre_flight(
            strategy_name=self.strategy_name,
            budget_gbp=gbp_budget,
            wallet_name=self.wallet_name,
            sol_wallet_name=self.sol_wallet_name,
            eth_rpc=self.eth_client.rpc_url if self.eth_client else None,
            sol_rpc=self.sol_client.rpc_url if self.sol_client else None,
        )

        # Display the plan
        print(self.investment_guard.format_plan(report))

        # Block if not approved
        if not report.is_approved:
            raise SafetyError(
                f"Pre-flight checks FAILED. {len(report.failures)} blocking issue(s). "
                "Fix them and retry."
            )

        # Record daily spend
        eth_est = gbp_budget * report.eth_gbp_alloc / 2000 if gbp_budget > 0 else 0
        sol_est = gbp_budget * report.sol_gbp_alloc / 120 if gbp_budget > 0 else 0
        self.investment_guard.record_spend(eth_est, sol_est)

        eth_alloc = self.strategy.get("chains", {}).get("ethereum", {}).get("allocations", {})
        sol_alloc = self.strategy.get("chains", {}).get("solana", {}).get("allocations", {})

        eth_weight = sum(eth_alloc.values()) / 100
        sol_weight = sum(sol_alloc.values()) / 100

        # ── AI sanitisation of portfolio action ──
        from src.ai_sanitizer import get_ai_sanitizer
        ai = get_ai_sanitizer()
        pfolio = ai.sanitise_portfolio_action(
            strategy=self.strategy.get("name", self.strategy_name),
            budget_gbp=gbp_budget,
            action_type="invest",
            eth_pct=eth_weight * 100,
            sol_pct=sol_weight * 100,
        )
        if not pfolio.is_safe:
            raise SafetyError(f"AI portfolio check failed: {pfolio.warnings}")
        for w in pfolio.warnings:
            print(f"[AI WARNING] {w}")

        eth_weight = sum(eth_alloc.values()) / 100
        sol_weight = sum(sol_alloc.values()) / 100

        eth_gbp = gbp_budget * eth_weight
        sol_gbp = gbp_budget * sol_weight

        if eth_gbp > 0 and self.eth_client:
            print(f"\n--- Ethereum leg (~£{eth_gbp:.2f}) ---")
            self.buy_and_withdraw("XETHZGBP", eth_gbp, "getin_eth_wallet")
            print("  NOTE: Kraken withdrawals take ~5-30 min to confirm on-chain.")
            print("  The on-chain balance will show 0 until the withdrawal clears.")
            print("  Run --positions later to verify. Deposits require confirmed balance.")
            if not self.guard.is_dry_run():
                print("  Balance at current wallet: %.4f ETH" % self.eth_client.get_eth_balance())

        if sol_gbp > 0 and self.sol_client:
            print(f"\n--- Solana leg (~£{sol_gbp:.2f}) ---")
            self.buy_and_withdraw("XSOLZGBP", sol_gbp, "getin_sol_wallet")
            print("  NOTE: Kraken withdrawals take ~2-10 min to confirm on-chain.")
            print("  The on-chain balance will show 0 until the withdrawal clears.")
            print("  Run --positions later to verify. Deposits require confirmed balance.")
            if not self.guard.is_dry_run():
                print("  Balance at current wallet: %.4f SOL" % self.sol_client.get_balance())

        print("\n" + "=" * 60)
        print("DEPLOYMENT COMPLETE")
        print("=" * 60)

    def get_positions(self) -> Dict[str, Any]:
        """Snapshot current yield positions across chains."""
        positions: Dict[str, Any] = {}
        if self.eth_client:
            positions["ethereum"] = {}
            try:
                lido = LidoClient(self.eth_client, self.guard)
                positions["ethereum"]["lido_steth"] = lido.get_steth_balance()
            except Exception:
                pass
            try:
                aave = AaveV3Client(self.eth_client, self.guard)
                data = aave.get_user_account_data()
                positions["ethereum"]["aave_total_collateral_eth"] = data["totalCollateralBase"] / 1e8
            except Exception:
                pass
        if self.sol_client:
            positions["solana"] = {}
            for name, cfg in self.protocols.items():
                if cfg.get("chain") == "solana":
                    mint = cfg.get("mint")
                    if mint:
                        try:
                            bal = self.sol_client.get_token_balance(mint)
                            positions["solana"][name] = bal
                        except Exception:
                            pass
        return positions
