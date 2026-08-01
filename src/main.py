import argparse
import json
import os
import sys

from src.config_manager import load_env
from src.cryptorank_client import CryptoRankClient
from src.currency_monitor import CurrencyMonitor
from src.harvester import YieldHarvester
from src.portfolio_manager import PortfolioManager
from src.safety_guard import SafetyGuard
from src.wallet_manager import WalletManager
from src.wallet_setup import generate_wallet, generate_solana_wallet, import_mnemonic
from src.yield_scanner import YieldScanner


WARNING = """
SECURITY WARNING
This bot can sign real on-chain transactions (if DRY_RUN is off).
Use a dedicated wallet with limited funds.
Keys are stored locally (chmod 600) and never sent to any third-party API.
Recovery phrases are written to a file, NOT printed to the terminal.

Press Ctrl+C now to abort, or the operation will continue.
"""


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="GETIN Yield Agent")
    parser.add_argument("--generate-wallet", metavar="NAME", nargs="?", const="wallet_01",
                        help="Generate a fresh BIP39 wallet.")
    parser.add_argument("--import-mnemonic", metavar="NAME", nargs="?", const="wallet_01",
                        help="Import a 12-word mnemonic and derive the private key.")
    parser.add_argument("--generate-solana-wallet", metavar="NAME", nargs="?", const="solana_01",
                        help="Generate a fresh Solana keypair.")
    parser.add_argument("--currency-symbols", nargs="+", default=[], help="Symbols to monitor.")
    parser.add_argument("--market", action="store_true", help="Show global market snapshot.")
    parser.add_argument("--yield-scan", action="store_true", help="Scan DeFi yields and show ROI projections.")
    parser.add_argument("--invest", action="store_true", help="Full deployment: exchange buy -> wallet -> yield deposit. Requires Kraken API keys and real funds.")
    parser.add_argument("--harvest", action="store_true", help="Harvest accrued yield from all active positions.")
    parser.add_argument("--positions", action="store_true", help="Show current yield positions across chains.")
    parser.add_argument("--unwind", action="store_true", help="Withdraw all funds from yield protocols back to wallet.")
    parser.add_argument("--strategy", default="conservative", help="Strategy name from config/strategies.yaml")
    parser.add_argument("--budget-gbp", type=float, default=0.0, help="GBP budget for --invest")
    parser.add_argument("--rpc", default=os.getenv("ETH_RPC_URL", "https://eth.drpc.org"), help="Ethereum RPC endpoint")
    parser.add_argument("--sol-rpc", default=os.getenv("SOL_RPC_URL", "https://api.mainnet-beta.solana.com"), help="Solana RPC endpoint")
    parser.add_argument("--wallet", default="wallet_01", help="Ethereum wallet name for transaction execution")
    parser.add_argument("--sol-wallet", default="solana_01", help="Solana wallet name for transaction execution")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode for this run")
    parser.add_argument("--yes", action="store_true", help="Skip confirmations (dangerous)")

    args = parser.parse_args()

    if args.dry_run:
        os.environ["DRY_RUN"] = "true"
    if args.yes:
        os.environ["REQUIRE_CONFIRMATION"] = "false"

    guard = SafetyGuard()

    # ── Wallet setup ──
    if args.generate_wallet:
        print(WARNING)
        try:
            generate_wallet(args.generate_wallet)
        except KeyboardInterrupt:
            print("\nAborted."); sys.exit(0)
        return

    if args.import_mnemonic:
        print(WARNING)
        lines = []
        try:
            raw = sys.stdin.read().strip()
            if not raw:
                print("Paste your 12-word mnemonic phrase below.")
                print("Type it and press Ctrl+D (Linux/Mac) or Ctrl+Z (Windows) when done.")
                raw = sys.stdin.read().strip()
            lines = raw.split()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted."); sys.exit(0)
        mnemonic = " ".join(lines).strip().lower()
        if not mnemonic:
            print("No mnemonic entered. Aborted."); sys.exit(1)
        import_mnemonic(mnemonic, args.import_mnemonic)
        return

    if args.generate_solana_wallet:
        print(WARNING)
        generate_solana_wallet(args.generate_solana_wallet)
        return

    # ── Yield farming: invest ──
    if args.invest:
        if args.budget_gbp <= 0:
            print("Usage: --invest --budget-gbp 100 [--strategy conservative]")
            sys.exit(1)
        print(f"Strategy: {args.strategy} | Budget: GBP {args.budget_gbp}")
        print(f"DRY RUN: {guard.is_dry_run()}")
        pm = PortfolioManager(
            strategy_name=args.strategy,
            eth_rpc=args.rpc, sol_rpc=args.sol_rpc,
            wallet_name=args.wallet, sol_wallet_name=args.sol_wallet,
            guard=guard,
        )
        pm.run_full_deployment(args.budget_gbp)
        harv = YieldHarvester(
            eth_rpc=args.rpc, sol_rpc=args.sol_rpc,
            strategy_name=args.strategy, wallet_name=args.wallet, guard=guard,
        )
        harv.record_baselines()
        return

    # ── Harvest ──
    if args.harvest:
        harv = YieldHarvester(
            eth_rpc=args.rpc, sol_rpc=args.sol_rpc,
            strategy_name=args.strategy, wallet_name=args.wallet, guard=guard,
        )
        summary = harv.run_harvest()
        print(json.dumps(summary, indent=2))
        return

    # ── Positions ──
    if args.positions:
        pm = PortfolioManager(
            strategy_name=args.strategy,
            eth_rpc=args.rpc, sol_rpc=args.sol_rpc,
            wallet_name=args.wallet, sol_wallet_name=args.sol_wallet,
            guard=guard,
        )
        pos = pm.get_positions()
        print(json.dumps(pos, indent=2))
        return

    # ── Unwind ──
    if args.unwind:
        print("UNWIND: Withdrawing all funds from yield protocols...")
        from src.chain_clients.ethereum_client import EthereumClient
        from src.chain_clients.solana_client import SolanaClient
        from src.yield_protocols.aave_v3 import AaveV3Client
        from src.yield_protocols.jupiter_solana import JupiterSwap
        try:
            eth = EthereumClient(args.rpc, wallet_name=args.wallet, guard=guard)
            aave = AaveV3Client(eth, guard)
            for asset_name, asset_addr in [
                ("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
                ("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
            ]:
                try: tx = aave.withdraw_all(asset_addr); print(f"  {asset_name} withdrawn: {tx}")
                except Exception as e: print(f"  {asset_name}: {e}")
        except Exception as e: print(f"  Ethereum unwind error: {e}")
        try:
            sol = SolanaClient(args.sol_rpc, wallet_name=args.sol_wallet, guard=guard)
            jupiter = JupiterSwap(sol, guard)
            for name, mint in [
                ("JitoSOL", "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"),
                ("mSOL", "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"),
            ]:
                bal = sol.get_token_balance(mint)
                if bal > 0:
                    try: r = jupiter.swap_token_to_sol(mint, int(bal*1e9)); print(f"  {name} -> SOL: {r['tx']}")
                    except Exception as e: print(f"  {name}: {e}")
                else: print(f"  {name}: no balance")
        except Exception as e: print(f"  Solana unwind error: {e}")
        print("UNWIND COMPLETE")
        return

    # ── Market data ──
    needs_key = any([args.market, bool(args.currency_symbols)])
    client = CryptoRankClient() if needs_key else None

    if args.market:
        snapshot = client.get_global_snapshot()
        print(json.dumps(snapshot, indent=2))

    if args.currency_symbols:
        monitor = CurrencyMonitor(client, args.currency_symbols)
        snapshots = monitor.check()
        for s in snapshots:
            print(f"{s['symbol']}: ${s['price_usd']} | MCap: ${s['market_cap_usd']}")

    if args.yield_scan:
        scanner = YieldScanner()
        pools = scanner.scan()
        if not pools:
            print("Could not fetch yield data. Check network.")
        else:
            print(f"{'Protocol':<32} {'Asset':<10} {'APY %':>8} {'TVL':>16}  {'6h ROI/$1000':>15} {'30d ROI/$1000':>15}")
            print("-" * 115)
            total = 0.0
            for p in pools:
                roi = scanner.calculate_roi(p["apy"])
                print(f"{p['label']:<32} {p['asset']:<10} {p['apy']:>7.2f}% ${p['tvl']:>14,.0f}  ${roi['roi_6h_usd']:>13.4f}  ${roi['roi_30d_usd']:>13.2f}")
                total += p["tvl"]
            print("-" * 115)
            print(f"{'Total TVL tracked':<32} {'':<10} {'':>8} ${total:>14,.0f}")
            print()
            print("ROI uses compound APY formula: amount * ((1 + APY)^(fraction) - 1)")


if __name__ == "__main__":
    main()