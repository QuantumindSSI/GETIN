import argparse
import json
import sys

from src.config_manager import load_env
from src.cryptorank_client import CryptoRankClient
from src.currency_monitor import CurrencyMonitor
from src.logger import ActivityLogger
from src.refresh_watchlist import refresh_watchlist
from src.task_scheduler import TaskScheduler
from src.tge_monitor import TGEMonitor
from src.wallet_manager import WalletManager
from src.wallet_setup import generate_wallet, import_mnemonic


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
    parser.add_argument("--refresh", action="store_true", help="Refresh the ranked watchlist.")
    parser.add_argument(
        "--currency-symbols",
        nargs="+",
        default=[],
        help="Symbols to monitor.",
    )
    parser.add_argument("--market", action="store_true", help="Show global market snapshot.")
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
            import sys as _sys
            raw = _sys.stdin.read().strip()
            if not raw:
                print("Paste your 12-word mnemonic phrase below.")
                print("Type it and press Ctrl+D (Linux/Mac) or Ctrl+Z (Windows) when done.")
                raw = _sys.stdin.read().strip()
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

    client = CryptoRankClient()

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

    if args.run_tasks:
        logger = ActivityLogger()
        scheduler = TaskScheduler("ranked_watchlist.json", logger)
        wallet = WalletManager(args.rpc, wallet_name=args.wallet)
        scheduler.run(wallet)


if __name__ == "__main__":
    main()