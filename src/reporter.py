import asyncio
import json
import os
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot
from telegram.error import TelegramError

from src.cryptorank_client import CryptoRankClient
from src.subscriptions import _load_subscribers
from src.yield_scanner import YieldScanner

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CR_API_KEY = os.getenv("CRYPTORANK_API_KEY")
REPORT_CHATS_FILE = "report_chats.json"


def _load_report_chats() -> list[int]:
    """Load the list of chat IDs that get auto-reports."""
    try:
        with open(REPORT_CHATS_FILE, "r") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return []


def _save_report_chats(chat_ids: list[int]) -> None:
    """Persist the auto-report chat list."""
    with open(REPORT_CHATS_FILE, "w") as fh:
        json.dump(chat_ids, fh)


async def premium_report_job(bot: Bot) -> None:
    """Send yield and market snapshots to premium subscribers."""
    subs = _load_subscribers()
    premium_ids = [
        int(uid) for uid, data in subs.get("users", {}).items()
        if data.get("tier") == "premium"
    ]
    if not premium_ids:
        return
    try:
        scanner = YieldScanner()
        pools = scanner.scan()
        if not pools:
            return
        lines = ["<b>GETIN Auto-Report (6h)</b>", f"<pre>{'Protocol':<22} {'APY':>7}</pre>"]
        for p in pools:
            lines.append(f"<pre>{p['label']:<22} {p['apy']:>6.2f}%</pre>")

        if CR_API_KEY:
            client = CryptoRankClient(CR_API_KEY)
            snap = client.get_global_snapshot()
            d = snap.get("data", {})
            lines.append(
                f"\nMCap: ${float(d.get('totalMarketCap',0)):,.0f}  "
                f"24h Vol: ${float(d.get('totalVolume24h',0)):,.0f}"
            )

        lines.append(f"\n{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

        for cid in premium_ids:
            try:
                await bot.send_message(cid, "\n".join(lines), parse_mode="HTML")
            except TelegramError:
                pass
    except Exception:
        pass


async def daily_free_report_job(bot: Bot) -> None:
    """Send a once-daily report to all subscribed chats."""
    chat_ids = _load_report_chats()
    if not chat_ids:
        return
    try:
        scanner = YieldScanner()
        pools = scanner.scan()
        if not pools:
            return
        lines = [
            "<b>GETIN Daily Report</b>",
            f"<pre>{'Protocol':<22} {'APY':>7} {'30d ROI':>10}</pre>",
        ]
        for p in pools[:5]:
            roi = scanner.calculate_roi(p["apy"])
            lines.append(
                f"<pre>{p['label']:<22} {p['apy']:>6.2f}% ${roi['roi_30d_usd']:>8.2f}</pre>"
            )
        lines.append("\n/subscribe to receive these daily.")
        lines.append("/upgrade for 6-hour premium reports.")
        for cid in chat_ids:
            try:
                await bot.send_message(cid, "\n".join(lines), parse_mode="HTML")
            except TelegramError:
                pass
    except Exception:
        pass


def install_scheduler(application: "Application") -> None:
    """Attach the scheduler to the bot's event loop via post_init."""
    async def _post_init(app):
        scheduler = AsyncIOScheduler(timezone="UTC")
        bot = app.bot
        scheduler.add_job(
            premium_report_job, "interval", hours=6, args=[bot],
            id="premium_6h",
        )
        scheduler.add_job(
            daily_free_report_job, "cron", hour=9, minute=0, args=[bot],
            id="daily_free",
        )
        scheduler.start()

    application.post_init = _post_init


def subscribe_chat(chat_id: int) -> None:
    """Add a chat to the daily free report list."""
    chats = _load_report_chats()
    if chat_id not in chats:
        chats.append(chat_id)
        _save_report_chats(chats)


def unsubscribe_chat(chat_id: int) -> None:
    """Remove a chat from the daily free report list."""
    chats = _load_report_chats()
    if chat_id in chats:
        chats.remove(chat_id)
        _save_report_chats(chats)