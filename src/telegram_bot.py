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
from src.ai_content_generator import AIContentGenerator
from src.ai_quest_runner import AIQuestRunner
from src.referrals import get_referral_link, get_referral_stats, record_referral
from src.twitter_connector import TwitterConnector
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
from src.safety_guard import SafetyGuard
from src.portfolio_manager import PortfolioManager
from src.harvester import YieldHarvester

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
    "GETIN Yield Farming Agent — DeFi yield scanner and demo tracker.\n\n"
    "Real Yield Commands (uses YOUR funds on mainnet):\n"
    "/invest STRATEGY GBP — Buy crypto, withdraw, deposit into yield\n"
    "/harvest — Claim accrued yield from active positions\n"
    "/positions — Show your yield positions\n"
    "/unwind — Exit all protocols back to wallet\n"
    "/safety — Show safety limits and dry-run status\n\n"
    "Demo Quest Tracker (LOCAL only — no real tokens earned):\n"
    "/quests — Browse quest descriptions\n"
    "/quest S1 — Step-by-step guide reference\n"
    "/complete S1 — Track locally (simulated)\n"
    "/earnings — Tracking summary (no real value)\n"
    "/auto_quest — Demo sweep (local JSON only)\n\n"
    "Market Data:\n"
    "/yield — Live DeFi yields from DefiLlama\n"
    "/market — Global crypto market snapshot\n"
    "/prices BTC ETH SOL — Live prices\n"
    "/activities — 149 farming activities reference\n\n"
    "Wallet & Setup:\n"
    "/wallet — Generate ETH wallet\n"
    "/solana_wallet — Generate Solana wallet\n"
    "/subscribe — Daily reports (9am UTC)\n"
    "/upgrade — Premium details\n"
    "/share — Share with friends\n"
    "/help — This message\n\n"
    "DRY_RUN is ON by default. No real transactions sent unless disabled."
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
    """Send a welcome message and track referrals on /start."""
    user = update.effective_user
    register_user(user.id, user.username or "")
    if context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0].split("_")[1])
            record_referral(referrer_id, user.id, user.username or "")
        except Exception:
            pass
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
        f"<b>GETIN Premium</b>\n\n"
        f"Premium features (available by operator invitation):\n"
        "• All yield pools shown (free: top 3)\n"
        "• Unlimited price lookups\n"
        "• Auto-reports at 6-hour intervals\n"
        "• TGE alerts pushed to Telegram\n"
        "• Priority support\n\n"
        "Note: Premium access is granted by the bot operator.\n"
        "No automated payment gateway is currently active.\n"
        "Contact the operator directly to request premium access."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

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
    """Mark a quest as completed (LOCAL TRACKING ONLY — no real tokens earned)."""
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
        f"Quest tracked: {result['quest']}\n"
        f"{result['token']}\n\n"
        f"IMPORTANT: Quest completions are LOCAL TRACKING only.\n"
        f"No real tokens are earned. No platforms are contacted.\n"
        f"Actual rewards require manual completion on each platform.\n\n"
        f"/quests for more. /earnings for full report."
    )


async def earnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display quest tracking summary (LOCAL TRACKING ONLY — no real earnings)."""
    user = update.effective_user
    tracker = QuestTracker(user.id)
    data = tracker.get_earnings()

    if data["quests_completed"] == 0:
        await update.message.reply_text(
            "No quests tracked yet. Start with /quests beginner\n"
            "Every quest is $0 cost — just sweat equity."
        )
        return

    lines = [
        "<b>Quest Tracking Summary</b>",
        f"Quests tracked: {data['quests_completed']}",
        "",
        "IMPORTANT: All quest completions are LOCAL TRACKING ONLY.",
        "No real tokens have been earned. No platforms were contacted.",
        "Actual rewards require manual completion on each platform.",
        "",
        "To earn real tokens: deploy capital via /invest conservative 100",
        "This buys crypto on exchange, withdraws to your wallet, and",
        "deposits into real DeFi protocols (Aave, Lido, JitoSOL).",
        "",
        "<b>Tracked quests:</b>",
    ]
    for q in data["quests"][-10:]:
        lines.append(f"  {q['id']} — {q['title']} — {q.get('note', '')}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)



async def auto_quest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run local quest tracking demo across testnets, Galxe, and curated quests. No real tokens earned."""
    user = update.effective_user
    msg = await update.message.reply_text('Running AI auto-quest cycle...')

    try:
        runner = AIQuestRunner(user.id)
        results = runner.run_full_cycle()

        curated = results.get('curated', {})
        testnets = results.get('testnets', {})
        galxe = results.get('galxe', {})

        lines = ['<b>AI Auto-Quest Results</b>', '']

        if curated.get('ok'):
            lines.append(f'Curated quests completed: {curated.get("quests_just_completed", 0)}')
            lines.append(f'Total earned from quests: ${curated.get("total_earned", 0):.2f}')
            by_token = ', '.join(f'{k} ${v:.2f}' for k, v in curated.get('by_token', {}).items())
            if by_token:
                lines.append(f'Tokens: {by_token}')
        else:
            lines.append('Curated quests completed already or unavailable.')

        if testnets.get('ok'):
            lines.append(f'')
            lines.append(f'Testnet transactions: {testnets.get("total_txns", 0)}')
            for net, txs in testnets.items():
                if net == 'ok' or net == 'total_txns':
                    continue
                ok_count = sum(1 for t in txs if t.get('ok'))
                lines.append(f'  {net}: {ok_count}/{len(txs)} actions confirmed')
        else:
            error = testnets.get('error', 'Unknown')
            lines.append(f'Testnet farming: {error}')

        if galxe.get('ok'):
            lines.append(f'')
            lines.append(f'Galxe auto-completable quests: {galxe.get("automatable", 0)}')
            lines.append(f'Total active quests scanned: {galxe.get("total_active_quests", 0)}')
        elif galxe.get('error'):
            lines.append(f'Galxe: {galxe["error"]}')

        lines.append('')
        lines.append(
            'IMPORTANT: All auto-quest completions are LOCAL TRACKING ONLY.\n'
            'No real tokens are earned. No platforms are contacted.\n'
            'Actual rewards require manual work on each platform.\n\n'
            'To earn real yield: /invest conservative 100 to deploy\n'
            'actual capital into Aave, Lido, and JitoSOL.'
        )
        lines.append('')
        lines.append('/quests for manual quests. /earnings for full report.')
        await msg.edit_text('\n'.join(lines), parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f'Auto-quest failed: {e}')




async def write_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        msg = (
            "WRITING DRAFT TEMPLATES (REQUIRES HUMAN REWRITING):\n"
            "/write tutorial TOPIC — blog draft\n"
            "/write thread TOPIC — Twitter thread draft\n"
            "/write bug PROJECT VULN SEVERITY — bug report TEMPLATE (DO NOT SUBMIT)\n"
            "/write docs PROJECT PAGETITLE — documentation draft\n"
            "/write quiz TOPIC Q1 Q2 Q3 — study guide (no answers provided)\n\n"
            "CRITICAL: All output is AI-generated DRAFT templates.\n"
            "Do NOT submit to bounty platforms without substantial rewriting.\n"
            "Submitting AI content as your own work violates platform ToS."
        )
        await update.message.reply_text(msg)
        return

    gen = AIContentGenerator()
    content_type = context.args[0].lower()
    rest = ' '.join(context.args[1:]) if len(context.args) > 1 else 'Crypto'

    msg = await update.message.reply_text(f'Generating {content_type} content...')

    if content_type == 'thread':
        result = gen.generate_twitter_thread(rest)
        with open(result['filepath']) as fh:
            preview = fh.read()[:800]
        await msg.edit_text(
            f"<b>Thread: {result['title']}</b>\n"
            f"Tweets: {result['tweet_count']} | Reward: {result['estimated_reward']}\n"
            f"Saved to: {result['filepath']}\n\n"
            f"<pre>{preview}</pre>\n"
            f"/post_twitter to publish. /review for full text.",
            parse_mode=ParseMode.HTML
        )
    elif content_type == 'tutorial':
        result = gen.generate_blog_post(rest)
        with open(result['filepath']) as fh:
            preview = fh.read()[:600]
        await msg.edit_text(
            f"<b>{result['title']}</b>\n"
            f"Words: ~{result['word_count']} | Sections: {result['sections']}\n"
            f"Reward: {result['estimated_reward']}\n\n"
            f"<pre>{preview}</pre>\n\n"
            f"Saved: {result['filepath']}\n"
            f"Review, customize, then submit to Superteam.",
            parse_mode=ParseMode.HTML
        )
    elif content_type == 'bug':
        parts = rest.split(' ', 2)
        project = parts[0] if parts else 'Project'
        vuln = parts[1] if len(parts) > 1 else 'Access Control'
        severity = parts[2] if len(parts) > 2 else 'Medium'
        result = gen.generate_bug_report(project, vuln, severity)
        with open(result['filepath']) as fh:
            preview = fh.read()[:600]
        await msg.edit_text(
            f"<b>{result['title']}</b>\n"
            f"Severity: {result['severity']} | Reward: {result['estimated_reward']}\n\n"
            f"<pre>{preview}</pre>\n\n"
            f"Saved: {result['filepath']}\n"
            f"Verify accuracy before submitting to Immunefi/Superteam.",
            parse_mode=ParseMode.HTML
        )
    elif content_type == 'docs':
        project = rest.split(' ')[0] if rest else 'Project'
        pagetitle = ' '.join(rest.split(' ')[1:]) if ' ' in rest else 'API Reference'
        result = gen.generate_documentation_page(project, pagetitle)
        await msg.edit_text(
            f"<b>{result['title']}</b>\n"
            f"Reward: {result['estimated_reward']}\n"
            f"Saved: {result['filepath']}\n"
            f"Submit as a GitHub PR for Tea Protocol rewards.",
            parse_mode=ParseMode.HTML
        )
    elif content_type == 'quiz':
        gen.generate_quiz_answers(rest, ['Question 1', 'Question 2', 'Question 3'])
        fn = rest.lower().replace(' ', '-')
        await msg.edit_text(
            f"Quiz answers generated for: {rest}\n"
            f"Saved: generated_content/quiz-{fn}.json\n"
            f"Use answers to complete the quiz on the quest platform."
        )
    else:
        await msg.edit_text(
            'Unknown type. Use: tutorial, thread, bug, docs, or quiz.'
        )


async def post_twitter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Post the most recent generated thread to Twitter (REQUIRES CONFIRMATION)."""
    import glob as _glob
    files = sorted(_glob.glob('generated_content/thread-*.txt'), key=os.path.getmtime, reverse=True)
    if not files:
        await update.message.reply_text('No thread found. Use /write thread TOPIC first.')
        return

    msg = await update.message.reply_text(
        '⚠ WARNING: Generated threads contain AI TEMPLATE text.\n'
        'You MUST review and rewrite all content before posting.\n'
        'Posting AI-generated content without substantial rewriting\n'
        'violates Twitter policy and bounty platform ToS.'
    )
    tw = TwitterConnector(update.effective_user.id)

    if not tw.is_connected():
        await msg.edit_text(
            'Twitter not connected. Set these in .env from developer.twitter.com:\n'
            'TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET,\n'
            'TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET,\n'
            'TWITTER_BEARER_TOKEN\n\n'
            'Then restart the bot.'
        )
        return

    with open(files[0]) as fh:
        thread_text = fh.read()

    tweets = [t.strip() for t in thread_text.split('\n\n') if t.strip()]
    if not tweets:
        await msg.edit_text('Thread is empty. Regenerate with /write thread TOPIC.')
        return

    lines = [f'DRAFT thread loaded ({len(tweets)} tweets):\n']
    for i, t in enumerate(tweets[:5], 1):
        lines.append(f'  Tweet {i}: {t[:150]}...')
    lines.append(
        '\n⛔ Automated posting is DISABLED for safety.\n'
        'Generated content contains AI templates that\n'
        'must be substantially rewritten by a human first.\n'
        'Use /review to read the full draft, then\n'
        'post manually through Twitter.com.'
    )
    await msg.edit_text('\n'.join(lines), parse_mode=ParseMode.HTML)


async def review_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show generated content for REVIEW before any submission."""
    import glob as _glob
    files = sorted(_glob.glob('generated_content/*.md') + _glob.glob('generated_content/*.txt') + _glob.glob('generated_content/*.json'), key=os.path.getmtime, reverse=True)
    if not files:
        await update.message.reply_text('No generated content yet. Use /write to create some.')
        return

    await update.message.reply_text(
        f'AI-Generated DRAFT for review: {os.path.basename(files[0])}\n\n'
        'CRITICAL: This is AI-generated TEMPLATE content.\n'
        'Facts, statistics, and code may be FABRICATED.\n'
        'You MUST verify and rewrite before any submission.\n'
        f'Full file at: {files[0]}'
    )

async def share_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a referral link and show the user their referral stats."""
    user = update.effective_user
    link = get_referral_link(user.id)
    stats = get_referral_stats(user.id)
    await update.message.reply_text(
        f"<b>Share GETIN with your network</b>\n\n"
        f"Your referral link:\n<code>{link}</code>\n\n"
        f"Community stats: {stats['total']} referrals, {stats['earned_credits']} credits\n\n"
        f"Premium benefits are granted at the operator's discretion.\n"
        f"Referral credits are community metrics — no monetary value.\n\n"
        f"Share the bot in crypto groups or with friends. "
        f"Anyone who starts with your link is counted.",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


# --- Real Yield Farming Commands ---

async def invest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deploy capital: exchange -> wallet -> yield protocols."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /invest STRATEGY_BUDGET_GBP\n"
            "Example: /invest conservative 100\n"
            "Strategies: conservative, balanced, aggressive_solana"
        )
        return

    strategy = context.args[0]
    try:
        budget = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Budget must be a number (GBP).")
        return

    msg = await update.message.reply_text(
        f"Starting deployment: {strategy} strategy, £{budget} budget...\n"
        f"This may take several minutes (exchange order + withdrawal + on-chain deposits)."
    )

    def _run():
        guard = SafetyGuard()
        pm = PortfolioManager(
            strategy_name=strategy,
            eth_rpc=os.getenv("ETH_RPC_URL"),
            sol_rpc=os.getenv("SOL_RPC_URL"),
            guard=guard,
        )
        pm.run_full_deployment(budget)
        harv = YieldHarvester(
            eth_rpc=os.getenv("ETH_RPC_URL"),
            sol_rpc=os.getenv("SOL_RPC_URL"),
            strategy_name=strategy,
            guard=guard,
        )
        harv.record_baselines()
        return "Deployment complete. Baselines recorded for future harvests."

    try:
        result = await asyncio.to_thread(_run)
        await msg.edit_text(f"<b>Investment Deployed</b>\n{result}")
    except Exception as exc:
        await msg.edit_text(f"Investment failed: {exc}")


async def harvest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Harvest accrued yield from all active positions."""
    msg = await update.message.reply_text("Running harvest cycle across all protocols...")

    def _run():
        harv = YieldHarvester(
            eth_rpc=os.getenv("ETH_RPC_URL"),
            sol_rpc=os.getenv("SOL_RPC_URL"),
            guard=SafetyGuard(),
        )
        return harv.run_harvest()

    try:
        summary = await asyncio.to_thread(_run)
        lines = ["<b>Harvest Results</b>"]
        for protocol, data in summary.items():
            lines.append(f"\n<u>{protocol.upper()}</u>")
            if data.get("ok"):
                results = data.get("results", [])
                for r in results:
                    harvested = "✅" if r.get("harvested") else "⏸"
                    lines.append(
                        f"  {harvested} {r.get('protocol', '')}: yield={r.get('yield', r.get('gain', 0)):.6f}"
                    )
            else:
                lines.append(f"  Error: {data.get('error', 'unknown')}")
        await msg.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)
    except Exception as exc:
        await msg.edit_text(f"Harvest failed: {exc}")


async def positions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current yield positions across chains."""
    strategy = context.args[0] if context.args else "conservative"

    def _run():
        pm = PortfolioManager(
            strategy_name=strategy,
            eth_rpc=os.getenv("ETH_RPC_URL"),
            sol_rpc=os.getenv("SOL_RPC_URL"),
            guard=SafetyGuard(),
        )
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
    """Withdraw all funds from yield protocols back to wallet."""
    msg = await update.message.reply_text(
        "Unwinding all yield positions...\n"
        "This will exit Aave, Lido, JitoSOL, and mSOL."
    )

    def _run():
        from src.chain_clients.ethereum_client import EthereumClient
        from src.chain_clients.solana_client import SolanaClient
        from src.yield_protocols.aave_v3 import AaveV3Client
        from src.yield_protocols.jupiter_solana import JupiterSwap
        from src.safety_guard import SafetyGuard

        guard = SafetyGuard()
        results = []
        eth_rpc = os.getenv("ETH_RPC_URL")
        sol_rpc = os.getenv("SOL_RPC_URL")

        if eth_rpc:
            eth = EthereumClient(eth_rpc, guard=guard)
            aave = AaveV3Client(eth, guard)
            weth = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
            usdc = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
            try:
                tx = aave.withdraw_all(weth)
                results.append(f"Aave WETH withdrawn: {tx[:20]}...")
            except Exception as e:
                results.append(f"Aave WETH: {e}")
            try:
                tx = aave.withdraw_all(usdc)
                results.append(f"Aave USDC withdrawn: {tx[:20]}...")
            except Exception as e:
                results.append(f"Aave USDC: {e}")

        if sol_rpc:
            sol = SolanaClient(sol_rpc, guard=guard)
            jupiter = JupiterSwap(sol, guard)
            for mint_name, mint in (
                ("JitoSOL", "J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn"),
                ("mSOL", "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"),
            ):
                bal = sol.get_token_balance(mint)
                if bal > 0:
                    try:
                        res = jupiter.swap_token_to_sol(mint, int(bal * 1e9))
                        results.append(f"{mint_name} -> SOL: {res['tx'][:20]}...")
                    except Exception as e:
                        results.append(f"{mint_name} unwind failed: {e}")
                else:
                    results.append(f"{mint_name}: no balance")
        return results

    try:
        results = await asyncio.to_thread(_run)
        text = "<b>Unwind Results</b>\n" + "\n".join(f"• {r}" for r in results)
        await msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as exc:
        await msg.edit_text(f"Unwind failed: {exc}")


async def safety_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display current safety guard configuration."""
    guard = SafetyGuard()
    lines = [
        "<b>Safety Guard Status</b>",
        f"DRY_RUN: {'ON' if guard.is_dry_run() else 'OFF'}",
        f"REQUIRE_CONFIRMATION: {'ON' if guard.require_confirmation() else 'OFF'}",
        f"MAX_GAS_GWEI: {guard.get('MAX_GAS_GWEI')}",
        f"MAX_SLIPPAGE_BPS: {guard.get('MAX_SLIPPAGE_BPS')}",
        f"MIN_TRADE_ETH: {guard.get('MIN_TRADE_ETH')}",
        f"MIN_TRADE_SOL: {guard.get('MIN_TRADE_SOL')}",
        "",
        "All transactions respect these limits.",
        "Set in .env and restart bot to change.",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def dryrun_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin toggle for DRY_RUN mode."""
    if str(update.effective_user.id) != OWNER_ID:
        await update.message.reply_text("Admin only.")
        return
    current = os.getenv("DRY_RUN", "true").lower() == "true"
    new_val = "false" if current else "true"
    os.environ["DRY_RUN"] = new_val
    await update.message.reply_text(
        f"DRY_RUN toggled to <b>{new_val.upper()}</b>.\n"
        f"{'Real transactions will now be sent!' if new_val == 'false' else 'No real txs will be sent.'}"
    )


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
    app.add_handler(CommandHandler("share", share_cmd))
    app.add_handler(CommandHandler("upgrade", upgrade_cmd))
    app.add_handler(CommandHandler("set_premium", set_premium_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_cmd))
    app.add_handler(CommandHandler("quests", quests_cmd))
    app.add_handler(CommandHandler("quest", quest_detail_cmd))
    app.add_handler(CommandHandler("complete", complete_cmd))
    app.add_handler(CommandHandler("earnings", earnings_cmd))
    app.add_handler(CommandHandler("auto_quest", auto_quest_cmd))
    app.add_handler(CommandHandler("write", write_cmd))
    app.add_handler(CommandHandler("post_twitter", post_twitter_cmd))
    app.add_handler(CommandHandler("review", review_cmd))

    # Real yield farming handlers
    app.add_handler(CommandHandler("invest", invest_cmd))
    app.add_handler(CommandHandler("harvest", harvest_cmd))
    app.add_handler(CommandHandler("positions", positions_cmd))
    app.add_handler(CommandHandler("unwind", unwind_cmd))
    app.add_handler(CommandHandler("safety", safety_cmd))
    app.add_handler(CommandHandler("dryrun", dryrun_cmd))

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