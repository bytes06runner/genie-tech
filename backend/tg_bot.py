"""
tg_bot.py — X10V Autonomous Telegram Trading Bot
====================================================
Main entry point. Bridges Telegram commands to the Gemini AI Swarm,
Paper Trading Engine, Algorand Wallet, and Async Market Monitor.

Commands:
  /start                — Initialise user profile ($1,000 demo balance)
  /connect_wallet       — Generate & link an Algorand Testnet wallet
  /analyze <asset>      — Trigger swarm analysis on any asset
  /portfolio            — View balance, open positions, active monitors
  /close <position_id>  — Close an open paper trade
  /monitors             — List active price monitors
  /cancel <job_id>      — Cancel an active price monitor
  /help                 — Show all commands

Architecture:
  python-telegram-bot v20+ (async) → swarm_brain.py → paper_engine.py
  APScheduler market_monitor.py runs autonomously in the background.
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional

from dotenv import load_dotenv
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from paper_engine import (
    create_user,
    get_balance,
    get_user,
    link_wallet,
    disconnect_wallet,
    open_position,
    close_position,
    get_open_positions,
    get_all_positions,
)
from market_monitor import (
    create_monitor,
    get_user_monitors,
    cancel_monitor,
    start_monitor_scheduler,
    set_tg_notify,
    fetch_current_price,
)
from swarm_brain import run_swarm
from memory_manager import log_memory

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("tg_bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://x10v-webapp.vercel.app")
DEFAULT_ALLOCATION = 100.0


async def tg_notify(tg_user_id: int, message: str):
    """Send a push notification to a user via Telegram. Used by market_monitor."""
    try:
        from telegram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=tg_user_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error("Failed to send TG notification to %d: %s", tg_user_id, e)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start — register user with $1,000 demo balance."""
    tg_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or ""

    user = await create_user(tg_id, username)
    is_new = user.get("is_new", False)

    if is_new:
        text = (
            "🚀 *Welcome to X10V Autonomous Trading Bot*\n\n"
            f"Hey {username}! Your profile is live.\n\n"
            "💰 *Demo Balance:* `$1,000.00`\n"
            "🔗 *Wallet:* Not connected\n\n"
            "Get started:\n"
            "• `/analyze XAU/USD` — AI Swarm analysis\n"
            "• `/connect_wallet` — Link Algorand Testnet\n"
            "• `/portfolio` — View your positions\n"
            "• `/help` — All commands"
        )
    else:
        balance = user.get("balance", 0)
        wallet = "✅ Connected" if user.get("algo_address") else "❌ Not connected"
        text = (
            "👋 *Welcome back to X10V!*\n\n"
            f"💰 *Balance:* `${balance:.2f}`\n"
            f"🔗 *Wallet:* {wallet}\n\n"
            "Use `/help` to see all commands."
        )

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    log_memory("TelegramBot", f"/start by user {tg_id} ({username})")


async def cmd_connect_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /connect_wallet — open Mini App for real Lute Wallet connection."""
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first to create your profile.", parse_mode=ParseMode.MARKDOWN)
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="🔗 Connect Lute Wallet",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )],
    ])

    if user.get("algo_address"):
        await update.message.reply_text(
            f"🔗 *Current Wallet*\n\n"
            f"Address: `{user['algo_address']}`\n\n"
            f"Tap below to *update* to a different Lute wallet, "
            f"or use `/disconnect` to remove it entirely.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            "🔗 *Connect Your Algorand Wallet*\n\n"
            "Tap below to open the Web3 Bridge.\n"
            "Connect your *Lute Wallet* and your real TestNet address "
            "will be linked automatically.\n\n"
            "_Make sure the Lute browser extension is installed and set to TestNet._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
    log_memory("TelegramBot", f"/connect_wallet (Mini App) by user {tg_id}")


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive real wallet address from the Telegram Mini App via web_app_data."""
    tg_id = update.effective_user.id
    raw_data = update.effective_message.web_app_data.data

    try:
        payload = json.loads(raw_data)
        address = payload.get("address", "").strip()
    except (json.JSONDecodeError, AttributeError):
        address = raw_data.strip()

    if not address or len(address) < 20:
        await update.message.reply_text("⚠️ Invalid wallet address received from Mini App.")
        return

    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    await link_wallet(tg_id, address, "lute-external-wallet")

    await update.message.reply_text(
        f"✅ *Successfully connected real wallet!*\n\n"
        f"📬 *Address:*\n`{address}`\n\n"
        f"💧 *Fund it:* [Algorand Testnet Dispenser](https://bank.testnet.algorand.network/)\n\n"
        f"_Your Lute Wallet is now linked to X10V. Use `/portfolio` to check your status._",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )
    log_memory("TelegramBot", f"Real wallet connected via Mini App for user {tg_id}: {address[:16]}…")


async def cmd_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /disconnect — wipe saved wallet address so user can start fresh."""
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    if not user.get("algo_address"):
        await update.message.reply_text(
            "ℹ️ No wallet is currently connected.\n\n"
            "Use `/connect_wallet` to link one.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    old_address = user["algo_address"]
    await disconnect_wallet(tg_id)

    await update.message.reply_text(
        f"🔓 *Wallet Disconnected*\n\n"
        f"Removed: `{old_address}`\n\n"
        f"Use `/connect_wallet` to link a new Lute wallet.",
        parse_mode=ParseMode.MARKDOWN,
    )
    log_memory("TelegramBot", f"/disconnect by user {tg_id}, removed {old_address[:16]}…")


async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /analyze <asset> — trigger AI Swarm analysis."""
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    if not context.args:
        await update.message.reply_text(
            "📊 *Usage:* `/analyze <asset>`\n\n"
            "Examples:\n"
            "• `/analyze XAU/USD`\n"
            "• `/analyze RELIANCE`\n"
            "• `/analyze BTC`\n"
            "• `/analyze AAPL`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    asset = " ".join(context.args).upper()
    await update.message.reply_text(
        f"🧠 *X10V Swarm Activated*\n\n"
        f"Analyzing `{asset}` …\n"
        f"_Alpha → Beta → Gamma pipeline running_",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        input_text = f"Analyze {asset} — provide current price, trend analysis, support/resistance levels, and a clear trading recommendation."
        verdict = await run_swarm(
            text_data=input_text,
            user_command=f"Analyze {asset} for trading",
        )

        sd = verdict.get("structured_data", {})
        summary = sd.get("summary", "No summary generated.")
        metrics = sd.get("timeline_or_metrics", [])
        decision = verdict.get("decision", "inform")
        domain = verdict.get("domain", "general")
        reasoning = verdict.get("reasoning", "")

        metrics_text = ""
        for m in metrics[:10]:
            key = m.get("key", "?")
            val = m.get("value", "?")
            metrics_text += f"  • *{key}:* {val}\n"

        decision_emoji = {"inform": "📋", "execute": "✅", "abort": "🛑"}.get(decision, "❓")
        response = (
            f"📊 *X10V Swarm Verdict — {asset}*\n\n"
            f"🏷️ Domain: `{domain}` | Decision: {decision_emoji} `{decision}`\n\n"
            f"📝 *Summary:*\n{summary}\n\n"
        )
        if metrics_text:
            response += f"📈 *Key Metrics:*\n{metrics_text}\n"
        if reasoning:
            response += f"🧠 *Reasoning:* _{reasoning[:200]}_\n\n"

        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

        trade_decision = verdict.get("trade_decision", decision)
        target_price = verdict.get("target_entry_price")
        asset_ticker = verdict.get("asset_ticker", asset)

        if trade_decision == "monitor_and_execute" and target_price:
            balance = await get_balance(tg_id)
            alloc = min(DEFAULT_ALLOCATION, balance or 0)
            if alloc > 0:
                job_id = create_monitor(
                    asset=asset_ticker,
                    target_price=float(target_price),
                    allocation_usd=alloc,
                    tg_user_id=tg_id,
                    direction="below",
                )
                await update.message.reply_text(
                    f"📡 *Auto-Monitor Created*\n\n"
                    f"Asset: `{asset_ticker}`\n"
                    f"Target: `${float(target_price):.2f}`\n"
                    f"Allocation: `${alloc:.2f}`\n"
                    f"Check Interval: Every 5 min\n"
                    f"Job ID: `{job_id}`\n\n"
                    f"_I'll auto-execute the trade and notify you when the price hits target._",
                    parse_mode=ParseMode.MARKDOWN,
                )

        elif trade_decision == "execute_now":
            current_price = await fetch_current_price(asset_ticker)
            if current_price:
                balance = await get_balance(tg_id)
                alloc = min(DEFAULT_ALLOCATION, balance or 0)
                if alloc > 0:
                    try:
                        pos = await open_position(tg_id, asset_ticker, alloc, current_price)
                        await update.message.reply_text(
                            f"✅ *Trade Executed!*\n\n"
                            f"Asset: `{asset_ticker}`\n"
                            f"Entry: `${current_price:.2f}`\n"
                            f"Allocated: `${alloc:.2f}`\n"
                            f"Position ID: `{pos['id']}`\n\n"
                            f"Use `/close {pos['id']}` to close.",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except ValueError as e:
                        await update.message.reply_text(f"⚠️ Trade failed: {e}")

    except Exception as e:
        logger.error("Swarm analysis failed for %s: %s", asset, e)
        await update.message.reply_text(f"⚠️ Analysis failed: {str(e)[:200]}")

    log_memory("TelegramBot", f"/analyze {asset} by user {tg_id}")


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /portfolio — show balance + positions + monitors."""
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    balance = user.get("balance", 0)
    wallet = user.get("algo_address")
    positions = await get_open_positions(tg_id)
    monitors = get_user_monitors(tg_id)
    all_positions = await get_all_positions(tg_id)
    closed = [p for p in all_positions if p["status"] == "closed"]

    text = (
        f"💼 *X10V Portfolio*\n\n"
        f"💰 *Balance:* `${balance:.2f}`\n"
        f"🔗 *Wallet:* `{wallet[:16]}…`\n\n" if wallet else
        f"💼 *X10V Portfolio*\n\n"
        f"💰 *Balance:* `${balance:.2f}`\n"
        f"🔗 *Wallet:* Not connected\n\n"
    )

    if positions:
        text += f"📈 *Open Positions ({len(positions)}):*\n"
        for p in positions:
            text += (
                f"  • `{p['asset']}` — ${p['amount_usd']:.2f} @ ${p['entry_price']:.2f}\n"
                f"    ID: `{p['id']}` | Opened: {p['opened_at'][:10]}\n"
            )
        text += "\n"
    else:
        text += "📈 *Open Positions:* None\n\n"

    if monitors:
        text += f"📡 *Active Monitors ({len(monitors)}):*\n"
        for m in monitors:
            text += f"  • `{m['asset']}` target $`{m['target_price']:.2f}` — Job: `{m['job_id']}`\n"
        text += "\n"

    if closed:
        total_pnl = sum(p.get("pnl", 0) for p in closed)
        emoji = "🟢" if total_pnl >= 0 else "🔴"
        text += f"📊 *Closed Trades:* {len(closed)} | {emoji} Total PnL: `${total_pnl:+.2f}`\n"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /close <position_id> — close a paper trade."""
    tg_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "📊 *Usage:* `/close <position_id>`\n\nFind your position ID with `/portfolio`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    pos_id = context.args[0]
    positions = await get_open_positions(tg_id)
    target = next((p for p in positions if p["id"] == pos_id), None)

    if not target:
        await update.message.reply_text(f"⚠️ No open position with ID `{pos_id}`.", parse_mode=ParseMode.MARKDOWN)
        return

    asset = target["asset"]
    await update.message.reply_text(f"🔄 Fetching current price for `{asset}` …", parse_mode=ParseMode.MARKDOWN)

    current_price = await fetch_current_price(asset)
    if current_price is None:
        await update.message.reply_text(f"⚠️ Could not fetch current price for `{asset}`. Try again later.")
        return

    try:
        result = await close_position(tg_id, pos_id, current_price)
        pnl = result.get("pnl", 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        await update.message.reply_text(
            f"✅ *Position Closed*\n\n"
            f"Asset: `{asset}`\n"
            f"Entry: `${result['entry_price']:.2f}` → Exit: `${current_price:.2f}`\n"
            f"{emoji} PnL: `${pnl:+.2f}`\n\n"
            f"Updated balance in `/portfolio`.",
            parse_mode=ParseMode.MARKDOWN,
        )
    except ValueError as e:
        await update.message.reply_text(f"⚠️ {e}")


async def cmd_monitors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /monitors — list active price monitors."""
    tg_id = update.effective_user.id
    monitors = get_user_monitors(tg_id)

    if not monitors:
        await update.message.reply_text("📡 No active price monitors. Use `/analyze` to create one.", parse_mode=ParseMode.MARKDOWN)
        return

    text = f"📡 *Active Price Monitors ({len(monitors)}):*\n\n"
    for m in monitors:
        text += (
            f"• `{m['asset']}` → Target: `${m['target_price']:.2f}`\n"
            f"  Allocation: `${m['allocation_usd']:.2f}` | Dir: {m['direction']}\n"
            f"  Job: `{m['job_id']}` | Since: {m['created_at'][:10]}\n\n"
        )
    text += "Cancel with `/cancel <job_id>`"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /cancel <job_id> — cancel a price monitor."""
    if not context.args:
        await update.message.reply_text("📡 *Usage:* `/cancel <job_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    job_id = context.args[0]
    success = cancel_monitor(job_id)
    if success:
        await update.message.reply_text(f"✅ Monitor `{job_id}` cancelled.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"⚠️ No active monitor with ID `{job_id}`.", parse_mode=ParseMode.MARKDOWN)


async def cmd_transact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /transact — open the Telegram Mini App for Algorand Web3 transactions."""
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="⚡ Open Algorand Bridge",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )],
    ])

    await update.message.reply_text(
        "🌐 *X10V Web3 Bridge*\n\n"
        "Tap below to open the Algorand Mini App.\n"
        "Connect your *Lute Wallet*, view your TestNet balance, "
        "and sign transactions — all inside Telegram.\n\n"
        "_Powered by Algorand TestNet + Lute Wallet_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )
    log_memory("TelegramBot", f"/transact by user {tg_id}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /help — show all available commands."""
    text = (
        "🤖 *X10V Autonomous Trading Bot*\n\n"
        "*Commands:*\n"
        "  /start — Create profile ($1,000 demo)\n"
        "  /connect\\_wallet — Connect Lute wallet via Mini App\n"
        "  /disconnect — Remove linked wallet\n"
        "  /analyze `<asset>` — AI Swarm analysis\n"
        "  /transact — Open Web3 Bridge (Lute Wallet)\n"
        "  /portfolio — Balance & positions\n"
        "  /close `<id>` — Close a paper trade\n"
        "  /monitors — Active price watchers\n"
        "  /cancel `<job_id>` — Stop a monitor\n"
        "  /help — This message\n\n"
        "*How it works:*\n"
        "1️⃣ `/analyze XAU/USD` triggers the Gemini AI Swarm\n"
        "2️⃣ If the swarm says 'monitor\\_and\\_execute', a background job watches the price every 5 min\n"
        "3️⃣ When the target is hit, the bot auto-executes a paper trade and DMs you\n"
        "4️⃣ `/transact` opens the Web3 Mini App for real Algorand TestNet transactions\n\n"
        "_Powered by Gemini 2.5 Flash + Groq + Algorand + Lute_"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text messages — route them through the swarm."""
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Send `/start` first!", parse_mode=ParseMode.MARKDOWN)
        return

    text = update.message.text
    await update.message.reply_text("🧠 _Processing with AI Swarm …_", parse_mode=ParseMode.MARKDOWN)

    try:
        verdict = await run_swarm(text_data=text, user_command=text)
        sd = verdict.get("structured_data", {})
        summary = sd.get("summary", "No summary.")
        decision = verdict.get("decision", "inform")
        await update.message.reply_text(
            f"📋 *Swarm Says:* `{decision}`\n\n{summary}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)[:200]}")


async def post_init(application):
    """Set bot commands in the Telegram UI menu."""
    commands = [
        BotCommand("start", "Create profile ($1,000 demo)"),
        BotCommand("connect_wallet", "Connect Lute wallet via Mini App"),
        BotCommand("disconnect", "Remove linked wallet"),
        BotCommand("analyze", "AI Swarm analysis on any asset"),
        BotCommand("transact", "Open Algorand Web3 Bridge"),
        BotCommand("portfolio", "View balance & positions"),
        BotCommand("close", "Close a paper trade"),
        BotCommand("monitors", "List active price monitors"),
        BotCommand("cancel", "Cancel a price monitor"),
        BotCommand("help", "Show all commands"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Bot commands registered in Telegram UI")


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set in .env — exiting.")
        return

    set_tg_notify(tg_notify)
    start_monitor_scheduler()

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("connect_wallet", cmd_connect_wallet))
    app.add_handler(CommandHandler("disconnect", cmd_disconnect))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("transact", cmd_transact))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("close", cmd_close))
    app.add_handler(CommandHandler("monitors", cmd_monitors))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("=" * 60)
    logger.info("  X10V Telegram Bot — Starting polling")
    logger.info("=" * 60)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
