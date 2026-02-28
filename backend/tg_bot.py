"""
tg_bot.py — X10V Autonomous Telegram Trading Bot
====================================================
Main entry point. Bridges Telegram commands to the Gemini AI Swarm,
Paper Trading Engine, Algorand Wallet, and Async Market Monitor.

Commands:
  /start                — Initialise user profile ($1,000 demo balance)
  /connect_wallet       — Open Mini App to connect Lute Wallet (Web3)
  /disconnect           — Remove linked wallet address
  /reset_wallet         — Alias for /disconnect (force-clear)
  /analyze <asset>      — Trigger swarm analysis on any asset
  /transact             — Open Web3 Bridge for Algorand transactions
  /portfolio            — View balance, open positions, active monitors
  /close <position_id>  — Close an open paper trade
  /monitors             — List active price monitors
  /cancel <job_id>      — Cancel an active price monitor
  /help                 — Show all commands

Architecture:
  python-telegram-bot v20+ (async) → swarm_brain.py → paper_engine.py
  APScheduler market_monitor.py runs autonomously in the background.
  Wallet connection is fully Web3 via Telegram Mini App + Lute Extension.
  Zero backend key generation — no algosdk.account, no mnemonics.
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
from rule_engine import (
    DynamicRuleEngine,
    GrowwMockExecutor,
    evaluate_all_rules,
    set_rule_notify,
    get_smart_suggestions,
)

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("tg_bot")

import time as _time

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://webapp-ten-fawn-33.vercel.app")
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

    connect_url = f"{WEBAPP_URL}?mode=connect&_t={int(_time.time())}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="🔗 Connect Lute Wallet",
            web_app=WebAppInfo(url=connect_url),
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


async def cmd_reset_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /reset_wallet — force-clear wallet regardless of current state."""
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    old_address = user.get("algo_address")
    await disconnect_wallet(tg_id)

    if old_address:
        await update.message.reply_text(
            f"🗑️ *Wallet Force-Reset*\n\n"
            f"Cleared: `{old_address}`\n"
            f"Mnemonic wiped from DB.\n\n"
            f"You're on a clean slate. Use `/connect_wallet` to link your real Lute wallet.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            "✅ *Wallet already clean* — no address stored.\n\n"
            "Use `/connect_wallet` to link your Lute wallet.",
            parse_mode=ParseMode.MARKDOWN,
        )
    log_memory("TelegramBot", f"/reset_wallet by user {tg_id}")

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

    transact_url = f"{WEBAPP_URL}?mode=transact&_t={int(_time.time())}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text="⚡ Open Algorand Bridge",
            web_app=WebAppInfo(url=transact_url),
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
        "  /reset\\_wallet — Force-clear wallet (clean slate)\n"
        "  /analyze `<asset>` — AI Swarm analysis\n"
        "  /transact — Open Web3 Bridge (Lute Wallet)\n"
        "  /portfolio — Balance & positions\n"
        "  /close `<id>` — Close a paper trade\n"
        "  /monitors — Active price watchers\n"
        "  /cancel `<job_id>` — Stop a monitor\n"
        "  /set\\_rule `<rule>` — Create automation rule\n"
        "  /my\\_rules — View all your rules\n"
        "  /delete\\_rule `<id>` — Remove a rule\n"
        "  /suggest — AI-powered smart suggestions\n"
        "  /mock\\_trade `<asset> <amount>` — Execute mock Groww trade\n"
        "  /trade\\_history — View Groww mock trade log\n"
        "  /help — This message\n\n"
        "*How it works:*\n"
        "1️⃣ `/analyze XAU/USD` triggers the Gemini AI Swarm\n"
        "2️⃣ If the swarm says 'monitor\\_and\\_execute', a background job watches the price every 5 min\n"
        "3️⃣ When the target is hit, the bot auto-executes a paper trade and DMs you\n"
        "4️⃣ `/transact` opens the Web3 Mini App for real Algorand TestNet transactions\n"
        "5️⃣ `/set_rule` creates dynamic automation rules evaluated every 60s\n"
        "6️⃣ Voice commands from the web dashboard trigger actions here via Bridge\n\n"
        "_Powered by Gemini 2.5 Flash + Groq + Algorand + Lute + Groww Mock_"
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

    # Check if this looks like a rule-setting natural language command
    rule_keywords = ["if ", "when ", "rule:", "automate ", "set rule"]
    if any(text.lower().startswith(kw) or kw in text.lower()[:30] for kw in rule_keywords):
        await _handle_natural_rule(update, tg_id, text)
        return

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


async def _handle_natural_rule(update: Update, tg_id: int, text: str):
    """Parse natural language into a trading rule via Groq."""
    await update.message.reply_text("⚙️ _Parsing your rule with AI…_", parse_mode=ParseMode.MARKDOWN)

    try:
        from groq import Groq
        import os
        groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

        prompt = f"""Parse this trading rule into JSON:
"{text}"

Return ONLY valid JSON:
{{
    "name": "short descriptive name",
    "asset": "TICKER",
    "conditions": {{
        "price_below": number or null,
        "price_above": number or null,
        "rsi_below": number or null,
        "rsi_above": number or null,
        "sentiment": "bullish" or "bearish" or null,
        "logic": "AND"
    }},
    "action_type": "buy" or "sell",
    "amount_usd": number (default 100)
}}"""

        resp = groq.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
        )
        raw = resp.choices[0].message.content
        json_start = raw.find('{')
        json_end = raw.rfind('}') + 1
        parsed = json.loads(raw[json_start:json_end])

        # Clean null values from conditions
        conditions = {k: v for k, v in parsed.get("conditions", {}).items() if v is not None}

        rule = await DynamicRuleEngine.create_rule(
            tg_id=tg_id,
            name=parsed.get("name", "Custom Rule"),
            asset=parsed.get("asset", "UNKNOWN"),
            conditions=conditions,
            action_type=parsed.get("action_type", "buy"),
            amount_usd=parsed.get("amount_usd", 100.0),
        )

        conditions_str = json.dumps(conditions, indent=2)
        await update.message.reply_text(
            f"✅ *Rule Created!*\n\n"
            f"📋 Name: `{rule['name']}`\n"
            f"📊 Asset: `{rule['asset']}`\n"
            f"⚙️ Conditions:\n```\n{conditions_str}\n```\n"
            f"💰 Action: `{rule['action_type']}` $`{rule['amount_usd']:.2f}`\n"
            f"🆔 Rule ID: `{rule['id']}`\n\n"
            f"_This rule is evaluated every 60 seconds. Trades execute via Groww Mock._",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Could not parse rule: {str(e)[:200]}")


# ═══════════════════════════════════════════════════════
#  Rule Engine Commands
# ═══════════════════════════════════════════════════════

async def cmd_set_rule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /set_rule — create a dynamic trading rule."""
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    if not context.args:
        await update.message.reply_text(
            "⚙️ *Create a Trading Rule*\n\n"
            "*Usage:* `/set_rule <natural language rule>`\n\n"
            "*Examples:*\n"
            "• `/set_rule Buy AAPL if price below 180`\n"
            "• `/set_rule Sell BTC when RSI above 70`\n"
            "• `/set_rule Buy gold if RSI below 30 and sentiment is bullish`\n\n"
            "_Or just type a rule in plain text like:_\n"
            "\"If AAPL drops below 175, buy $200 worth\"",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = " ".join(context.args)
    await _handle_natural_rule(update, tg_id, text)


async def cmd_my_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /my_rules — list all user rules."""
    tg_id = update.effective_user.id
    rules = await DynamicRuleEngine.get_user_rules(tg_id)

    if not rules:
        await update.message.reply_text(
            "📋 No rules yet. Use `/set_rule` to create one.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = f"⚙️ *Your Trading Rules ({len(rules)}):*\n\n"
    for r in rules:
        conditions = json.loads(r["conditions"]) if isinstance(r["conditions"], str) else r["conditions"]
        status_emoji = "🟢" if r["status"] == "active" else "🟡"
        text += (
            f"{status_emoji} *{r['name']}*\n"
            f"  Asset: `{r['asset']}` | Action: `{r['action_type']}` $`{r['amount_usd']:.0f}`\n"
            f"  Triggered: {r['trigger_count']}x | ID: `{r['id']}`\n\n"
        )

    text += "Delete with `/delete_rule <id>`"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_delete_rule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /delete_rule — remove a rule."""
    if not context.args:
        await update.message.reply_text("⚙️ *Usage:* `/delete_rule <rule_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    rule_id = context.args[0]
    await DynamicRuleEngine.delete_rule(rule_id)
    await update.message.reply_text(f"🗑️ Rule `{rule_id}` deleted.", parse_mode=ParseMode.MARKDOWN)


async def cmd_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /suggest — AI-powered smart suggestions based on user's rules and trades."""
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    await update.message.reply_text("🧠 _Analyzing your rules and trades…_", parse_mode=ParseMode.MARKDOWN)

    try:
        suggestions = await get_smart_suggestions(tg_id)
        await update.message.reply_text(suggestions, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Could not generate suggestions: {str(e)[:200]}")


async def cmd_mock_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /mock_trade — execute a Groww mock trade manually."""
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "💹 *Groww Mock Trade*\n\n"
            "*Usage:* `/mock_trade <asset> <amount>`\n\n"
            "*Examples:*\n"
            "• `/mock_trade AAPL 200`\n"
            "• `/mock_trade BTC 500`\n"
            "• `/mock_trade RELIANCE 150`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    asset = context.args[0].upper()
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid amount. Use a number like `200`.")
        return

    await update.message.reply_text(f"💹 _Executing mock trade on Groww for `{asset}`…_", parse_mode=ParseMode.MARKDOWN)

    price = await fetch_current_price(asset)
    if price is None:
        price = 100.0  # fallback for demo
        await update.message.reply_text(f"ℹ️ _Could not fetch live price for {asset}, using $100.00 demo price._", parse_mode=ParseMode.MARKDOWN)

    try:
        result = await GrowwMockExecutor.execute_trade(
            tg_id=tg_id,
            asset=asset,
            side="buy",
            quantity_usd=amount,
            market_price=price,
        )

        await update.message.reply_text(
            f"✅ *Groww Mock Trade Filled!*\n\n"
            f"📋 Order: `{result['order_id']}`\n"
            f"📊 Asset: `{result['asset']}`\n"
            f"💰 Amount: `${result['quantity_usd']:.2f}`\n"
            f"📈 Market: `${result['market_price']:.4f}`\n"
            f"📈 Filled: `${result['execution_price']:.4f}`\n"
            f"📉 Slippage: `{result['slippage_pct']:.3f}%`\n"
            f"💸 Fee: `${result['fee_usd']:.4f}`\n"
            f"💵 Net Cost: `${result['net_cost']:.2f}`\n\n"
            f"_Platform: {result['platform']}_",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Mock trade failed: {str(e)[:200]}")


async def cmd_trade_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /trade_history — view Groww mock trade log."""
    tg_id = update.effective_user.id
    trades = await GrowwMockExecutor.get_trade_history(tg_id)

    if not trades:
        await update.message.reply_text(
            "💹 No mock trades yet. Use `/mock_trade` or set rules with `/set_rule`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = f"💹 *Groww Mock Trade History ({len(trades)}):*\n\n"
    for t in trades[:10]:
        text += (
            f"📋 `{t['order_id']}`\n"
            f"  {t['side'].upper()} `{t['asset']}` — ${t['quantity_usd']:.2f} @ ${t['execution_price']:.4f}\n"
            f"  Slip: {t['slippage_pct']:.3f}% | Fee: ${t['fee_usd']:.4f} | {t['executed_at'][:10]}\n\n"
        )

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def post_init(application):
    """Set bot commands in the Telegram UI menu."""
    commands = [
        BotCommand("start", "Create profile ($1,000 demo)"),
        BotCommand("connect_wallet", "Connect Lute wallet via Mini App"),
        BotCommand("disconnect", "Remove linked wallet"),
        BotCommand("reset_wallet", "Force-clear wallet (clean slate)"),
        BotCommand("analyze", "AI Swarm analysis on any asset"),
        BotCommand("transact", "Open Algorand Web3 Bridge"),
        BotCommand("portfolio", "View balance & positions"),
        BotCommand("close", "Close a paper trade"),
        BotCommand("monitors", "List active price monitors"),
        BotCommand("cancel", "Cancel a price monitor"),
        BotCommand("set_rule", "Create automation rule"),
        BotCommand("my_rules", "View your trading rules"),
        BotCommand("delete_rule", "Remove a rule"),
        BotCommand("suggest", "AI-powered smart suggestions"),
        BotCommand("mock_trade", "Execute Groww mock trade"),
        BotCommand("trade_history", "View mock trade log"),
        BotCommand("help", "Show all commands"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Bot commands registered in Telegram UI")


def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set in .env — exiting.")
        return

    set_tg_notify(tg_notify)
    set_rule_notify(tg_notify)
    start_monitor_scheduler()

    # Start rule engine evaluation loop (every 60 seconds)
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    rule_scheduler = AsyncIOScheduler()
    rule_scheduler.add_job(evaluate_all_rules, "interval", seconds=60, id="rule_engine_tick")
    rule_scheduler.start()
    logger.info("⚙️ Rule engine scheduler started (60s interval)")

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
    app.add_handler(CommandHandler("reset_wallet", cmd_reset_wallet))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("transact", cmd_transact))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("close", cmd_close))
    app.add_handler(CommandHandler("monitors", cmd_monitors))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("set_rule", cmd_set_rule))
    app.add_handler(CommandHandler("my_rules", cmd_my_rules))
    app.add_handler(CommandHandler("delete_rule", cmd_delete_rule))
    app.add_handler(CommandHandler("suggest", cmd_suggest))
    app.add_handler(CommandHandler("mock_trade", cmd_mock_trade))
    app.add_handler(CommandHandler("trade_history", cmd_trade_history))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("=" * 60)
    logger.info("  X10V Telegram Bot — Starting polling")
    logger.info("=" * 60)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
