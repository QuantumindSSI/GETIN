import argparse
import json

from src.config_manager import load_env
from src.cryptorank_client import CryptoRankClient
from src.currency_monitor import CurrencyMonitor
from src.logger import ActivityLogger
from src.refresh_watchlist import refresh_watchlist
from src.task_scheduler import TaskScheduler
from src.tge_monitor import TGEMonitor
from src.wallet_manager import WalletManager


def main() -> None:
    """Parse arguments and run the requested agent tasks."""
    load_env()
    parser = argparse.ArgumentParser(description="DeepSeek Farming Agent")
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
    args = parser.parse_args()

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
        wallet = WalletManager(args.rpc)
        scheduler.run(wallet)


if __name__ == "__main__":
    main()