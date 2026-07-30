import asyncio
import json
import os
import signal
import textwrap
from datetime import datetime, timezone
from typing import Any, Dict, List

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from src.config_manager import load_env
from src.cryptorank_client import CryptoRankClient
from src.currency_monitor import CurrencyMonitor
from src.quest_engine import QuestTracker
from src.reporter import subscribe_chat, unsubscribe_chat
from src.subscriptions import (
    get_premium_price,
    get_tier,
    get_usage_count,
    increment_counter,
    register_user,
    set_premium as _set_premium_fn,
)
from src.wallet_setup import generate_wallet, generate_solana_wallet
from src.yield_scanner import YieldScanner

load_env()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CR_API_KEY = os.getenv("CRYPTORANK_API_KEY")
OWNER_ID = os.getenv("TELEGRAM_OWNER_ID", "")

FREE_LIMIT = 3
DEFAULT_SYMBOLS = ["BTC", "ETH", "SOL"]

PROMO_TEXT = (
    "Want instant alerts, expanded data, and reports every 6 hours?\n"
    f"Upgrade to Premium for ${get_premium_price():.2f}/month.\n"
    "/upgrade for details."
)

START_TEXT = (
    "GETIN Farming Agent — earn from $0 with sweat equity.\n\n"
    "Quest Commands:\n"
    "/quests — All available quests\n"
    "/quests beginner — $0 cost quests\n"
    "/quest S1 — Step-by-step guide\n"
    "/complete S1 — Mark done, earn rewards\n"
    "/earnings — Your total + ROI projection\n\n"
    "Market Commands:\n"
    "/yield — Live DeFi yields (ETH + SOL)\n"
    "/market — Global crypto market snapshot\n"
    "/prices BTC ETH SOL — Live prices\n"
    "/activities — 149 farming activities\n\n"
    "Wallet & Setup:\n"
    "/wallet — Generate ETH wallet\n"
    "/solana_wallet — Generate Solana wallet\n"
    "/subscribe — Daily reports (9am UTC)\n"
    "/upgrade — Premium subscription\n"
    "/help — This message"
)


def _format_yield_table(pools: List[Dict[str, Any]], free: bool = True) -> str:
    """Format yield scan output as a Telegram-friendly table."""
    scanner = YieldScanner()
    lines = []
    header = f"{'Protocol':<22} {'APY':>7}  {'6h':>8} {'30d':>8}"
    sep = "-" * 50
    lines.append(f"<pre>{header}\n{sep}")

    for i, p in enumerate(pools):
        if free and i >= FREE_LIMIT:
            break
        roi = scanner.calculate_roi(p["apy"])
        lines.append(
            f"{p['label']:<22} "
            f"{p['apy']:>6.2f}% "
            f"${roi['roi_6h_usd']:>6.4f} "
            f"${roi['roi_30d_usd']:>6.2f}"
        )

    if free and len(pools) > FREE_LIMIT:
        lines.append(f"\n({len(pools) - FREE_LIMIT} more pools hidden. /upgrade to unlock)")

    lines.append("</pre>")
    lines.append("ROI per $1000 invested. Rates from DefiLlama.")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message on /start."""
    user = update.effective_user
    register_user(user.id, user.username or "")
    await update.message.reply_text(START_TEXT)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the command list."""
    await update.message.reply_text(START_TEXT)


async def yield_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scan live DeFi yields and show top pools."""
    user = update.effective_user
    tier = get_tier(user.id)
    is_free = tier != "premium"

    if is_free:
        count = get_usage_count(user.id)
        if count >= 10:
            await update.message.reply_text(
                "Free tier limit reached (10 scans). /upgrade to continue."
            )
            return

    msg = await update.message.reply_text("Scanning live DeFi yields...")

    try:
        scanner = YieldScanner()
        pools = scanner.scan()
        if not pools:
            await msg.edit_text("Could not fetch yield data. Try again later.")
            return

        text = _format_yield_table(pools, free=is_free)
        if is_free:
            increment_counter(user.id)
            text += f"\n\nFree scans remaining: {10 - get_usage_count(user.id)}"
        else:
            text += "\n\nPremium tier — all pools shown."

        await msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as exc:
        await msg.edit_text(f"Yield scan failed: {exc}")


async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the global crypto market snapshot."""
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
    """Show live prices for chosen symbols."""
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
    """Generate a new ETH wallet."""
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("Use /wallet in a private chat for security.")
        return

    name = context.args[0] if context.args else "tg_wallet"
    try:
        addr = generate_wallet(name)
        await update.message.reply_text(
            f"ETH wallet generated: <code>{addr}</code>\n"
            f"Key saved to wallets/{name}.env\n\n"
            "Send minimal gas tokens to this address. Never fund it with real assets.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        await update.message.reply_text(f"Wallet generation failed: {exc}")


async def solana_wallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a new Solana wallet."""
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("Use /solana_wallet in a private chat for security.")
        return

    name = context.args[0] if context.args else "tg_solana"
    try:
        addr = generate_solana_wallet(name)
        await update.message.reply_text(
            f"Solana wallet generated: <code>{addr}</code>\n"
            f"Key saved to wallets/{name}.env\n\n"
            "Import into Phantom or Solflare. Use for testnet/devnet only.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        await update.message.reply_text(f"Wallet generation failed: {exc}")


async def activities_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Summarize testnet farming activities."""
    text = (
        "<b>Testnet Farming — 149 activities across 4 chains</b>\n\n"
        "<b>Monad</b> — 78 activities (34 DEXes, 9 staking, 5 lending, 6 NFTs, 6 daily)\n"
        "<b>Berachain</b> — 41 activities (BEX, Bend, Berps, Honey, BGT Station)\n"
        "<b>Somnia</b> — 12 activities (Quest portal, Stargate bridge)\n"
        "<b>Solana Devnet</b> — 18 activities (zero-capital strategy)\n\n"
        "Full details: config/testnet_activities.yaml\n"
        "Or run locally: python -m src.main --activities"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def upgrade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show premium subscription details."""
    price = get_premium_price()
    text = (
        f"<b>GETIN Premium — ${price:.2f}/month</b>\n\n"
        "Premium features:\n"
        "• All 17 yield pools shown (free: 3)\n"
        "• Unlimited price lookups\n"
        "• Auto-reports every 6 hours\n"
        "• TGE alerts pushed to Telegram\n"
        "• Priority support\n\n"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    # Admin can upgrade users
    if str(update.effective_user.id) == OWNER_ID:
        await update.message.reply_text(
            "Admin: reply with /set_premium USER_ID to upgrade a user."
        )


async def set_premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to upgrade a user to premium."""
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text("Admin only.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /set_premium USER_ID")
        return
    uid = int(context.args[0])
    _set_premium_fn(uid)
    await update.message.reply_text(f"User {uid} upgraded to premium.")


async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Subscribe the current chat to daily free reports."""
    chat_id = update.effective_chat.id
    subscribe_chat(chat_id)
    await update.message.reply_text(
        "Subscribed to daily reports (9:00 AM UTC).\n"
        "/unsubscribe to stop.\n"
        "/upgrade for 6-hour premium reports."
    )


async def unsubscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unsubscribe the current chat from daily reports."""
    chat_id = update.effective_chat.id
    unsubscribe_chat(chat_id)
    await update.message.reply_text("Unsubscribed from daily reports.")


async def quests_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show available quests filtered by category."""
    user = update.effective_user
    tracker = QuestTracker(user.id)
    category = context.args[0] if context.args else None
    quests = tracker.get_quests(category)

    if not quests:
        await update.message.reply_text("No quests found. Try /quests beginner")
        return

    lines = ["<b>Available Quests</b>", ""]
    cats = {}
    for q in quests:
        cats.setdefault(q["category"], []).append(q)

    for cat, qlist in cats.items():
        lines.append(f"<b>{cat.upper()} — {len(qlist)} quests</b>")
        for q in qlist:
            status = "DONE" if q["completed"] else f"${q['reward']} {q['reward_token']}"
            lines.append(
                f"  /quest {q['id']} | {q['title'][:40]} | {status} | {q['estimated_minutes']}min"
            )
        lines.append("")

    lines.append("Usage: /quest S1 for details. /complete S1 to mark done.")
    lines.append("Filter: /quests beginner | /quests intermediate | /quests advanced")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def quest_detail_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show step-by-step instructions for a specific quest."""
    if not context.args:
        await update.message.reply_text("Usage: /quest S1\nUse /quests to see available IDs.")
        return

    quest_id = context.args[0].upper()
    user = update.effective_user
    tracker = QuestTracker(user.id)
    quests = tracker.get_quests()
    quest = next((q for q in quests if q["id"] == quest_id), None)

    if not quest:
        await update.message.reply_text("Quest not found. Use /quests to list them.")
        return

    status = " COMPLETED" if quest["completed"] else ""
    lines = [
        f"<b>{quest['title']}</b>{status}",
        f"Platform: {quest['platform']} | Difficulty: {quest['difficulty']}",
        f"Reward: ${quest['reward']} {quest['reward_token']}",
        f"Time: ~{quest['estimated_minutes']} minutes | Cost: ${quest['cost']}",
        "",
        f"<b>Steps:</b>",
    ]
    for i, step in enumerate(quest["steps"], 1):
        lines.append(f"  {i}. {step}")
    lines.append("")
    lines.append(f"URL: {quest['url']}")
    lines.append(f"Requires: {', '.join(quest['requires'])}")
    lines.append("")
    if not quest["completed"]:
        lines.append("Complete this quest? Send: /complete " + quest_id)
    else:
        lines.append("Quest completed. Check your earnings: /earnings")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def complete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mark a quest as completed and add its reward to earnings."""
    if not context.args:
        await update.message.reply_text("Usage: /complete S1")
        return

    quest_id = context.args[0].upper()
    user = update.effective_user
    tracker = QuestTracker(user.id)
    result = tracker.complete_quest(quest_id)

    if not result["ok"]:
        await update.message.reply_text(result["error"])
        return

    await update.message.reply_text(
        f"Quest completed: {result['quest']}\n"
        f"+${result['reward']} {result['token']}\n"
        f"Total earned: ${result['total_earned']:.2f}\n\n"
        f"/quests for more. /earnings for full report."
    )


async def earnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the user's accumulated quest earnings and 6h/30d projections."""
    user = update.effective_user
    tracker = QuestTracker(user.id)
    data = tracker.get_earnings()

    if data["quests_completed"] == 0:
        await update.message.reply_text(
            "No earnings yet. Start with /quests beginner\n"
            "Every quest is $0 cost — just sweat equity."
        )
        return

    lines = [
        "<b>Your Sweat Equity Earnings</b>",
        f"Quests completed: {data['quests_completed']}",
        f"Total earned: ${data['total_usd']:.2f}",
        "",
        "<b>By token:</b>",
    ]
    for token, amount in sorted(data["by_token"].items(), key=lambda x: -x[1]):
        lines.append(f"  {token}: ${amount:.2f}")

    lines.append("")
    lines.append("<b>Recent completions:</b>")
    for q in data["quests"][-5:]:
        lines.append(f"  {q['id']} — {q['title']} — +${q['reward']} {q['token']}")

    # ROI projection if deployed
    if data["total_usd"] >= 5.0:
        from src.yield_scanner import YieldScanner
        scanner = YieldScanner()
        roi = scanner.calculate_roi(7.83, data["total_usd"])
        lines.append("")
        lines.append("<b>If deployed at 7.83% APY (Orca SOL/USDC):</b>")
        lines.append(f"  6h return: ${roi['roi_6h_usd']:.4f}")
        lines.append(f"  30d return: ${roi['roi_30d_usd']:.2f}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


def build_app() -> Application:
    """Create and configure the Telegram bot application."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("yield", yield_cmd))
    app.add_handler(CommandHandler("market", market_cmd))
    app.add_handler(CommandHandler("prices", prices_cmd))
    app.add_handler(CommandHandler("wallet", wallet_cmd))
    app.add_handler(CommandHandler("solana_wallet", solana_wallet_cmd))
    app.add_handler(CommandHandler("activities", activities_cmd))
    app.add_handler(CommandHandler("upgrade", upgrade_cmd))
    app.add_handler(CommandHandler("set_premium", set_premium_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_cmd))
    app.add_handler(CommandHandler("quests", quests_cmd))
    app.add_handler(CommandHandler("quest", quest_detail_cmd))
    app.add_handler(CommandHandler("complete", complete_cmd))
    app.add_handler(CommandHandler("earnings", earnings_cmd))

    return app


def run_bot() -> None:
    """Start the Telegram bot in polling mode."""
    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN is missing. Set it in .env")
        return

    app = build_app()

    from src.reporter import install_scheduler
    install_scheduler(app)

    print(f"GETIN Telegram bot starting...")
    print(f"Token loaded: {'yes' if BOT_TOKEN else 'no'}")
    print(f"CryptoRank key loaded: {'yes' if CR_API_KEY else 'no'}")
    print(f"Auto-reporter scheduler active")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run(app))
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        loop.close()


async def _run(app: Application) -> None:
    """Initialize and run the bot with graceful shutdown."""
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