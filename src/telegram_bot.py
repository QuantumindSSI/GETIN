import asyncio
import json
import os
import signal
from datetime import datetime, timezone
from typing import Any, Dict, List

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from src.config_manager import load_env
from src.cryptorank_client import CryptoRankClient
from src.currency_monitor import CurrencyMonitor
from src.safety_guard import SafetyGuard
from src.portfolio_manager import PortfolioManager
from src.harvester import YieldHarvester
from src.wallet_setup import generate_wallet, generate_solana_wallet
from src.yield_scanner import YieldScanner
from src.ai_sanitizer import get_ai_sanitizer

load_env()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CR_API_KEY = os.getenv("CRYPTORANK_API_KEY")
OWNER_ID = os.getenv("TELEGRAM_OWNER_ID", "")
ETH_RPC = os.getenv("ETH_RPC_URL", "https://eth.drpc.org")
SOL_RPC = os.getenv("SOL_RPC_URL", "https://api.mainnet-beta.solana.com")

DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL"]

START_TEXT = (
    "GETIN Yield Farming Agent — real on-chain automation.\n\n"
    "Yield Commands:\n"
    "/yield — Live DeFi yields from DefiLlama (ETH + SOL)\n"
    "/market — Global crypto market snapshot\n"
    "/prices BTC ETH SOL — Live prices\n\n"
    "Investment Commands:\n"
    "/invest STRATEGY GBP — Buy crypto, withdraw, deposit into yield\n"
    "/harvest — Claim accrued yield from all active positions\n"
    "/positions — Show current yield positions\n"
    "/unwind — Exit all yield protocols back to wallet\n\n"
    "Wallet:\n"
    "/wallet — Generate ETH wallet\n"
    "/solana_wallet — Generate Solana wallet\n\n"
    "Safety:\n"
    "/safety — Show safety limits and DRY_RUN status\n"
    "/help — This message\n\n"
    "DRY_RUN is ON by default. No real transactions sent unless disabled.\n"
    "Real yield farming requires funded wallets and exchange API keys."
)


def _format_yield_table(pools: List[Dict[str, Any]]) -> str:
    scanner = YieldScanner()
    lines = []
    header = f"{'Protocol':<22} {'APY':>7}  {'6h':>8} {'30d':>8}"
    sep = "-" * 50
    lines.append(f"<pre>{header}\n{sep}")

    for p in pools[:10]:
        roi = scanner.calculate_roi(p["apy"])
        lines.append(
            f"{p['label']:<22} "
            f"{p['apy']:>6.2f}% "
            f"${roi['roi_6h_usd']:>6.4f} "
            f"${roi['roi_30d_usd']:>6.2f}"
        )
    lines.append("</pre>")
    lines.append("ROI per $1000 invested. Rates from DefiLlama — live, change daily.")
    return "\n".join(lines)


async def _check_message(update: Update, context: ContextTypes.DEFAULT_TYPE, intent: str) -> Optional[str]:
    """Validate incoming Telegram message with AI. Returns rejection reason or None if ok."""
    if not update.message or not update.message.text:
        return None
    ai = get_ai_sanitizer()
    result = ai.sanitise_message(update.message.text)
    if not result.is_safe:
        await update.message.reply_text("[AI SAFETY] {}".format(
            "; ".join(result.warnings) if result.warnings else "Message blocked by safety filter."
        ))
        return "blocked"
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_TEXT)


async def yield_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("Scanning live DeFi yields...")
    try:
        scanner = YieldScanner()
        pools = scanner.scan()
        if not pools:
            await msg.edit_text("Could not fetch yield data. Try again later.")
            return
        text = _format_yield_table(pools)
        await msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as exc:
        await msg.edit_text(f"Yield scan failed: {exc}")


async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CR_API_KEY:
        await update.message.reply_text("CRYPTORANK_API_KEY is not set. Check .env.")
        return
    try:
        client = CryptoRankClient(CR_API_KEY)
        snapshot = client.get_global_snapshot()
        d = snapshot.get("data", {})
        lines = [
            "<b>Global Crypto Market</b>",
            f"Total MCap: ${float(d.get('totalMarketCap',0)):,.0f}",
            f"24h Volume: ${float(d.get('totalVolume24h',0)):,.0f}",
            f"BTC Dominance: {float(d.get('btcMarketCap',0))/float(d.get('totalMarketCap',1))*100:.1f}%",
            f"Active Currencies: {d.get('activeCurrencies',0)}",
            f"24h Change: {d.get('marketCapChangePercent24h',0):.2f}%",
        ]
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as exc:
        await update.message.reply_text(f"Market data failed: {exc}")


async def prices_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CR_API_KEY:
        await update.message.reply_text("CRYPTORANK_API_KEY is not set. Check .env.")
        return
    symbols = context.args if context.args else DEFAULT_SYMBOLS
    try:
        client = CryptoRankClient(CR_API_KEY)
        monitor = CurrencyMonitor(client, list(symbols))
        snapshots = monitor.check()
        if not snapshots:
            await update.message.reply_text("No data found for those symbols.")
            return
        lines = ["<b>Live Prices</b>"]
        for s in snapshots:
            lines.append(
                f"{s['symbol']}: ${float(s['price_usd'] or 0):,.2f}  "
                f"(MCap: ${float(s['market_cap_usd'] or 0):,.0f})"
            )
        lines.append(f"\nUpdated: {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as exc:
        await update.message.reply_text(f"Price fetch failed: {exc}")


async def wallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("Use /wallet in a private chat for security.")
        return
    name = context.args[0] if context.args else "tg_wallet"
    try:
        addr = generate_wallet(name)
        await update.message.reply_text(
            f"ETH wallet generated: <code>{addr}</code>\n"
            f"Key saved to wallets/{name}.env\n\n"
            "Fund with minimal gas tokens. Never fund with real assets you cannot afford to lose.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        await update.message.reply_text(f"Wallet generation failed: {exc}")


async def solana_wallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("Use /solana_wallet in a private chat for security.")
        return
    name = context.args[0] if context.args else "tg_solana"
    try:
        addr = generate_solana_wallet(name)
        await update.message.reply_text(
            f"Solana wallet generated: <code>{addr}</code>\n"
            f"Key saved to wallets/{name}.env\n\n"
            "Hex format for internal GETIN use only. Use wallet address to fund from an exchange.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        await update.message.reply_text(f"Wallet generation failed: {exc}")


# ── Real Yield Farming Commands ──

async def invest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _check_message(update, context, "invest"):
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /invest STRATEGY BUDGET_GBP\n"
            "Example: /invest conservative 100\n"
            "Strategies: conservative, balanced, aggressive_solana\n\n"
            "Requires KRAKEN_API_KEY and KRAKEN_API_SECRET in .env\n"
            "Requires DRY_RUN=false for real transactions"
        )
        return
    strategy = context.args[0]
    try:
        budget = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Budget must be a number (GBP).")
        return
    msg = await update.message.reply_text(
        f"Starting deployment: {strategy} strategy, GBP {budget} budget..."
    )
    def _run():
        guard = SafetyGuard()
        pm = PortfolioManager(
            strategy_name=strategy, eth_rpc=ETH_RPC, sol_rpc=SOL_RPC, guard=guard,
        )
        pm.run_full_deployment(budget)
        harv = YieldHarvester(
            eth_rpc=ETH_RPC, sol_rpc=SOL_RPC, strategy_name=strategy,
            wallet_name="wallet_01", sol_wallet_name="solana_01", guard=guard,
        )
        harv.record_baselines()
        return "Deployment complete. Check /positions."
    try:
        result = await asyncio.to_thread(_run)
        await msg.edit_text(f"<b>Investment Deployed</b>\n{result}", parse_mode=ParseMode.HTML)
    except Exception as exc:
        await msg.edit_text(f"Investment failed: {exc}")


async def harvest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _check_message(update, context, "harvest"):
        return
    msg = await update.message.reply_text("Running harvest cycle...")
    def _run():
        harv = YieldHarvester(eth_rpc=ETH_RPC, sol_rpc=SOL_RPC, wallet_name="wallet_01", sol_wallet_name="solana_01", guard=SafetyGuard())
        return harv.run_harvest()
    try:
        summary = await asyncio.to_thread(_run)
        lines = ["<b>Harvest Results</b>"]
        for protocol, data in summary.items():
            lines.append(f"\n<u>{protocol.upper()}</u>")
            if data.get("ok"):
                for r in data.get("results", []):
                    harvested = "✅" if r.get("harvested") else "⏸"
                    lines.append(f"  {harvested} {r.get('protocol','')}: yield={r.get('yield',r.get('gain',0)):.6f}")
            else:
                lines.append(f"  Error: {data.get('error','unknown')}")
        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as exc:
        await msg.edit_text(f"Harvest failed: {exc}")


async def positions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    strategy = context.args[0] if context.args else "conservative"
    def _run():
        pm = PortfolioManager(strategy_name=strategy, eth_rpc=ETH_RPC, sol_rpc=SOL_RPC, guard=SafetyGuard())
        return pm.get_positions()
    try:
        pos = await asyncio.to_thread(_run)
        lines = [f"<b>Positions ({strategy})</b>"]
        for chain, protocols in pos.items():
            lines.append(f"\n<u>{chain.upper()}</u>")
            if not protocols:
                lines.append("  No active positions")
                continue
            for name, val in protocols.items():
                lines.append(f"  {name}: {val:.6f}")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as exc:
        await update.message.reply_text(f"Positions failed: {exc}")


async def unwind_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("Unwinding all yield positions...")
    def _run():
        from src.chain_clients.ethereum_client import EthereumClient
        from src.chain_clients.solana_client import SolanaClient
        from src.yield_protocols.aave_v3 import AaveV3Client
        from src.yield_protocols.jupiter_solana import JupiterSwap
        guard = SafetyGuard()
        results = []
        if ETH_RPC:
            eth = EthereumClient(ETH_RPC, guard=guard)
            aave = AaveV3Client(eth, guard)
            weth = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
            usdc = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
            try: tx = aave.withdraw_all(weth); results.append(f"Aave WETH withdrawn: {tx[:20]}...")
            except Exception as e: results.append(f"Aave WETH: {e}")
            try: tx = aave.withdraw_all(usdc); results.append(f"Aave USDC withdrawn: {tx[:20]}...")
            except Exception as e: results.append(f"Aave USDC: {e}")
        if SOL_RPC:
            sol = SolanaClient(SOL_RPC, guard=guard)
            jupiter = JupiterSwap(sol, guard)
            for mint_name, mint in (
                ("JitoSOL", "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"),
                ("mSOL", "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"),
            ):
                bal = sol.get_token_balance(mint)
                if bal > 0:
                    try: res = jupiter.swap_token_to_sol(mint, int(bal*1e9)); results.append(f"{mint_name} -> SOL: {res['tx'][:20]}...")
                    except Exception as e: results.append(f"{mint_name} unwind failed: {e}")
                else: results.append(f"{mint_name}: no balance")
        return results
    try:
        results = await asyncio.to_thread(_run)
        text = "<b>Unwind Results</b>\n" + "\n".join(f"• {r}" for r in results)
        await msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as exc:
        await msg.edit_text(f"Unwind failed: {exc}")


async def safety_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    guard = SafetyGuard()
    ai = get_ai_sanitizer()
    report = ai.get_report()
    lines = [
        "<b>Safety Guard</b>",
        f"DRY_RUN: {'ON' if guard.is_dry_run() else 'OFF (REAL TRANSACTIONS)'}",
        f"REQUIRE_CONFIRMATION: {'ON' if guard.require_confirmation() else 'OFF'}",
        f"MAX_GAS_GWEI: {guard.get('MAX_GAS_GWEI')}",
        f"MAX_SLIPPAGE_BPS: {guard.get('MAX_SLIPPAGE_BPS')}",
        f"MIN_TRADE_ETH: {guard.get('MIN_TRADE_ETH')}",
        f"MIN_TRADE_SOL: {guard.get('MIN_TRADE_SOL')}",
        "",
        "<b>AI Sanitisation</b>",
        f"Checks: {report.total_checks} | Passed: {report.passed} | Rejected: {report.rejected}",
        "",
        "Set DRY_RUN=false in .env to enable real transactions.",
        "All transactions respect these limits.",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def dryrun_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text("Admin only.")
        return
    current = os.getenv("DRY_RUN", "true").lower() == "true"
    new_val = "false" if current else "true"
    os.environ["DRY_RUN"] = new_val
    await update.message.reply_text(
        f"DRY_RUN toggled to <b>{new_val.upper()}</b>.\n"
        f"{'REAL TRANSACTIONS WILL BE SENT.' if new_val == 'false' else 'No real transactions.'}"
    )


def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("yield", yield_cmd))
    app.add_handler(CommandHandler("market", market_cmd))
    app.add_handler(CommandHandler("prices", prices_cmd))
    app.add_handler(CommandHandler("wallet", wallet_cmd))
    app.add_handler(CommandHandler("solana_wallet", solana_wallet_cmd))
    app.add_handler(CommandHandler("invest", invest_cmd))
    app.add_handler(CommandHandler("harvest", harvest_cmd))
    app.add_handler(CommandHandler("positions", positions_cmd))
    app.add_handler(CommandHandler("unwind", unwind_cmd))
    app.add_handler(CommandHandler("safety", safety_cmd))
    app.add_handler(CommandHandler("dryrun", dryrun_cmd))
    return app


def run_bot() -> None:
    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN is missing. Set it in .env")
        return
    app = build_app()
    print(f"GETIN Telegram bot starting...")
    print(f"Token loaded: {'yes' if BOT_TOKEN else 'no'}")
    print(f"CryptoRank key loaded: {'yes' if CR_API_KEY else 'no'}")
    print(f"DRY_RUN: {os.getenv('DRY_RUN', 'true')}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run(app))
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        loop.close()


async def _run(app: Application) -> None:
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    print("Bot is running. Press Ctrl+C to stop.")
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    await app.updater.stop()
    await app.stop()
    await app.shutdown()


if __name__ == "__main__":
    run_bot()