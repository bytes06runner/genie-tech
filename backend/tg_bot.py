"""
tg_bot.py — X10V Ultimate Automation Telegram Bot
====================================================
Full-featured Telegram bot matching website capabilities. Features:

  🧠 3-LLM Swarm Chatbot   — Every message routes through Alpha→Beta→Gamma
  📊 Real-Time Stock Data   — yfinance + web scraping for 90-95% accuracy
  🕷️ Web Scraping           — Playwright deep scraper on demand
  ⚡ n8n-Style Workflows    — Multi-step automation pipelines with triggers
  📬 Scheduled Messages     — Recurring and one-shot automated messaging
  📺 YouTube Research       — Domain-agnostic deep research summaries
  🎯 Trading Rules          — Dynamic rule engine evaluated every 60s
  💹 Paper Trading          — Full paper trading with mock Groww execution
  🔗 Algorand Wallet        — Web3 Mini App wallet via Lute Extension
  🤖 Natural Language AI    — Groq parses rules, workflows, schedules from text

Commands (30+):
  /start, /help, /chat, /stock, /news, /scrape, /research,
  /workflow, /my_workflows, /run_workflow, /delete_workflow,
  /schedule, /my_schedules, /delete_schedule,
  /set_rule, /my_rules, /delete_rule, /suggest,
  /analyze, /portfolio, /mock_trade, /trade_history, /close,
  /monitors, /cancel, /connect_wallet, /disconnect, /reset_wallet, /transact
"""

import asyncio
import json
import logging
import os
import re
import time as _time
from typing import Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
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
from automation_engine import (
    init_automation_db,
    create_workflow,
    get_user_workflows,
    delete_workflow,
    toggle_workflow,
    execute_workflow,
    evaluate_workflows,
    create_scheduled_message,
    get_user_scheduled_messages,
    delete_scheduled_message,
    evaluate_scheduled_messages,
    parse_workflow_from_nl,
    parse_scheduled_message_nl,
    set_automation_notify,
    _fetch_stock_data,
    execute_action_node,
)
from algorand_indexer import (
    init_indexer_db,
    set_indexer_notify,
    set_swap_prompt_callback,
    get_pending_transaction,
    mark_transaction_signed,
    get_user_pending_transactions,
    get_algo_balance,
    get_account_transactions,
    DEFAULT_SENDER,
)
from dex_screener import (
    search_pairs,
    get_top_boosted,
    get_trending_with_analysis,
    format_pair_data,
    format_pair_telegram,
    analyze_opportunity,
    subscribe_alerts,
    unsubscribe_alerts,
    get_alert_status,
    init_dex_db,
    set_dex_notify,
    load_all_subscribers,
    evaluate_dex_alerts,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("tg_bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://x10v-webapp.vercel.app")
DEFAULT_ALLOCATION = 100.0


# ═══════════════════════════════════════════════════════════════════
#  TG NOTIFY — Push messages to any user from anywhere
# ═══════════════════════════════════════════════════════════════════

_bot_app = None


def _sanitize_markdown(text: str) -> str:
    """
    Sanitize text for Telegram Markdown (v1) parse mode.
    Escapes characters that break Markdown parsing when they appear
    in dynamic content like RSS feed titles/summaries.
    Strategy: remove orphaned/unbalanced markdown markers instead of
    blindly escaping everything (which would make the text ugly).
    """
    # Fix unbalanced backticks — if odd number, remove all
    if text.count('`') % 2 != 0:
        text = text.replace('`', '')
    # Fix unbalanced bold markers
    if text.count('*') % 2 != 0:
        text = text.replace('*', '')
    # Fix unbalanced italic markers (underscores)
    if text.count('_') % 2 != 0:
        text = text.replace('_', '')
    # Fix unmatched square brackets (breaks link syntax)
    if text.count('[') != text.count(']'):
        text = text.replace('[', '(').replace(']', ')')
    return text


async def tg_notify(tg_id: int, text: str):
    """Push a message to a Telegram user from any module."""
    global _bot_app
    if _bot_app and _bot_app.bot:
        # Try Markdown first, fall back to plain text on parse error
        try:
            await _bot_app.bot.send_message(
                chat_id=tg_id,
                text=_sanitize_markdown(text),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            # Markdown failed — send as plain text (never loses the message)
            try:
                await _bot_app.bot.send_message(
                    chat_id=tg_id,
                    text=text,
                )
            except Exception as e:
                logger.error("tg_notify failed for %d: %s", tg_id, e)


async def tg_send_swap_prompt(
    tg_id: int,
    pending_tx_id: str,
    amount_algo: float,
    reason: str,
    sentiment_label: str,
):
    """
    Send an Inline Keyboard Button to Telegram with a protective transfer
    approval prompt. When clicked, opens the Mini App with the unsigned
    transaction details for signing via Lute Wallet.
    """
    global _bot_app
    if not _bot_app or not _bot_app.bot:
        logger.error("Cannot send swap prompt — bot not initialized")
        return

    swap_url = f"{WEBAPP_URL}?mode=sign_swap&ptx={pending_tx_id}&_t={int(_time.time())}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            text=f"🔐 Approve & Sign ({amount_algo} ALGO)",
            web_app=WebAppInfo(url=swap_url),
        )],
        [InlineKeyboardButton(
            text="❌ Reject Transfer",
            callback_data=f"reject_swap:{pending_tx_id}",
        )],
    ])

    text = (
        f"🚨 *DeFi Agent — Protective Transfer*\n\n"
        f"*{sentiment_label}*\n\n"
        f"📊 *Reason:* {_sanitize_markdown(reason)}\n"
        f"💰 *Amount:* `{amount_algo} ALGO` → Safe Vault\n"
        f"🆔 *TX ID:* `{pending_tx_id}`\n\n"
        f"Tap below to review & sign in your Lute Wallet, "
        f"or reject to cancel."
    )

    try:
        await _bot_app.bot.send_message(
            chat_id=tg_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )
        logger.info("✅ Swap prompt sent to user %d — PTX: %s", tg_id, pending_tx_id)
    except Exception as e:
        logger.error("Failed to send swap prompt: %s", e)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callback queries (e.g., reject transfer)."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data.startswith("reject_swap:"):
        ptx_id = data.split(":", 1)[1]
        # Mark as rejected in DB
        try:
            import aiosqlite
            async with aiosqlite.connect(
                os.getenv("USERS_DB_PATH", "users.db")
            ) as db:
                await db.execute(
                    "UPDATE pending_transactions SET status = 'rejected' WHERE id = ?",
                    (ptx_id,),
                )
                await db.commit()
        except Exception as e:
            logger.error("Failed to reject transfer %s: %s", ptx_id, e)

        await query.edit_message_text(
            f"❌ *Transfer Rejected*\n\n"
            f"Transaction `{ptx_id}` was cancelled.\n"
            f"No funds were moved.",
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info("❌ User %d rejected transfer %s", update.effective_user.id, ptx_id)
    else:
        logger.warning("Unknown callback query: %s", data)


# ═══════════════════════════════════════════════════════════════════
#  /start — User Onboarding
# ═══════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    name = update.effective_user.first_name or "Agent"
    user = await get_user(tg_id)

    if not user:
        await create_user(tg_id)
        await update.message.reply_text(
            f"🚀 *Welcome to X10V, {name}!*\n\n"
            f"Your AI-powered automation headquarters.\n\n"
            f"💰 *$1,000* paper trading balance loaded\n"
            f"🧠 3-LLM Swarm (Gemini + Groq) ready\n"
            f"📊 Real-time stock data engine online\n"
            f"⚡ n8n-style workflow automation enabled\n"
            f"📬 Scheduled messaging activated\n\n"
            f"*Quick Start:*\n"
            f"• Just *type anything* → AI Swarm responds\n"
            f"• `/stock AAPL` → Real-time stock data\n"
            f"• `/workflow` → Create automations\n"
            f"• `/help` → See all 30+ commands\n\n"
            f"_Powered by Gemini 2.5 Flash + Groq + Playwright_",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        # Returning user — show real on-chain balance if wallet connected
        wallet_line = ""
        if user.get("algo_address"):
            chain_info = await get_algo_balance(user["algo_address"])
            if chain_info:
                wallet_line = (
                    f"� Wallet: `{user['algo_address'][:16]}…`\n"
                    f"💎 ALGO: `{chain_info['balance_algo']:.6f}`\n"
                )
            else:
                wallet_line = f"🔗 Wallet: `{user['algo_address'][:16]}…` _(balance unavailable)_\n"
        else:
            wallet_line = "🔗 Wallet: Not connected — use `/connect_wallet`\n"

        await update.message.reply_text(
            f"👋 *Welcome back, {name}!*\n\n"
            f"{wallet_line}"
            f"📝 Paper Balance: `${user.get('balance', 0):.2f}`\n\n"
            f"Type anything to chat with the AI Swarm, or use `/help` for commands.",
            parse_mode=ParseMode.MARKDOWN,
        )
    log_memory("TelegramBot", f"/start by user {tg_id} ({name})")


# ═══════════════════════════════════════════════════════════════════
#  /help — Command Reference
# ═══════════════════════════════════════════════════════════════════

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *X10V Ultimate Automation Bot*\n\n"

        "━━━ 🧠 *AI & Chat* ━━━\n"
        "  _Just type anything_ — 3-LLM Swarm responds\n"
        "  `/chat <msg>` — Force swarm analysis\n\n"

        "━━━ 📊 *Real-Time Data* ━━━\n"
        "  `/stock <ticker>` — Live stock/crypto data\n"
        "  `/news <topic>` — Web-scraped latest news\n"
        "  `/scrape <query>` — Deep web scrape\n"
        "  `/research <yt_url>` — YouTube deep research\n\n"

        "━━━ ⚡ *Automation Workflows* ━━━\n"
        "  `/workflow <description>` — Create n8n-style workflow\n"
        "  `/my_workflows` — List your workflows\n"
        "  `/run_workflow <id>` — Manually trigger a workflow\n"
        "  `/pause_workflow <id>` — Pause/resume workflow\n"
        "  `/delete_workflow <id>` — Delete a workflow\n\n"

        "━━━ 📬 *Scheduled Messages* ━━━\n"
        "  `/schedule <description>` — Schedule automated messages\n"
        "  `/my_schedules` — List scheduled messages\n"
        "  `/delete_schedule <id>` — Remove scheduled message\n\n"

        "━━━ 🎯 *Trading Rules* ━━━\n"
        "  `/set_rule <rule>` — Create automation rule\n"
        "  `/my_rules` — View your rules\n"
        "  `/delete_rule <id>` — Remove a rule\n"
        "  `/suggest` — AI-powered smart suggestions\n\n"

        "━━━ 💹 *Trading* ━━━\n"
        "  `/analyze <asset>` — AI Swarm asset analysis\n"
        "  `/mock_trade <asset> <amt>` — Paper trade\n"
        "  `/trade_history` — View trade log\n"
        "  `/portfolio` — Balance & positions\n"
        "  `/close <id>` — Close a position\n"
        "  `/monitors` — Active price watchers\n"
        "  `/cancel <job_id>` — Stop a monitor\n\n"

        "━━━ 🔗 *Wallet* ━━━\n"
        "  `/connect_wallet` — Link Lute wallet\n"
        "  `/transact` — Algorand Web3 Bridge\n"
        "  `/disconnect` — Remove wallet\n"
        "  `/reset_wallet` — Force-clear wallet\n\n"

        "━━━ 📡 *DEX Screener* ━━━\n"
        "  `/dex <token>` — Search token (buyers, sellers, volume)\n"
        "  `/dex_trending` — Trending tokens + AI analysis\n"
        "  `/dex_alerts on` — Enable smart DEX notifications\n"
        "  `/dex_alerts off` — Disable notifications\n\n"

        "_Type naturally — the AI understands rules, schedules, and queries from plain text!_"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  /stock <ticker> — Real-Time Stock Data (90-95% accuracy)
# ═══════════════════════════════════════════════════════════════════

async def cmd_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📊 *Usage:* `/stock <ticker>`\n\n"
            "*Examples:*\n"
            "• `/stock AAPL` — Apple Inc.\n"
            "• `/stock TSLA` — Tesla\n"
            "• `/stock RELIANCE.NS` — Reliance (NSE)\n"
            "• `/stock BTC-USD` — Bitcoin\n"
            "• `/stock ETH-USD` — Ethereum\n"
            "• `/stock XAU=F` — Gold\n"
            "• `/stock ^GSPC` — S&P 500",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    ticker = " ".join(context.args).upper().strip()
    await update.message.reply_text(f"📊 _Fetching real-time data for_ `{ticker}` …", parse_mode=ParseMode.MARKDOWN)

    try:
        data = await _fetch_stock_data(ticker)
        await update.message.reply_text(data, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Failed to fetch data: {str(e)[:200]}")

    log_memory("TelegramBot", f"/stock {ticker}")


# ═══════════════════════════════════════════════════════════════════
#  /news <topic> — Web-Scraped News
# ═══════════════════════════════════════════════════════════════════

async def cmd_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📰 *Usage:* `/news <topic>`\n\n"
            "*Examples:*\n"
            "• `/news AAPL earnings`\n"
            "• `/news crypto market today`\n"
            "• `/news Indian stock market`\n"
            "• `/news AI industry trends`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    topic = " ".join(context.args)
    await update.message.reply_text(f"📰 _Scraping latest news on_ `{topic}` …", parse_mode=ParseMode.MARKDOWN)

    try:
        from deep_scraper import deep_scrape

        # Multi-source scraping for better coverage
        results = []
        queries = [
            f"{topic} latest news today",
            f"{topic} market analysis",
        ]

        for q in queries:
            result = await deep_scrape(q, timeout_seconds=8)
            if result.get("success"):
                results.append(result)

        if not results:
            await update.message.reply_text("⚠️ Could not scrape any relevant news. Try different keywords.")
            return

        # Send to swarm for synthesis
        combined_text = "\n\n---\n\n".join(
            f"Source: {r.get('url', 'N/A')}\n{r.get('text', '')[:800]}"
            for r in results
        )

        verdict = await run_swarm(
            text_data=f"Synthesize these news articles about '{topic}':\n\n{combined_text}",
            user_command=f"News summary for {topic}",
        )

        sd = verdict.get("structured_data", {})
        summary = sd.get("summary", "No summary generated.")
        metrics = sd.get("timeline_or_metrics", [])

        response = f"📰 *News Digest: {topic}*\n\n{summary}\n\n"
        if metrics:
            response += "📋 *Key Points:*\n"
            for m in metrics[:8]:
                response += f"  • *{m.get('key', '')}:* {m.get('value', '')}\n"
            response += "\n"

        for r in results[:2]:
            if r.get("url"):
                response += f"🔗 [Source]({r['url']})\n"

        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

    except Exception as e:
        await update.message.reply_text(f"⚠️ News fetch failed: {str(e)[:200]}")

    log_memory("TelegramBot", f"/news {topic}")


# ═══════════════════════════════════════════════════════════════════
#  /scrape <query> — Deep Web Scraping
# ═══════════════════════════════════════════════════════════════════

async def cmd_scrape(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "🕷️ *Usage:* `/scrape <query>`\n\n"
            "*Examples:*\n"
            "• `/scrape Tesla Q4 earnings report`\n"
            "• `/scrape Python FastAPI tutorial`\n"
            "• `/scrape React best practices 2025`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"🕷️ _Deep scraping_ `{query}` …", parse_mode=ParseMode.MARKDOWN)

    try:
        from deep_scraper import deep_scrape
        result = await deep_scrape(query, timeout_seconds=10)

        if result.get("success"):
            text = result.get("text", "")[:3000]
            url = result.get("url", "")
            response = f"🕷️ *Scraped Data*\n\n"
            if url:
                response += f"🔗 Source: {url}\n\n"
            response += f"```\n{text[:2500]}\n```"
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        else:
            await update.message.reply_text("⚠️ Scraping failed — no data retrieved. Try different keywords.")

    except Exception as e:
        await update.message.reply_text(f"⚠️ Scrape error: {str(e)[:200]}")

    log_memory("TelegramBot", f"/scrape {query}")


# ═══════════════════════════════════════════════════════════════════
#  /research <youtube_url> — YouTube Deep Research
# ═══════════════════════════════════════════════════════════════════

async def cmd_research(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📺 *Usage:* `/research <youtube_url>`\n\n"
            "*Examples:*\n"
            "• `/research https://youtube.com/watch?v=dQw4w9WgXcQ`\n"
            "• `/research youtu.be/abc123`\n\n"
            "_Generates a comprehensive domain-adaptive research summary._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    url = context.args[0]
    await update.message.reply_text(f"📺 _Analyzing video_ …\n_Extracting transcript + running AI research pipeline_", parse_mode=ParseMode.MARKDOWN)

    try:
        from yt_research import research_video
        result = await research_video(url)

        if result.get("error"):
            await update.message.reply_text(f"⚠️ {result['error']}")
            return

        # Send structured results
        data = result.get("data", {})
        title = data.get("title", "Unknown")
        domain = data.get("domain", "general")
        tone = data.get("tone", "neutral")
        executive = data.get("executive_summary", "")
        insights = data.get("deep_insights", [])
        topics = data.get("mentioned_topics", [])
        takeaways = data.get("key_takeaways", [])

        response = (
            f"📺 *YouTube Research Complete*\n\n"
            f"🎬 *{title}*\n"
            f"🏷️ Domain: `{domain}` | Tone: `{tone}`\n\n"
            f"📝 *Executive Summary:*\n{executive}\n\n"
        )

        if insights:
            response += "🔬 *Deep Insights:*\n"
            for ins in insights[:5]:
                response += f"  • *{ins.get('topic', '')}:* {ins.get('insight', '')}\n"
            response += "\n"

        if takeaways:
            response += "🎯 *Key Takeaways:*\n"
            for t in takeaways[:5]:
                response += f"  • {t}\n"
            response += "\n"

        if topics:
            topics_str = ", ".join(f"`{t}`" for t in topics[:10])
            response += f"📋 *Topics:* {topics_str}\n"

        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Research failed: {str(e)[:200]}")

    log_memory("TelegramBot", f"/research {url}")


# ═══════════════════════════════════════════════════════════════════
#  /workflow — n8n-Style Automation Workflows
# ═══════════════════════════════════════════════════════════════════

async def cmd_workflow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    if not context.args:
        await update.message.reply_text(
            "⚡ *Create Automation Workflow*\n\n"
            "Describe what you want in plain English!\n\n"
            "*Examples:*\n"
            "• `/workflow Every hour check AAPL price and send me an update`\n"
            "• `/workflow When Tesla drops below $200, analyze it and notify me`\n"
            "• `/workflow Every morning scrape crypto news and send summary`\n"
            "• `/workflow Check gold price every 30 minutes, if above $2500 alert me`\n"
            "• `/workflow Research this YouTube video and send me the summary: <url>`\n\n"
            "*Workflow Actions:*\n"
            "  🧠 AI Analysis • 🕷️ Web Scrape • 📊 Stock Lookup\n"
            "  📺 YouTube Research • 📬 Send Message • 🌐 HTTP Request\n"
            "  ⏳ Delay • 🔀 Conditions\n\n"
            "*Triggers:*\n"
            "  ⏰ Interval (every N min) • 📈 Price Threshold\n"
            "  📅 One-time Schedule • 🔘 Manual\n\n"
            "_The AI will parse your request into an automated pipeline!_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = " ".join(context.args)
    await update.message.reply_text("⚡ _Building your automation workflow with AI…_", parse_mode=ParseMode.MARKDOWN)

    try:
        parsed = await parse_workflow_from_nl(text, tg_id)

        wf = await create_workflow(
            tg_id=tg_id,
            name=parsed.get("name", "Custom Workflow"),
            description=parsed.get("description", text),
            trigger_type=parsed.get("trigger_type", "manual"),
            trigger_config=parsed.get("trigger_config", {}),
            steps=parsed.get("steps", []),
        )

        steps_preview = "\n".join(
            f"  {i+1}. *{s.get('name', 'Step')}* — `{s.get('type', '?')}`"
            for i, s in enumerate(parsed.get("steps", []))
        )
        trigger_str = parsed.get("trigger_type", "manual")
        trigger_cfg = parsed.get("trigger_config", {})
        if trigger_str == "interval":
            trigger_str += f" (every {trigger_cfg.get('interval_minutes', '?')} min)"
        elif trigger_str == "price_threshold":
            trigger_str += f" ({trigger_cfg.get('ticker', '?')} {trigger_cfg.get('direction', '?')} ${trigger_cfg.get('threshold', '?')})"

        await update.message.reply_text(
            f"✅ *Workflow Created!*\n\n"
            f"📋 *{wf['name']}*\n"
            f"📝 {wf.get('description', '')[:150]}\n\n"
            f"🔥 *Trigger:* `{trigger_str}`\n\n"
            f"📦 *Steps:*\n{steps_preview}\n\n"
            f"🆔 ID: `{wf['id']}`\n\n"
            f"• `/run_workflow {wf['id']}` — Run now\n"
            f"• `/pause_workflow {wf['id']}` — Pause/resume\n"
            f"• `/delete_workflow {wf['id']}` — Delete\n\n"
            f"_Active workflows are auto-evaluated every 30 seconds._",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error("Workflow creation failed: %s", e)
        await update.message.reply_text(f"⚠️ Could not create workflow: {str(e)[:200]}")

    log_memory("TelegramBot", f"/workflow by user {tg_id}")


async def cmd_my_workflows(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    workflows = await get_user_workflows(tg_id)

    if not workflows:
        await update.message.reply_text(
            "⚡ No workflows yet. Use `/workflow <description>` to create one!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = f"⚡ *Your Workflows ({len(workflows)}):*\n\n"
    for wf in workflows:
        status_emoji = "🟢" if wf["status"] == "active" else "🟡"
        runs = wf.get("run_count", 0)
        last_run = wf.get("last_run_at", "Never")
        if last_run and last_run != "Never":
            last_run = last_run[:16].replace("T", " ")
        text += (
            f"{status_emoji} *{wf['name']}*\n"
            f"  Trigger: `{wf['trigger_type']}` | Runs: {runs}\n"
            f"  Last: {last_run} | ID: `{wf['id']}`\n\n"
        )

    text += "• `/run_workflow <id>` — Run\n• `/delete_workflow <id>` — Delete"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_run_workflow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🚀 cmd_run_workflow invoked by user %s, args=%s", update.effective_user.id, context.args)
    tg_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("⚡ *Usage:* `/run_workflow <workflow_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    wf_id = context.args[0]
    workflows = await get_user_workflows(tg_id)
    target = next((w for w in workflows if w["id"] == wf_id), None)

    if not target:
        await update.message.reply_text(f"⚠️ No workflow with ID `{wf_id}`.", parse_mode=ParseMode.MARKDOWN)
        return

    await update.message.reply_text(
        f"▶️ _Running workflow_ `{target['name']}` …\n_This may take a moment._",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        result = await execute_workflow(target)
        status_emoji = "✅" if result["status"] == "completed" else "❌"

        steps_summary = ""
        for s in result.get("steps_log", []):
            s_emoji = "✅" if s.get("success") else "❌"
            steps_summary += f"  {s_emoji} *{s.get('name', 'Step')}*\n    └ {s.get('output_preview', '')[:100]}\n"

        await update.message.reply_text(
            f"{status_emoji} *Workflow Complete: {target['name']}*\n\n"
            f"📦 *Steps:*\n{steps_summary}\n"
            f"🆔 Log: `{result.get('log_id', '?')}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Execution failed: {str(e)[:200]}")


async def cmd_pause_workflow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚡ *Usage:* `/pause_workflow <id>`", parse_mode=ParseMode.MARKDOWN)
        return

    wf_id = context.args[0]
    new_status = await toggle_workflow(wf_id)
    if new_status == "not_found":
        await update.message.reply_text(f"⚠️ No workflow `{wf_id}` found.", parse_mode=ParseMode.MARKDOWN)
    else:
        emoji = "🟢" if new_status == "active" else "🟡"
        await update.message.reply_text(
            f"{emoji} Workflow `{wf_id}` is now `{new_status}`.",
            parse_mode=ParseMode.MARKDOWN,
        )


async def cmd_delete_workflow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚡ *Usage:* `/delete_workflow <id>`", parse_mode=ParseMode.MARKDOWN)
        return

    wf_id = context.args[0]
    deleted = await delete_workflow(wf_id)
    if deleted:
        await update.message.reply_text(f"🗑️ Workflow `{wf_id}` deleted.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"⚠️ No workflow with ID `{wf_id}`.", parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  /schedule — Automated Scheduled Messages
# ═══════════════════════════════════════════════════════════════════

async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    if not context.args:
        await update.message.reply_text(
            "📬 *Schedule Automated Messages*\n\n"
            "Describe your schedule in plain English!\n\n"
            "*Examples:*\n"
            "• `/schedule Remind me to check stocks in 30 minutes`\n"
            "• `/schedule Every hour tell me to take a break`\n"
            "• `/schedule Every morning at 9am send market opening reminder`\n"
            "• `/schedule In 2 hours remind me about the meeting`\n\n"
            "_AI will parse your timing and set it up!_",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = " ".join(context.args)
    await update.message.reply_text("📬 _Parsing your schedule with AI…_", parse_mode=ParseMode.MARKDOWN)

    try:
        parsed = await parse_scheduled_message_nl(text)

        msg = await create_scheduled_message(
            tg_id=tg_id,
            message=parsed.get("message", text),
            run_at=parsed.get("run_at"),
            repeat=parsed.get("repeat", False),
            repeat_interval_min=parsed.get("repeat_interval_min", 0),
        )

        repeat_str = "🔁 Recurring" if parsed.get("repeat") else "📌 One-time"
        timing_str = ""
        if parsed.get("run_at"):
            timing_str = f"⏰ Scheduled: `{parsed['run_at'][:16]}`\n"
        if parsed.get("repeat") and parsed.get("repeat_interval_min"):
            timing_str += f"🔄 Every `{parsed['repeat_interval_min']}` minutes\n"

        await update.message.reply_text(
            f"✅ *Message Scheduled!*\n\n"
            f"📝 Message: _{msg['message'][:100]}_\n"
            f"{timing_str}"
            f"📋 Type: {repeat_str}\n"
            f"🆔 ID: `{msg['id']}`\n\n"
            f"• `/my_schedules` — View all\n"
            f"• `/delete_schedule {msg['id']}` — Cancel",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        await update.message.reply_text(f"⚠️ Could not parse schedule: {str(e)[:200]}")

    log_memory("TelegramBot", f"/schedule by user {tg_id}")


async def cmd_my_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    messages = await get_user_scheduled_messages(tg_id)

    if not messages:
        await update.message.reply_text(
            "📬 No scheduled messages. Use `/schedule <description>` to create one!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = f"📬 *Your Scheduled Messages ({len(messages)}):*\n\n"
    for m in messages:
        status_emoji = {"active": "🟢", "delivered": "✅", "cancelled": "🔴"}.get(m["status"], "⚪")
        repeat_str = "🔁" if m.get("repeat") else "📌"
        text += (
            f"{status_emoji} {repeat_str} _{m['message'][:60]}_\n"
            f"  Runs: {m.get('run_count', 0)} | Status: `{m['status']}`\n"
            f"  ID: `{m['id']}`\n\n"
        )

    text += "Delete with `/delete_schedule <id>`"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_delete_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📬 *Usage:* `/delete_schedule <id>`", parse_mode=ParseMode.MARKDOWN)
        return

    msg_id = context.args[0]
    deleted = await delete_scheduled_message(msg_id)
    if deleted:
        await update.message.reply_text(f"🗑️ Scheduled message `{msg_id}` deleted.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"⚠️ No scheduled message with ID `{msg_id}`.", parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  /chat — Force Swarm Chat
# ═══════════════════════════════════════════════════════════════════

async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    if not context.args:
        await update.message.reply_text(
            "🧠 *Usage:* `/chat <your message>`\n\n"
            "Or just type anything without a command — the AI will respond!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = " ".join(context.args)
    await _swarm_chat(update, tg_id, text)


# ═══════════════════════════════════════════════════════════════════
#  /analyze <asset> — AI Swarm Analysis
# ═══════════════════════════════════════════════════════════════════

async def cmd_analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        # First get real-time stock data
        stock_data = await _fetch_stock_data(asset)

        input_text = (
            f"Analyze {asset} for trading.\n\n"
            f"REAL-TIME DATA:\n{stock_data}\n\n"
            f"Based on this live data, provide: trend analysis, support/resistance levels, "
            f"key metrics assessment, and a clear trading recommendation."
        )
        verdict = await run_swarm(text_data=input_text, user_command=f"Analyze {asset}")

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

        # Include live price data
        response += f"━━━━━━━━━━━━━━━\n📊 *Live Data:*\n{stock_data}\n"

        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)

        # Auto-monitor logic
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
                    f"Asset: `{asset_ticker}` | Target: `${float(target_price):.2f}`\n"
                    f"Allocation: `${alloc:.2f}` | Job: `{job_id}`\n\n"
                    f"_I'll auto-execute and notify you when target hits._",
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
                            f"Asset: `{asset_ticker}` | Entry: `${current_price:.2f}`\n"
                            f"Allocated: `${alloc:.2f}` | ID: `{pos['id']}`\n\n"
                            f"Use `/close {pos['id']}` to close.",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    except ValueError as e:
                        await update.message.reply_text(f"⚠️ Trade failed: {e}")

    except Exception as e:
        logger.error("Swarm analysis failed for %s: %s", asset, e)
        await update.message.reply_text(f"⚠️ Analysis failed: {str(e)[:200]}")

    log_memory("TelegramBot", f"/analyze {asset} by user {tg_id}")


# ═══════════════════════════════════════════════════════════════════
#  WALLET & TRADING COMMANDS (preserved)
# ═══════════════════════════════════════════════════════════════════

async def cmd_connect_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    wallet_url = f"{WEBAPP_URL}?mode=connect&_t={int(_time.time())}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="🔗 Open Wallet Connector", web_app=WebAppInfo(url=wallet_url))],
    ])

    if user.get("algo_address"):
        await update.message.reply_text(
            f"🔗 *Current Wallet*\n\nAddress: `{user['algo_address']}`\n\n"
            f"Tap below to *update*, or `/disconnect` to remove.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
        )
    else:
        await update.message.reply_text(
            "🔗 *Connect Algorand Wallet*\n\nTap below to connect via Lute Wallet.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
        )


async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    raw_data = update.effective_message.web_app_data.data
    try:
        payload = json.loads(raw_data)
        address = payload.get("address", "").strip()
    except (json.JSONDecodeError, AttributeError):
        address = raw_data.strip()

    if not address or len(address) < 20:
        await update.message.reply_text("⚠️ Invalid wallet address.")
        return

    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    await link_wallet(tg_id, address, "lute-external-wallet")

    # Fetch real on-chain balance to confirm connection
    chain_info = await get_algo_balance(address)
    if chain_info:
        balance_text = (
            f"💎 *Balance:* `{chain_info['balance_algo']:.6f} ALGO`\n"
            f"💧 *Available:* `{chain_info['available_algo']:.6f} ALGO`\n"
        )
    else:
        balance_text = "⚠️ _Could not fetch on-chain balance — check address_\n"

    await update.message.reply_text(
        f"✅ *Wallet Connected!*\n\n📬 `{address}`\n\n"
        f"{balance_text}\n"
        f"💧 [Fund on TestNet](https://bank.testnet.algorand.network/)\n"
        f"📊 Use `/portfolio` to see full details",
        parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True,
    )


async def cmd_disconnect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return
    if not user.get("algo_address"):
        await update.message.reply_text("ℹ️ No wallet connected.", parse_mode=ParseMode.MARKDOWN)
        return
    old = user["algo_address"]
    await disconnect_wallet(tg_id)
    await update.message.reply_text(f"🔓 Wallet `{old}` disconnected.", parse_mode=ParseMode.MARKDOWN)


async def cmd_reset_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return
    await disconnect_wallet(tg_id)
    await update.message.reply_text("🗑️ Wallet force-reset. Use `/connect_wallet` to relink.", parse_mode=ParseMode.MARKDOWN)


async def cmd_transact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    transact_url = f"{WEBAPP_URL}?mode=transact&_t={int(_time.time())}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="⚡ Open Algorand Bridge", web_app=WebAppInfo(url=transact_url))],
    ])
    await update.message.reply_text(
        "🌐 *Algorand Web3 Bridge*\n\nTap to connect Lute Wallet & sign transactions.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard,
    )


# ═══════════════════════════════════════════════════════════════════
#  DeFi AGENT COMMANDS — Whale Alerts, Pending Swaps
# ═══════════════════════════════════════════════════════════════════

async def cmd_whale_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually check for recent whale transactions on Algorand TestNet."""
    from algorand_indexer import poll_large_transactions

    min_algo = 10_000.0
    if context.args:
        try:
            min_algo = float(context.args[0])
        except ValueError:
            pass

    await update.message.reply_text(
        f"🐋 _Scanning Algorand TestNet for transfers > {min_algo:,.0f} ALGO…_",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        whales = await poll_large_transactions(min_algo=min_algo, limit=10)
        if not whales:
            await update.message.reply_text(
                f"No whale transactions found (>{min_algo:,.0f} ALGO) in recent blocks.",
            )
            return

        text = f"🐋 *Whale Alert — {len(whales)} Large Transfers*\n\n"
        for i, w in enumerate(whales[:5], 1):
            text += (
                f"{i}. `{w['amount_algo']:,.2f}` ALGO\n"
                f"   From: `{w['sender'][:12]}…`\n"
                f"   To: `{w['receiver'][:12]}…`\n"
                f"   Round: `{w['round']}` | Fee: `{w['fee']} ALGO`\n\n"
            )

        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Whale scan failed: {str(e)[:200]}")


async def cmd_pending_swaps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List pending unsigned transactions waiting for user approval."""
    tg_id = update.effective_user.id
    pending = await get_user_pending_transactions(tg_id)

    if not pending:
        await update.message.reply_text("✅ No pending transactions.")
        return

    text = f"🔔 *Pending Transfers ({len(pending)}):*\n\n"
    for p in pending[:5]:
        swap_url = f"{WEBAPP_URL}?mode=sign_swap&ptx={p['id']}&_t={int(_time.time())}"
        text += (
            f"🆔 `{p['id']}`\n"
            f"💰 {p['amount_algo']} ALGO → Safe Vault\n"
            f"📝 {p['note'][:60]}\n"
            f"🕐 {p['created_at'][:16]}\n\n"
        )

    text += "Use the inline buttons to approve or reject."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    paper_balance = user.get("balance", 0)
    wallet = user.get("algo_address")
    positions = await get_open_positions(tg_id)
    monitors = get_user_monitors(tg_id)
    all_positions = await get_all_positions(tg_id)
    closed = [p for p in all_positions if p["status"] == "closed"]
    workflows = await get_user_workflows(tg_id)
    schedules = await get_user_scheduled_messages(tg_id)

    text = f"💼 *X10V Portfolio*\n\n"

    # ── On-chain ALGO balance (real) ──
    if wallet:
        chain_info = await get_algo_balance(wallet)
        if chain_info:
            text += f"🔗 *Wallet:* `{wallet[:16]}…`\n"
            text += f"💎 *ALGO Balance:* `{chain_info['balance_algo']:.6f} ALGO`\n"
            text += f"💧 *Available:* `{chain_info['available_algo']:.6f} ALGO`\n"
            text += f"� *Min Balance:* `{chain_info['min_balance_algo']:.6f} ALGO`\n"
            if chain_info['total_assets'] > 0:
                text += f"🪙 *ASAs:* {chain_info['total_assets']} opted-in\n"
            text += f"🌐 *Status:* {chain_info['status']}\n\n"

            # Recent transactions
            recent_txns = await get_account_transactions(wallet, limit=3)
            if recent_txns:
                text += "📜 *Recent Transactions:*\n"
                for tx in recent_txns:
                    arrow = "📤" if tx["type"] == "sent" else "📥"
                    text += f"  {arrow} `{tx['amount_algo']:.4f}` ALGO — `{tx['tx_id']}`\n"
                text += "\n"
        else:
            text += f"🔗 *Wallet:* `{wallet[:16]}…`\n"
            text += f"⚠️ _Could not fetch on-chain balance_\n\n"
    else:
        text += "🔗 *Wallet:* Not connected — use `/connect_wallet`\n\n"

    # ── Paper trading balance ──
    text += f"📝 *Paper Trading Balance:* `${paper_balance:.2f}`\n\n"

    # Positions
    if positions:
        text += f"📈 *Open Positions ({len(positions)}):*\n"
        for p in positions:
            text += f"  • `{p['asset']}` — ${p['amount_usd']:.2f} @ ${p['entry_price']:.2f}\n"
        text += "\n"
    else:
        text += "📈 *Open Positions:* None\n\n"

    # Monitors
    if monitors:
        text += f"📡 *Monitors ({len(monitors)}):* Active\n"

    # PnL
    if closed:
        total_pnl = sum(p.get("pnl", 0) for p in closed)
        emoji = "🟢" if total_pnl >= 0 else "🔴"
        text += f"📊 *Closed Trades:* {len(closed)} | {emoji} PnL: `${total_pnl:+.2f}`\n"

    # Automations summary
    active_wf = len([w for w in workflows if w.get("status") == "active"])
    active_sched = len([s for s in schedules if s.get("status") == "active"])
    text += f"\n⚡ *Automations:* {active_wf} workflows | {active_sched} scheduled msgs"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("📊 *Usage:* `/close <position_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    pos_id = context.args[0]
    positions = await get_open_positions(tg_id)
    target = next((p for p in positions if p["id"] == pos_id), None)
    if not target:
        await update.message.reply_text(f"⚠️ No open position `{pos_id}`.", parse_mode=ParseMode.MARKDOWN)
        return

    asset = target["asset"]
    current_price = await fetch_current_price(asset)
    if current_price is None:
        await update.message.reply_text(f"⚠️ Could not fetch price for `{asset}`.")
        return

    try:
        result = await close_position(tg_id, pos_id, current_price)
        pnl = result.get("pnl", 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        await update.message.reply_text(
            f"✅ *Position Closed*\n\n"
            f"`{asset}`: ${result['entry_price']:.2f} → ${current_price:.2f}\n"
            f"{emoji} PnL: `${pnl:+.2f}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except ValueError as e:
        await update.message.reply_text(f"⚠️ {e}")


async def cmd_monitors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    monitors = get_user_monitors(tg_id)
    if not monitors:
        await update.message.reply_text("📡 No active monitors.", parse_mode=ParseMode.MARKDOWN)
        return

    text = f"📡 *Active Monitors ({len(monitors)}):*\n\n"
    for m in monitors:
        text += f"• `{m['asset']}` → $`{m['target_price']:.2f}` | Job: `{m['job_id']}`\n"
    text += "\nCancel with `/cancel <job_id>`"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("📡 *Usage:* `/cancel <job_id>`", parse_mode=ParseMode.MARKDOWN)
        return
    success = cancel_monitor(context.args[0])
    if success:
        await update.message.reply_text(f"✅ Monitor `{context.args[0]}` cancelled.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"⚠️ No monitor `{context.args[0]}`.", parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  RULE ENGINE COMMANDS
# ═══════════════════════════════════════════════════════════════════

async def cmd_set_rule(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            "_Rules are evaluated every 60 seconds._",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = " ".join(context.args)
    await _handle_natural_rule(update, tg_id, text)


async def _handle_natural_rule(update: Update, tg_id: int, text: str):
    await update.message.reply_text("⚙️ _Parsing your rule with AI…_", parse_mode=ParseMode.MARKDOWN)
    try:
        from groq import Groq
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
            temperature=0.1, max_tokens=300,
        )
        raw = resp.choices[0].message.content
        json_start = raw.find('{')
        json_end = raw.rfind('}') + 1
        parsed = json.loads(raw[json_start:json_end])

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
            f"📋 `{rule['name']}` | Asset: `{rule['asset']}`\n"
            f"⚙️ Conditions:\n```\n{conditions_str}\n```\n"
            f"💰 Action: `{rule['action_type']}` ${rule['amount_usd']:.0f}\n"
            f"🆔 `{rule['id']}`\n\n"
            f"_Evaluated every 60 seconds._",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Could not parse rule: {str(e)[:200]}")


async def cmd_my_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    rules = await DynamicRuleEngine.get_user_rules(tg_id)
    if not rules:
        await update.message.reply_text("📋 No rules. Use `/set_rule`.", parse_mode=ParseMode.MARKDOWN)
        return

    text = f"⚙️ *Your Rules ({len(rules)}):*\n\n"
    for r in rules:
        status_emoji = "🟢" if r["status"] == "active" else "🟡"
        text += (
            f"{status_emoji} *{r['name']}* — `{r['asset']}` `{r['action_type']}`\n"
            f"  Triggered: {r['trigger_count']}x | ID: `{r['id']}`\n\n"
        )
    text += "Delete: `/delete_rule <id>`"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_delete_rule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚙️ *Usage:* `/delete_rule <id>`", parse_mode=ParseMode.MARKDOWN)
        return
    await DynamicRuleEngine.delete_rule(context.args[0])
    await update.message.reply_text(f"🗑️ Rule `{context.args[0]}` deleted.", parse_mode=ParseMode.MARKDOWN)


async def cmd_suggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    await update.message.reply_text("🧠 _Analyzing your profile…_", parse_mode=ParseMode.MARKDOWN)
    try:
        suggestions = await get_smart_suggestions(tg_id)
        await update.message.reply_text(suggestions, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"⚠️ {str(e)[:200]}")


async def cmd_mock_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Use `/start` first.", parse_mode=ParseMode.MARKDOWN)
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "💹 *Usage:* `/mock_trade <asset> <amount>`\n\n"
            "• `/mock_trade AAPL 200`\n"
            "• `/mock_trade BTC 500`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    asset = context.args[0].upper()
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid amount.")
        return

    await update.message.reply_text(f"💹 _Executing mock trade for_ `{asset}` …", parse_mode=ParseMode.MARKDOWN)

    price = await fetch_current_price(asset)
    if price is None:
        price = 100.0
        await update.message.reply_text(f"ℹ️ _Using $100 demo price for {asset}_", parse_mode=ParseMode.MARKDOWN)

    try:
        result = await GrowwMockExecutor.execute_trade(
            tg_id=tg_id, asset=asset, side="buy", quantity_usd=amount, market_price=price,
        )
        await update.message.reply_text(
            f"✅ *Mock Trade Filled!*\n\n"
            f"📋 `{result['order_id']}` | `{result['asset']}`\n"
            f"💰 ${result['quantity_usd']:.2f} @ ${result['execution_price']:.4f}\n"
            f"📉 Slip: {result['slippage_pct']:.3f}% | Fee: ${result['fee_usd']:.4f}\n"
            f"💵 Net: ${result['net_cost']:.2f}",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Trade failed: {str(e)[:200]}")


async def cmd_trade_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    trades = await GrowwMockExecutor.get_trade_history(tg_id)
    if not trades:
        await update.message.reply_text("💹 No trades yet. Use `/mock_trade`.", parse_mode=ParseMode.MARKDOWN)
        return

    text = f"💹 *Trade History ({len(trades)}):*\n\n"
    for t in trades[:10]:
        text += (
            f"📋 {t['side'].upper()} `{t['asset']}` — ${t['quantity_usd']:.2f} @ ${t['execution_price']:.4f}\n"
            f"  {t['executed_at'][:10]} | Slip: {t['slippage_pct']:.3f}%\n\n"
        )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  DEX SCREENER — Token Search, Buyer/Seller Data, AI Alerts
# ═══════════════════════════════════════════════════════════════════

async def cmd_dex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search DEX Screener for any token — shows buyers, sellers, volume, AI analysis."""
    if not context.args:
        await update.message.reply_text(
            "🔍 *DEX Screener — Token Intelligence*\n\n"
            "*Usage:* `/dex <token_name_or_symbol>`\n\n"
            "*Examples:*\n"
            "• `/dex PEPE` — Search PEPE memecoin\n"
            "• `/dex SOL/USDC` — Search SOL/USDC pair\n"
            "• `/dex BONK` — Search BONK token\n"
            "• `/dex ALGO` — Search Algorand pairs\n"
            "• `/dex dogwifhat` — Search by token name\n\n"
            "Shows: price, volume, liquidity, buyers vs sellers, AI analysis\n\n"
            "🔔 *Want alerts?* Use `/dex_alerts on`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    query = " ".join(context.args)
    await update.message.reply_text(
        f"🔍 _Searching DEX Screener for_ `{query}` …\n"
        f"_Fetching buyer/seller data + running AI analysis_",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        pairs = await search_pairs(query)
        if not pairs:
            await update.message.reply_text(
                f"⚠️ No pairs found for `{query}`. Try a different name or symbol.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        # Format top 3 pairs
        formatted = [format_pair_data(p) for p in pairs[:3]]

        msg = f"🔍 *DEX Screener: {query.upper()}*\n"
        msg += f"_Found {len(pairs)} pairs — showing top {min(3, len(pairs))}_\n\n"

        for i, pd in enumerate(formatted, 1):
            msg += f"━━━ *#{i}* ━━━\n"
            msg += format_pair_telegram(pd)
            if pd.get("url"):
                msg += f"🔗 [View on DEX Screener]({pd['url']})\n"
            msg += "\n"

        # Run AI analysis on the top results
        try:
            analysis = await analyze_opportunity(pairs[:5])
            sd = analysis.get("structured_data", {})
            summary = sd.get("summary", "")
            if summary:
                msg += f"🧠 *AI Swarm Analysis:*\n_{_sanitize_markdown(summary[:600])}_\n\n"

            metrics = sd.get("timeline_or_metrics", [])
            if metrics:
                msg += "📊 *Key Signals:*\n"
                for m in metrics[:5]:
                    msg += f"  • *{m.get('key', '')}:* {m.get('value', '')}\n"
                msg += "\n"
        except Exception as ai_err:
            logger.warning("AI analysis failed for DEX query: %s", ai_err)

        msg = _sanitize_markdown(msg)
        try:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        except Exception:
            await update.message.reply_text(msg, disable_web_page_preview=True)

    except Exception as e:
        await update.message.reply_text(f"⚠️ DEX search failed: {str(e)[:200]}")

    log_memory("TelegramBot", f"/dex {query}")


async def cmd_dex_trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show trending/boosted tokens with AI-powered opportunity analysis."""
    await update.message.reply_text(
        "📈 _Fetching trending tokens from DEX Screener…_\n"
        "_Running 3-LLM Swarm analysis for trade opportunities_",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        result = await get_trending_with_analysis()
        tokens = result.get("tokens", [])
        analysis = result.get("analysis")

        if not tokens:
            await update.message.reply_text("⚠️ No trending tokens found. Try again in a few minutes.")
            return

        msg = f"📈 *DEX Screener — Trending Tokens*\n"
        msg += f"_Top {len(tokens)} boosted tokens with AI analysis_\n\n"

        for i, t in enumerate(tokens[:6], 1):
            bs_ratio = t.get('buy_sell_ratio_1h', 0)
            if bs_ratio >= 999:
                ratio_str = "∞"
            elif bs_ratio == 0:
                ratio_str = "0"
            else:
                ratio_str = f"{bs_ratio:.2f}"

            if bs_ratio > 1.5:
                emoji = "🟢"
            elif bs_ratio > 1.0:
                emoji = "🟡"
            elif bs_ratio > 0.7:
                emoji = "🟠"
            else:
                emoji = "🔴"

            msg += (
                f"*#{i}* {emoji} *{t['symbol']}* ({t['chain']})\n"
                f"  💰 `${float(t.get('price_usd', 0)):.6f}`\n"
                f"  📊 Vol: `${t.get('volume_24h', 0):,.0f}` | Liq: `${t.get('liquidity_usd', 0):,.0f}`\n"
                f"  🔄 Buys: `{t.get('buys_1h', 0)}` | Sells: `{t.get('sells_1h', 0)}` | Ratio: `{ratio_str}`\n"
                f"  Δ1h: `{t.get('price_change_1h', 0):+.2f}%`"
                f" | Δ24h: `{t.get('price_change_24h', 0):+.2f}%`\n\n"
            )

        if analysis:
            sd = analysis.get("structured_data", {})
            summary = sd.get("summary", "")
            if summary:
                msg += f"🧠 *AI Swarm Verdict:*\n_{_sanitize_markdown(summary[:500])}_\n\n"

            metrics = sd.get("timeline_or_metrics", [])
            if metrics:
                msg += "📊 *Opportunity Scores:*\n"
                for m in metrics[:6]:
                    msg += f"  • *{m.get('key', '')}:* {m.get('value', '')}\n"
                msg += "\n"

        msg += "_Powered by DEX Screener + 3-LLM Swarm_"

        msg = _sanitize_markdown(msg)
        try:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        except Exception:
            await update.message.reply_text(msg, disable_web_page_preview=True)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Trending fetch failed: {str(e)[:200]}")

    log_memory("TelegramBot", "/dex_trending")


async def cmd_dex_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage DEX Screener alert subscriptions."""
    tg_id = update.effective_user.id
    args = context.args or []

    if not args:
        # Show current status
        status = await get_alert_status(tg_id)
        if status and status.get("enabled"):
            await update.message.reply_text(
                "🔔 *DEX Screener Alerts — Active*\n\n"
                f"📡 Chain: `{status.get('chain', 'all')}`\n"
                f"📊 Min Volume: `${status.get('min_volume', 50000):,.0f}`\n"
                f"💧 Min Liquidity: `${status.get('min_liquidity', 10000):,.0f}`\n"
                f"⏱️ Scan Interval: Every 5 minutes\n\n"
                "*Commands:*\n"
                "• `/dex_alerts off` — Turn off alerts\n"
                "• `/dex_alerts on` — Re-enable alerts\n"
                "• `/dex_alerts on solana` — Filter by chain\n"
                "• `/dex_alerts on ethereum 100000` — Chain + min volume\n"
                "• `/dex_alerts on all 100000 25000` — All chains, custom thresholds",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await update.message.reply_text(
                "🔕 *DEX Screener Alerts — Inactive*\n\n"
                "Get notified when the AI Swarm detects high-volume "
                "trade opportunities on DEX Screener.\n\n"
                "The bot scans trending tokens every 5 minutes, "
                "analyzes them with 3 LLMs, and alerts you about "
                "coins with strong buying pressure.\n\n"
                "*Enable:*\n"
                "• `/dex_alerts on` — All chains, default filters\n"
                "• `/dex_alerts on solana` — Solana only\n"
                "• `/dex_alerts on ethereum 100000` — ETH, vol > $100K\n"
                "• `/dex_alerts on all 200000 50000` — Custom thresholds",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    action = args[0].lower()

    if action == "off":
        await unsubscribe_alerts(tg_id)
        await update.message.reply_text(
            "🔕 *DEX alerts disabled.*\nUse `/dex_alerts on` to re-enable.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if action == "on":
        chain = args[1].lower() if len(args) > 1 else "all"
        min_vol = float(args[2]) if len(args) > 2 else 50000
        min_liq = float(args[3]) if len(args) > 3 else 10000

        await subscribe_alerts(tg_id, chain=chain, min_volume=min_vol, min_liquidity=min_liq)
        await update.message.reply_text(
            "🔔 *DEX Screener Alerts — Enabled!*\n\n"
            f"📡 Chain: `{chain}`\n"
            f"📊 Min Volume: `${min_vol:,.0f}`\n"
            f"💧 Min Liquidity: `${min_liq:,.0f}`\n"
            f"⏱️ Scanning every 5 minutes\n\n"
            "The 3-LLM Swarm will analyze trending tokens and alert you "
            "about coins with high volume and strong buying pressure.\n\n"
            "Use `/dex_alerts off` to disable.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await update.message.reply_text(
        "⚠️ Unknown option. Use `/dex_alerts on` or `/dex_alerts off`.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ═══════════════════════════════════════════════════════════════════
#  INTELLIGENT FREE-TEXT HANDLER (3-LLM Swarm + Intent Detection)
# ═══════════════════════════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Master handler for all non-command text messages.
    Uses intelligent routing:
      1. Detect if it's a rule/schedule/workflow/stock request
      2. Route to appropriate handler
      3. Default: Full 3-LLM swarm chat
    """
    tg_id = update.effective_user.id
    user = await get_user(tg_id)
    if not user:
        await update.message.reply_text("⚠️ Send `/start` first!", parse_mode=ParseMode.MARKDOWN)
        return

    text = update.message.text.strip()

    # ── Guard: reject any message starting with / (command that leaked through) ──
    if text.startswith("/"):
        logger.warning("handle_text received command-like message: %r — attempting manual dispatch", text[:80])
        # Manual dispatch fallback for commands that leaked through filters
        parts = text.split(maxsplit=1)
        cmd_name = parts[0].lstrip("/").split("@")[0].lower()  # strip /cmd@BotName
        _COMMAND_DISPATCH = {
            "run_workflow": cmd_run_workflow,
            "my_workflows": cmd_my_workflows,
            "workflow": cmd_workflow,
            "pause_workflow": cmd_pause_workflow,
            "delete_workflow": cmd_delete_workflow,
            "schedule": cmd_schedule,
            "my_schedules": cmd_my_schedules,
            "delete_schedule": cmd_delete_schedule,
            "set_rule": cmd_set_rule,
            "my_rules": cmd_my_rules,
            "delete_rule": cmd_delete_rule,
            "stock": cmd_stock,
            "news": cmd_news,
            "scrape": cmd_scrape,
            "research": cmd_research,
            "chat": cmd_chat,
            "analyze": cmd_analyze,
            "portfolio": cmd_portfolio,
            "close": cmd_close,
            "monitors": cmd_monitors,
            "cancel": cmd_cancel,
            "suggest": cmd_suggest,
            "mock_trade": cmd_mock_trade,
            "trade_history": cmd_trade_history,
            "connect_wallet": cmd_connect_wallet,
            "disconnect": cmd_disconnect,
            "reset_wallet": cmd_reset_wallet,
            "transact": cmd_transact,
            "whale_alert": cmd_whale_alert,
            "pending_swaps": cmd_pending_swaps,
            "dex": cmd_dex,
            "dex_trending": cmd_dex_trending,
            "dex_alerts": cmd_dex_alerts,
            "start": cmd_start,
            "help": cmd_help,
        }
        handler_fn = _COMMAND_DISPATCH.get(cmd_name)
        if handler_fn:
            # Inject args manually since we're bypassing CommandHandler
            if len(parts) > 1:
                context.args = parts[1].split()
            else:
                context.args = []
            logger.info("Manual dispatch: /%s → %s (args=%s)", cmd_name, handler_fn.__name__, context.args)
            await handler_fn(update, context)
        else:
            logger.warning("Unknown leaked command: /%s — ignoring", cmd_name)
        return

    lower = text.lower()

    # Intent detection patterns
    rule_keywords = ["if ", "when ", "rule:", "automate ", "set rule"]
    schedule_keywords = ["remind me", "every hour", "every day", "every morning", "schedule", "in 30 min", "in 1 hour", "recurring"]
    workflow_keywords = ["workflow:", "create workflow", "automation:", "pipeline:"]
    stock_keywords = ["price of", "stock price", "how is", "what's the price", "ticker"]

    # Route to appropriate handler
    if any(kw in lower for kw in rule_keywords):
        await _handle_natural_rule(update, tg_id, text)
    elif any(kw in lower for kw in schedule_keywords):
        await _handle_natural_schedule(update, tg_id, text)
    elif any(kw in lower for kw in workflow_keywords):
        await _handle_natural_workflow(update, tg_id, text)
    elif any(kw in lower for kw in stock_keywords):
        # Extract potential ticker and fetch stock data
        await _handle_stock_query(update, text)
    else:
        # Default: 3-LLM Swarm chat
        await _swarm_chat(update, tg_id, text)


async def _swarm_chat(update: Update, tg_id: int, text: str):
    """Route any text through the full Alpha→Beta→Gamma swarm."""
    await update.message.reply_text(
        "🧠 _Processing with AI Swarm…_\n_Alpha → Beta → Gamma_",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        verdict = await run_swarm(text_data=text, user_command=text)
        sd = verdict.get("structured_data", {})
        summary = sd.get("summary", "No summary.")
        metrics = sd.get("timeline_or_metrics", [])
        decision = verdict.get("decision", "inform")
        domain = verdict.get("domain", "general")

        decision_emoji = {"inform": "📋", "execute": "✅", "abort": "🛑"}.get(decision, "❓")
        response = f"{decision_emoji} *Swarm ({domain}):*\n\n{summary}\n\n"

        if metrics:
            response += "📊 *Details:*\n"
            for m in metrics[:6]:
                response += f"  • *{m.get('key', '')}:* {m.get('value', '')}\n"

        response = _sanitize_markdown(response)
        try:
            await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error: {str(e)[:200]}")

    log_memory("TelegramBot", f"Chat by user {tg_id}: {text[:50]}")


async def _handle_natural_schedule(update: Update, tg_id: int, text: str):
    """Parse natural language into scheduled message."""
    await update.message.reply_text("📬 _Setting up your scheduled message…_", parse_mode=ParseMode.MARKDOWN)

    try:
        parsed = await parse_scheduled_message_nl(text)
        msg = await create_scheduled_message(
            tg_id=tg_id,
            message=parsed.get("message", text),
            run_at=parsed.get("run_at"),
            repeat=parsed.get("repeat", False),
            repeat_interval_min=parsed.get("repeat_interval_min", 0),
        )
        repeat_str = "🔁 Recurring" if parsed.get("repeat") else "📌 One-time"
        await update.message.reply_text(
            f"✅ *Scheduled!*\n\n📝 _{msg['message'][:80]}_\n📋 {repeat_str}\n🆔 `{msg['id']}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Could not schedule: {str(e)[:200]}")


async def _handle_natural_workflow(update: Update, tg_id: int, text: str):
    """Parse natural language into workflow."""
    await update.message.reply_text("⚡ _Building automation workflow…_", parse_mode=ParseMode.MARKDOWN)

    try:
        parsed = await parse_workflow_from_nl(text, tg_id)
        wf = await create_workflow(
            tg_id=tg_id,
            name=parsed.get("name", "Auto Workflow"),
            description=parsed.get("description", text),
            trigger_type=parsed.get("trigger_type", "manual"),
            trigger_config=parsed.get("trigger_config", {}),
            steps=parsed.get("steps", []),
        )
        await update.message.reply_text(
            f"✅ *Workflow Created!*\n\n📋 *{wf['name']}*\n🔥 Trigger: `{wf['trigger_type']}`\n🆔 `{wf['id']}`\n\n"
            f"Run: `/run_workflow {wf['id']}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Could not create workflow: {str(e)[:200]}")


async def _handle_stock_query(update: Update, text: str):
    """Handle natural language stock queries."""
    await update.message.reply_text("📊 _Fetching stock data…_", parse_mode=ParseMode.MARKDOWN)

    try:
        # Use Groq to extract ticker from natural language
        from groq import Groq
        groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
        resp = groq.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": f"Extract the stock/crypto ticker symbol from this text. Return ONLY the ticker symbol (e.g., AAPL, BTC-USD, RELIANCE.NS). Text: \"{text}\""}],
            temperature=0.1, max_tokens=20,
        )
        ticker = resp.choices[0].message.content.strip().upper()
        ticker = re.sub(r'[^A-Z0-9.\-^/=]', '', ticker)

        if ticker:
            data = await _fetch_stock_data(ticker)
            await update.message.reply_text(data, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("⚠️ Could not identify a stock ticker.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ {str(e)[:200]}")


# ═══════════════════════════════════════════════════════════════════
#  BOT INITIALIZATION & MAIN
# ═══════════════════════════════════════════════════════════════════

async def post_init(application):
    """Set bot commands in the Telegram UI menu."""
    commands = [
        BotCommand("start", "Create profile & connect wallet"),
        BotCommand("help", "Show all 30+ commands"),
        BotCommand("stock", "Real-time stock/crypto data"),
        BotCommand("news", "Web-scraped latest news"),
        BotCommand("scrape", "Deep web scrape"),
        BotCommand("research", "YouTube deep research"),
        BotCommand("chat", "Chat with 3-LLM Swarm"),
        BotCommand("workflow", "Create n8n-style automation"),
        BotCommand("my_workflows", "List your workflows"),
        BotCommand("run_workflow", "Run a workflow"),
        BotCommand("pause_workflow", "Pause/resume workflow"),
        BotCommand("delete_workflow", "Delete a workflow"),
        BotCommand("schedule", "Schedule automated messages"),
        BotCommand("my_schedules", "List scheduled messages"),
        BotCommand("delete_schedule", "Delete scheduled message"),
        BotCommand("analyze", "AI Swarm asset analysis"),
        BotCommand("set_rule", "Create automation rule"),
        BotCommand("my_rules", "View your rules"),
        BotCommand("delete_rule", "Remove a rule"),
        BotCommand("suggest", "AI smart suggestions"),
        BotCommand("mock_trade", "Paper trade on Groww"),
        BotCommand("trade_history", "View trade log"),
        BotCommand("portfolio", "Balance & positions"),
        BotCommand("close", "Close a position"),
        BotCommand("monitors", "Active price monitors"),
        BotCommand("cancel", "Cancel a monitor"),
        BotCommand("connect_wallet", "Link Lute wallet"),
        BotCommand("transact", "Algorand Web3 Bridge"),
        BotCommand("disconnect", "Remove wallet"),
        BotCommand("reset_wallet", "Force-clear wallet"),
        BotCommand("whale_alert", "Scan for whale transactions"),
        BotCommand("pending_swaps", "View pending DeFi swaps"),
        BotCommand("dex", "DEX Screener token search"),
        BotCommand("dex_trending", "Trending tokens + AI analysis"),
        BotCommand("dex_alerts", "DEX alert notifications"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ Bot commands registered (30 commands)")


def main():
    global _bot_app

    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not set — exiting.")
        return

    # Initialize automation DB
    import asyncio as _aio
    loop = _aio.new_event_loop()
    loop.run_until_complete(init_automation_db())
    loop.run_until_complete(init_indexer_db())
    loop.run_until_complete(init_dex_db())
    loop.run_until_complete(load_all_subscribers())
    loop.close()

    # Wire up notify callbacks
    set_tg_notify(tg_notify)
    set_rule_notify(tg_notify)
    set_automation_notify(tg_notify)
    set_indexer_notify(tg_notify)
    set_swap_prompt_callback(tg_send_swap_prompt)
    set_dex_notify(tg_notify)

    # Start market monitor scheduler
    start_monitor_scheduler()

    # Start rule engine (60s) + workflow engine (30s) + message scheduler (30s)
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    automation_scheduler = AsyncIOScheduler()
    automation_scheduler.add_job(evaluate_all_rules, "interval", seconds=60, id="rule_engine_tick")
    automation_scheduler.add_job(evaluate_workflows, "interval", seconds=30, id="workflow_engine_tick")
    automation_scheduler.add_job(evaluate_scheduled_messages, "interval", seconds=30, id="message_scheduler_tick")
    automation_scheduler.add_job(evaluate_dex_alerts, "interval", seconds=300, id="dex_alert_tick")
    automation_scheduler.start()
    logger.info("⚡ Automation scheduler started: rules(60s) + workflows(30s) + messages(30s) + dex_alerts(300s)")

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .read_timeout(30)
        .write_timeout(30)
        .build()
    )
    _bot_app = app

    # ─── Register all command handlers ───
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))

    # AI & Data
    app.add_handler(CommandHandler("chat", cmd_chat))
    app.add_handler(CommandHandler("stock", cmd_stock))
    app.add_handler(CommandHandler("news", cmd_news))
    app.add_handler(CommandHandler("scrape", cmd_scrape))
    app.add_handler(CommandHandler("research", cmd_research))

    # Automation Workflows
    app.add_handler(CommandHandler("workflow", cmd_workflow))
    app.add_handler(CommandHandler("my_workflows", cmd_my_workflows))
    app.add_handler(CommandHandler("run_workflow", cmd_run_workflow))
    app.add_handler(CommandHandler("pause_workflow", cmd_pause_workflow))
    app.add_handler(CommandHandler("delete_workflow", cmd_delete_workflow))

    # Scheduled Messages
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("my_schedules", cmd_my_schedules))
    app.add_handler(CommandHandler("delete_schedule", cmd_delete_schedule))

    # Trading
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("close", cmd_close))
    app.add_handler(CommandHandler("monitors", cmd_monitors))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # Rules
    app.add_handler(CommandHandler("set_rule", cmd_set_rule))
    app.add_handler(CommandHandler("my_rules", cmd_my_rules))
    app.add_handler(CommandHandler("delete_rule", cmd_delete_rule))
    app.add_handler(CommandHandler("suggest", cmd_suggest))
    app.add_handler(CommandHandler("mock_trade", cmd_mock_trade))
    app.add_handler(CommandHandler("trade_history", cmd_trade_history))

    # Wallet & DeFi
    app.add_handler(CommandHandler("connect_wallet", cmd_connect_wallet))
    app.add_handler(CommandHandler("disconnect", cmd_disconnect))
    app.add_handler(CommandHandler("reset_wallet", cmd_reset_wallet))
    app.add_handler(CommandHandler("transact", cmd_transact))
    app.add_handler(CommandHandler("whale_alert", cmd_whale_alert))
    app.add_handler(CommandHandler("pending_swaps", cmd_pending_swaps))

    # DEX Screener
    app.add_handler(CommandHandler("dex", cmd_dex))
    app.add_handler(CommandHandler("dex_trending", cmd_dex_trending))
    app.add_handler(CommandHandler("dex_alerts", cmd_dex_alerts))

    # Free-text, Callback Queries & Web App Data
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("=" * 60)
    logger.info("  X10V Autonomous DeFi Agent — 30+ commands")
    logger.info("  3-LLM Swarm | On-Chain Events | Sentiment Analysis")
    logger.info("  DEX Swaps | n8n Workflows | YouTube Research")
    logger.info("=" * 60)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
