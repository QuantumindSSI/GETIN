import argparse
import json
import sys

from src.config_manager import load_env, load_yaml
from src.cryptorank_client import CryptoRankClient
from src.currency_monitor import CurrencyMonitor
from src.logger import ActivityLogger
from src.refresh_watchlist import refresh_watchlist
from src.task_scheduler import TaskScheduler
from src.tge_monitor import TGEMonitor
from src.wallet_manager import WalletManager
from src.wallet_setup import generate_wallet, generate_solana_wallet, import_mnemonic
from src.yield_scanner import YieldScanner


WARNING = """
SECURITY WARNING
This bot signs real on-chain transactions.
Use a wallet that holds ZERO real assets (testnet tokens only).
Never reuse a private key from a wallet that stores actual funds.
Keys are stored locally and never sent to any third-party API.

Press Ctrl+C now to abort, or the operation will continue.
"""


def main() -> None:
    """Parse arguments and run the requested agent tasks."""
    load_env()
    parser = argparse.ArgumentParser(description="DeepSeek Farming Agent")
    parser.add_argument(
        "--generate-wallet",
        metavar="NAME",
        nargs="?",
        const="wallet_01",
        help="Generate a fresh BIP39 wallet for farming.",
    )
    parser.add_argument(
        "--import-mnemonic",
        metavar="NAME",
        nargs="?",
        const="wallet_01",
        help="Import a 12-word mnemonic and derive the private key.",
    )
    parser.add_argument(
        "--generate-solana-wallet",
        metavar="NAME",
        nargs="?",
        const="solana_01",
        help="Generate a fresh Solana keypair for Phantom or Solflare.",
    )
    parser.add_argument("--refresh", action="store_true", help="Refresh the ranked watchlist.")
    parser.add_argument(
        "--currency-symbols",
        nargs="+",
        default=[],
        help="Symbols to monitor.",
    )
    parser.add_argument("--market", action="store_true", help="Show global market snapshot.")
    parser.add_argument("--yield-scan", action="store_true", help="Scan DeFi yields and show ROI.")
    parser.add_argument("--activities", action="store_true", help="List all testnet farming activities.")
    parser.add_argument("--run-tasks", action="store_true", help="Execute the task loop.")
    parser.add_argument("--check-tge", action="store_true", help="Check for TGE/unlock events.")
    parser.add_argument(
        "--rpc",
        default="https://rpc.ankr.com/eth",
        help="RPC endpoint for the wallet.",
    )
    parser.add_argument(
        "--wallet",
        default="wallet_01",
        help="Wallet name to use for task execution.",
    )
    args = parser.parse_args()

    # --- Wallet setup commands (no network needed) ---
    if args.generate_wallet:
        print(WARNING)
        try:
            generate_wallet(args.generate_wallet)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(0)
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
            print("\nAborted.")
            sys.exit(0)
        mnemonic = " ".join(lines).strip().lower()
        if not mnemonic:
            print("No mnemonic entered. Aborted.")
            sys.exit(1)
        import_mnemonic(mnemonic, args.import_mnemonic)
        return

    if args.generate_solana_wallet:
        print(WARNING)
        generate_solana_wallet(args.generate_solana_wallet)
        return

    # --- Market data commands ---
    needs_key = any([args.market, args.refresh, bool(args.currency_symbols), args.check_tge])
    client = CryptoRankClient() if needs_key else None

    if args.market:
        snapshot = client.get_global_snapshot()
        print(json.dumps(snapshot, indent=2))

    if args.refresh:
        refresh_watchlist(client)
        print("Watchlist refreshed.")

    if args.currency_symbols:
        monitor = CurrencyMonitor(client, args.currency_symbols)
        snapshots = monitor.check()
        for s in snapshots:
            print(f"{s['symbol']}: ${s['price_usd']} | MCap: ${s['market_cap_usd']}")

    if args.check_tge:
        monitor = TGEMonitor(client)
        alerts = monitor.check()
        for a in alerts:
            print(f"ALERT: {a}")

    # --- Yield scanner ---
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
                print(
                    f"{p['label']:<32} "
                    f"{p['asset']:<10} "
                    f"{p['apy']:>7.2f}% "
                    f"${p['tvl']:>14,.0f}  "
                    f"${roi['roi_6h_usd']:>13.4f}  "
                    f"${roi['roi_30d_usd']:>13.2f}"
                )
                total += p["tvl"]
            print("-" * 115)
            print(f"{'Total TVL tracked':<32} {'':<10} {'':>8} ${total:>14,.0f}")
            print()
            print("ROI formula: amount * (APY / 100 / 365 / 24) * hours")
            print("Amount: $1000. 6h = 0.25 days. 30d = 30 days.")
            print("APY values are live from DefiLlama. Rates change daily.")
            print()

    # --- Testnet activities report ---
    if args.activities:
        data = load_yaml("config/testnet_activities.yaml")
        projects = data.get("projects", [])
        total = 0
        for proj in projects:
            name = proj["name"]
            count = proj.get("total_activities", 0)
            categories = [k for k in proj if k not in ("name", "network", "chain_id", "rpc", "symbol", "explorer", "note", "total_activities", "strategy", "zero_capital_workflow")]
            print(f"\n=== {name} ({proj['symbol']}) — {count} activities ===")
            if "note" in proj:
                print(f"  Note: {proj['note']}")
            for cat in categories:
                items = proj[cat]
                if not items:
                    continue
                print(f"  --- {cat.replace('_', ' ').title()} ({len(items)}) ---")
                for item in items:
                    if not isinstance(item, dict):
                        print(f"    {item}")
                        continue
                    url = item.get("url", "")
                    cooldown = f" [{item['cooldown_hours']}h]" if "cooldown_hours" in item else ""
                    nnote = f" — {item['note']}" if "note" in item else ""
                    ticker = f" ({item['ticker']})" if "ticker" in item else ""
                    display_name = item.get("name") or item.get("title") or str(item)
                    print(f"    {display_name}{ticker}{cooldown}{nnote}")
                    if url:
                        print(f"      {url}")
            if "zero_capital_workflow" in proj:
                print(f"  --- Zero-Capital Strategy ---")
                for step in proj["zero_capital_workflow"]:
                    if isinstance(step, dict):
                        print(f"    Step {step.get('step', '?')}: {step.get('title', '')}")
                        print(f"      {step.get('description', '')}")
            total += count
        print(f"\nTotal unique activities across all projects: {total}")
        print()
        print("ROI context: Testnet tokens have $0 market value.")
        print("The only payoff is a speculative airdrop at TGE (3-24 months).")
        print("Use --yield-scan for real mainnet DeFi yield projections.")

    # --- Task execution ---
    if args.run_tasks:
        logger = ActivityLogger()
        scheduler = TaskScheduler("ranked_watchlist.json", logger)
        wallet = WalletManager(args.rpc, wallet_name=args.wallet)
        scheduler.run(wallet)


if __name__ == "__main__":
    main()