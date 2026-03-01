"""
automation_engine.py — n8n-Style Workflow Automation Engine
=============================================================
A full-featured workflow automation engine inspired by n8n, designed for
Telegram-native execution. Supports:

  • Trigger Nodes  — cron, price_threshold, keyword_match, webhook, time_once,
                     on_chain_event (Algorand Indexer whale alerts)
  • Action Nodes   — send_message, ai_analyze, web_scrape, fetch_rss, stock_lookup,
                     youtube_research, execute_trade, api_call, analyze_sentiment,
                     execute_dex_swap
  • Condition Nodes — if/else branching based on variables
  • Workflow DAG    — multi-step pipelines with variable passing

All workflows are persisted to SQLite and evaluated by APScheduler.
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Coroutine, Optional

import aiosqlite
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("automation_engine")

DB_PATH = os.getenv("USERS_DB_PATH", "users.db")

# ─── Notify callback (set by tg_bot.py) ────────────────────────────
_tg_notify: Optional[Callable] = None

def set_automation_notify(fn):
    global _tg_notify
    _tg_notify = fn


# ═══════════════════════════════════════════════════════════════════
#  DATABASE SCHEMA
# ═══════════════════════════════════════════════════════════════════

async def init_automation_db():
    """Create automation tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id          TEXT PRIMARY KEY,
                tg_id       INTEGER NOT NULL,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                trigger_type TEXT NOT NULL,
                trigger_config TEXT DEFAULT '{}',
                steps       TEXT DEFAULT '[]',
                variables   TEXT DEFAULT '{}',
                status      TEXT DEFAULT 'active',
                run_count   INTEGER DEFAULT 0,
                last_run_at TEXT,
                created_at  TEXT,
                updated_at  TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS workflow_logs (
                id          TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                tg_id       INTEGER NOT NULL,
                status      TEXT DEFAULT 'running',
                steps_log   TEXT DEFAULT '[]',
                started_at  TEXT,
                finished_at TEXT,
                error       TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id          TEXT PRIMARY KEY,
                tg_id       INTEGER NOT NULL,
                message     TEXT NOT NULL,
                cron_expr   TEXT,
                run_at      TEXT,
                repeat      INTEGER DEFAULT 0,
                repeat_interval_min INTEGER DEFAULT 0,
                status      TEXT DEFAULT 'active',
                run_count   INTEGER DEFAULT 0,
                last_run_at TEXT,
                created_at  TEXT
            )
        """)
        await db.commit()
    logger.info("✅ Automation DB tables initialized")


# ═══════════════════════════════════════════════════════════════════
#  WORKFLOW CRUD
# ═══════════════════════════════════════════════════════════════════

async def create_workflow(
    tg_id: int,
    name: str,
    description: str,
    trigger_type: str,
    trigger_config: dict,
    steps: list,
) -> dict:
    """Create a new automation workflow."""
    wf_id = f"wf_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO workflows
               (id, tg_id, name, description, trigger_type, trigger_config, steps, variables, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, '{}', 'active', ?, ?)""",
            (wf_id, tg_id, name, description, trigger_type,
             json.dumps(trigger_config), json.dumps(steps), now, now),
        )
        await db.commit()

    logger.info("✅ Workflow created: %s (%s) for user %d", wf_id, name, tg_id)
    return {
        "id": wf_id, "name": name, "description": description,
        "trigger_type": trigger_type, "trigger_config": trigger_config,
        "steps": steps, "status": "active", "created_at": now,
    }


async def get_user_workflows(tg_id: int) -> list:
    """Get all workflows for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM workflows WHERE tg_id = ? ORDER BY created_at DESC", (tg_id,)
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_active_workflows() -> list:
    """Get all active workflows across all users."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM workflows WHERE status = 'active'"
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_workflow(wf_id: str) -> bool:
    """Delete a workflow by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM workflows WHERE id = ?", (wf_id,))
        await db.commit()
        return cursor.rowcount > 0


async def toggle_workflow(wf_id: str) -> str:
    """Toggle workflow status between active and paused."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT status FROM workflows WHERE id = ?", (wf_id,))
        row = await cursor.fetchone()
        if not row:
            return "not_found"
        new_status = "paused" if row["status"] == "active" else "active"
        await db.execute("UPDATE workflows SET status = ?, updated_at = ? WHERE id = ?",
                         (new_status, datetime.now(timezone.utc).isoformat(), wf_id))
        await db.commit()
    return new_status


# ═══════════════════════════════════════════════════════════════════
#  SCHEDULED MESSAGES
# ═══════════════════════════════════════════════════════════════════

async def create_scheduled_message(
    tg_id: int,
    message: str,
    run_at: Optional[str] = None,
    repeat: bool = False,
    repeat_interval_min: int = 0,
) -> dict:
    """Schedule a message for future delivery."""
    msg_id = f"msg_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO scheduled_messages
               (id, tg_id, message, run_at, repeat, repeat_interval_min, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'active', ?)""",
            (msg_id, tg_id, message, run_at, int(repeat), repeat_interval_min, now),
        )
        await db.commit()

    return {
        "id": msg_id, "message": message, "run_at": run_at,
        "repeat": repeat, "interval_min": repeat_interval_min,
    }


async def get_pending_messages() -> list:
    """Get all active scheduled messages that are due."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM scheduled_messages
               WHERE status = 'active' AND (run_at IS NULL OR run_at <= ?)""",
            (now,),
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_user_scheduled_messages(tg_id: int) -> list:
    """Get all scheduled messages for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM scheduled_messages WHERE tg_id = ? ORDER BY created_at DESC", (tg_id,)
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_scheduled_message(msg_id: str) -> bool:
    """Delete a scheduled message."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM scheduled_messages WHERE id = ?", (msg_id,))
        await db.commit()
        return cursor.rowcount > 0


# ═══════════════════════════════════════════════════════════════════
#  ACTION EXECUTORS (The nodes of our n8n-style pipeline)
# ═══════════════════════════════════════════════════════════════════

async def execute_action_node(action: dict, variables: dict) -> dict:
    """
    Execute a single action node in a workflow.
    Each action has a 'type' and 'config' dict.
    Returns updated variables dict with the action's output.
    """
    action_type = action.get("type", "")
    config = action.get("config", {})
    result = {"success": False, "output": ""}

    try:
        if action_type == "ai_analyze":
            from swarm_brain import run_swarm
            prompt = _interpolate(config.get("prompt", ""), variables)
            verdict = await run_swarm(text_data=prompt, user_command=prompt)
            sd = verdict.get("structured_data", {})
            result = {
                "success": True,
                "output": sd.get("summary", "No summary"),
                "decision": verdict.get("decision", "inform"),
                "full_verdict": verdict,
            }

        elif action_type == "web_scrape":
            from deep_scraper import deep_scrape
            query = _interpolate(config.get("query", ""), variables)
            url_hint = config.get("url", "")
            logger.info("🕷️ web_scrape action — query=%r, url_hint=%r", query, url_hint)
            scrape_result = await deep_scrape(query, timeout_seconds=10)
            scraped_text = scrape_result.get("text", "")
            scraped_url = scrape_result.get("url", "")
            logger.info("🕷️ web_scrape result — success=%s, url=%s, chars=%d",
                        scrape_result.get("success"), scraped_url, len(scraped_text))
            result = {
                "success": scrape_result.get("success", False) and len(scraped_text.strip()) > 20,
                "output": scraped_text[:1500] if scraped_text.strip() else "No content extracted from page.",
                "url": scraped_url,
            }

        elif action_type == "fetch_rss":
            import aiohttp
            import feedparser

            feed_url = _interpolate(config.get("feed_url", ""), variables)
            max_items = int(config.get("max_items", 5))
            logger.info("📰 fetch_rss action — feed_url=%s, max_items=%d", feed_url, max_items)

            # Fetch feed with a modern User-Agent
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(feed_url, headers=headers,
                                           timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        raw_feed = await resp.text()

                feed = feedparser.parse(raw_feed)
                entries = feed.entries[:max_items]

                if not entries:
                    result = {"success": False, "output": f"RSS feed returned 0 entries: {feed_url}"}
                else:
                    items = []
                    for entry in entries:
                        title = entry.get("title", "No title")
                        link = entry.get("link", "")
                        summary = entry.get("summary", entry.get("description", ""))[:200]
                        # Strip HTML tags from summary
                        summary = re.sub(r'<[^>]+>', '', summary).strip()
                        items.append(f"• {title}\n  {summary}\n  🔗 {link}")

                    output_text = f"📰 Latest {len(items)} items from RSS:\n\n" + "\n\n".join(items)
                    result = {
                        "success": True,
                        "output": output_text,
                        "titles": [e.get("title", "") for e in entries],
                        "links": [e.get("link", "") for e in entries],
                        "item_count": len(entries),
                    }
                    logger.info("📰 fetch_rss got %d entries from %s", len(entries), feed_url)
            except Exception as rss_err:
                logger.error("📰 fetch_rss failed for %s: %s", feed_url, rss_err)
                result = {"success": False, "output": f"RSS fetch failed: {str(rss_err)[:200]}"}

        elif action_type == "stock_lookup":
            ticker = _interpolate(config.get("ticker", ""), variables)
            data = await _fetch_stock_data(ticker)
            result = {"success": True, "output": data}

        elif action_type == "youtube_research":
            from yt_research import research_video
            url = _interpolate(config.get("url", ""), variables)
            research = await research_video(url)
            result = {
                "success": not research.get("error"),
                "output": research.get("markdown", research.get("error", "Failed")),
            }

        elif action_type == "send_message":
            msg = _interpolate(config.get("message", ""), variables)
            tg_id = config.get("tg_id") or variables.get("_tg_id")
            if tg_id and _tg_notify:
                await _tg_notify(int(tg_id), msg)
                result = {"success": True, "output": f"Message sent to {tg_id}"}
            else:
                result = {"success": False, "output": "No tg_id or notify function"}

        elif action_type == "condition":
            # Simple if/else evaluation
            condition_str = _interpolate(config.get("condition", ""), variables)
            try:
                passed = bool(eval(condition_str, {"__builtins__": {}}, variables))
            except Exception:
                passed = False
            result = {"success": True, "output": str(passed), "condition_passed": passed}

        elif action_type == "http_request":
            import aiohttp
            url = _interpolate(config.get("url", ""), variables)
            method = config.get("method", "GET").upper()
            headers = config.get("headers", {})
            body = _interpolate(config.get("body", ""), variables) if config.get("body") else None
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, data=body, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    text = await resp.text()
                    result = {"success": resp.status < 400, "output": text[:1500], "status_code": resp.status}

        elif action_type == "transform":
            # Simple data transformation using template
            template = config.get("template", "")
            result = {"success": True, "output": _interpolate(template, variables)}

        elif action_type == "delay":
            seconds = int(config.get("seconds", 5))
            await asyncio.sleep(min(seconds, 300))  # Max 5 min delay
            result = {"success": True, "output": f"Waited {seconds}s"}

        elif action_type == "analyze_sentiment":
            # ── NEW: LLM-powered sentiment analysis of text/RSS output ──
            from groq import Groq as _Groq
            input_text = _interpolate(config.get("text", ""), variables)
            # If no explicit text, use previous step output
            if not input_text.strip():
                for k in sorted(variables.keys(), reverse=True):
                    if k.startswith("step_") and k.endswith("_output") and variables[k]:
                        input_text = str(variables[k])
                        break

            if not input_text.strip():
                result = {"success": False, "output": "No text to analyze for sentiment."}
            else:
                groq_key = os.getenv("GROQ_API_KEY")
                _groq = _Groq(api_key=groq_key)

                sentiment_prompt = (
                    "You are a financial sentiment analyzer. Analyze the following text "
                    "and return ONLY a JSON object with these fields:\n"
                    '{"sentiment": "bullish" | "bearish" | "neutral", '
                    '"score": 0-100 (0=extreme bearish, 50=neutral, 100=extreme bullish), '
                    '"confidence": 0.0-1.0, '
                    '"key_signals": ["signal1", "signal2"], '
                    '"summary": "one-sentence summary"}\n\n'
                    f"TEXT TO ANALYZE:\n{input_text[:4000]}"
                )

                def _call_sentiment():
                    resp = _groq.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "user", "content": sentiment_prompt}],
                        temperature=0.1,
                        max_tokens=300,
                    )
                    return resp.choices[0].message.content

                raw_sentiment = await asyncio.get_event_loop().run_in_executor(None, _call_sentiment)

                try:
                    sentiment_data = _safe_parse_json(raw_sentiment)
                except Exception:
                    sentiment_data = {"sentiment": "neutral", "score": 50, "confidence": 0.3,
                                      "key_signals": [], "summary": raw_sentiment[:200]}

                score = sentiment_data.get("score", 50)
                sentiment = sentiment_data.get("sentiment", "neutral")
                signals = sentiment_data.get("key_signals", [])

                # Store structured output in variables for downstream steps
                variables["_sentiment_data"] = json.dumps(sentiment_data)
                variables["_sentiment_label"] = sentiment
                variables["_sentiment_score"] = str(score)

                emoji = "🟢" if sentiment == "bullish" else ("🔴" if sentiment == "bearish" else "⚖️")
                result = {
                    "success": True,
                    "output": (
                        f"{emoji} Sentiment: {sentiment.upper()} (Score: {score}/100)\n"
                        f"Confidence: {sentiment_data.get('confidence', 'N/A')}\n"
                        f"Signals: {', '.join(signals[:3]) if signals else 'None detected'}\n"
                        f"Summary: {sentiment_data.get('summary', 'N/A')}"
                    ),
                    "sentiment_data": sentiment_data,
                }
                logger.info("📊 Sentiment analysis: %s (score=%s)", sentiment, score)

        elif action_type == "execute_dex_swap":
            # ── NEW: Build unsigned Algorand TX + trigger Telegram approval prompt ──
            from algorand_indexer import execute_dex_swap_action
            from paper_engine import get_user

            tg_id = config.get("tg_id") or variables.get("_tg_id")
            amount_algo = float(config.get("amount_algo", 1.0))

            # Determine amount dynamically if configured
            if config.get("dynamic_amount") and "_sentiment_score" in variables:
                score = int(variables.get("_sentiment_score", 50))
                if score < 30:
                    amount_algo = float(config.get("bearish_amount", 5.0))
                elif score < 50:
                    amount_algo = float(config.get("cautious_amount", 2.0))
                else:
                    amount_algo = float(config.get("amount_algo", 1.0))

            reason = _interpolate(config.get("reason", "Autonomous DeFi Agent swap"), variables)

            # Get user's connected wallet
            user = await get_user(int(tg_id)) if tg_id else None
            sender_address = user.get("algo_address", "") if user else ""

            # Parse sentiment data if available
            sentiment_data = None
            if "_sentiment_data" in variables:
                try:
                    sentiment_data = json.loads(variables["_sentiment_data"])
                except Exception:
                    pass

            swap_result = await execute_dex_swap_action(
                tg_id=int(tg_id),
                sender_address=sender_address,
                amount_algo=amount_algo,
                reason=reason,
                sentiment_data=sentiment_data,
            )

            result = {
                "success": swap_result.get("success", False),
                "output": swap_result.get("output", "Swap action failed"),
                "pending_tx_id": swap_result.get("pending_tx_id"),
            }

        else:
            result = {"success": False, "output": f"Unknown action type: {action_type}"}

    except Exception as e:
        logger.error("Action node '%s' failed: %s", action_type, e)
        result = {"success": False, "output": f"Error: {str(e)[:200]}"}

    return result


def _interpolate(template: str, variables: dict) -> str:
    """Replace {{var}} placeholders with variable values."""
    for key, val in variables.items():
        template = template.replace(f"{{{{{key}}}}}", str(val))
    return template


# ═══════════════════════════════════════════════════════════════════
#  STOCK DATA FETCHER (High-accuracy via yfinance + web scraping)
# ═══════════════════════════════════════════════════════════════════

async def _fetch_stock_data(ticker: str) -> str:
    """
    Multi-source stock data fetcher for 90-95% accuracy.
    Priority: yfinance → DuckDuckGo scrape fallback.
    """
    try:
        data = await _yfinance_fetch(ticker)
        if data:
            return data
    except Exception as e:
        logger.warning("yfinance failed for %s: %s", ticker, e)

    # Fallback to web scraping
    try:
        from deep_scraper import deep_scrape
        result = await deep_scrape(f"{ticker} stock price today real-time", timeout_seconds=8)
        if result.get("success"):
            return f"📊 Web-scraped data for {ticker}:\n{result['text'][:1000]}"
    except Exception as e:
        logger.warning("Web scrape fallback failed for %s: %s", ticker, e)

    return f"⚠️ Could not fetch data for {ticker}"


async def _yfinance_fetch(ticker: str) -> Optional[str]:
    """Fetch comprehensive stock data via yfinance."""
    import yfinance as yf

    def _sync_fetch():
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info or not info.get("regularMarketPrice"):
            # Try common suffixes
            for suffix in [".NS", ".BSE", ".L", ""]:
                try:
                    alt = yf.Ticker(f"{ticker}{suffix}")
                    alt_info = alt.info
                    if alt_info and alt_info.get("regularMarketPrice"):
                        return alt_info
                except Exception:
                    continue
            return None
        return info

    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, _sync_fetch)

    if not info:
        return None

    name = info.get("shortName", info.get("longName", ticker))
    price = info.get("regularMarketPrice", info.get("currentPrice", 0))
    prev_close = info.get("regularMarketPreviousClose", info.get("previousClose", 0))
    change = price - prev_close if price and prev_close else 0
    change_pct = (change / prev_close * 100) if prev_close else 0
    high = info.get("dayHigh", info.get("regularMarketDayHigh", "N/A"))
    low = info.get("dayLow", info.get("regularMarketDayLow", "N/A"))
    volume = info.get("volume", info.get("regularMarketVolume", "N/A"))
    mkt_cap = info.get("marketCap", "N/A")
    pe = info.get("trailingPE", "N/A")
    week52_high = info.get("fiftyTwoWeekHigh", "N/A")
    week52_low = info.get("fiftyTwoWeekLow", "N/A")
    avg_vol = info.get("averageVolume", "N/A")
    beta = info.get("beta", "N/A")
    dividend = info.get("dividendYield", None)
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")

    emoji = "🟢" if change >= 0 else "🔴"

    # Format large numbers
    def _fmt(n):
        if isinstance(n, (int, float)):
            if n >= 1e12: return f"${n/1e12:.2f}T"
            if n >= 1e9: return f"${n/1e9:.2f}B"
            if n >= 1e6: return f"${n/1e6:.2f}M"
            return f"{n:,.0f}"
        return str(n)

    lines = [
        f"{emoji} *{name}* (`{ticker.upper()}`)",
        f"",
        f"💰 Price: `${price:,.2f}`  ({'+' if change >= 0 else ''}{change:,.2f} | {'+' if change_pct >= 0 else ''}{change_pct:.2f}%)",
        f"📈 Day High: `${high}`  |  📉 Day Low: `${low}`",
        f"📊 Volume: `{_fmt(volume)}`  |  Avg Vol: `{_fmt(avg_vol)}`",
        f"🏢 Market Cap: `{_fmt(mkt_cap)}`",
        f"📐 P/E Ratio: `{pe}`  |  Beta: `{beta}`",
        f"📅 52W High: `${week52_high}`  |  52W Low: `${week52_low}`",
    ]
    if dividend:
        lines.append(f"💵 Dividend Yield: `{dividend*100:.2f}%`")
    lines.append(f"🏭 Sector: `{sector}` | Industry: `{industry}`")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
#  WORKFLOW EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════════

async def execute_workflow(workflow: dict) -> dict:
    """
    Execute a full workflow pipeline — trigger already confirmed.
    Runs each step sequentially, passing variables between nodes.
    """
    wf_id = workflow["id"]
    tg_id = workflow["tg_id"]
    steps = json.loads(workflow["steps"]) if isinstance(workflow["steps"], str) else workflow["steps"]
    variables = json.loads(workflow.get("variables", "{}")) if isinstance(workflow.get("variables"), str) else workflow.get("variables", {})
    variables["_tg_id"] = tg_id
    variables["_workflow_id"] = wf_id
    variables["_timestamp"] = datetime.now(timezone.utc).isoformat()

    # Merge any injected variables from trigger evaluation (e.g., on-chain events)
    injected = workflow.get("_injected_variables", {})
    if injected:
        variables.update(injected)

    log_id = f"log_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    steps_log = []
    halted_early = False

    try:
        for i, step in enumerate(steps):
            step_name = step.get("name", f"Step {i+1}")
            step_type = step.get("type", "unknown")

            logger.info("▶️ Workflow %s step %d: %s (%s)", wf_id, i+1, step_name, step_type)

            result = await execute_action_node(step, variables)
            step_success = result.get("success", False)
            step_output = str(result.get("output", ""))

            steps_log.append({
                "step": i+1, "name": step_name, "type": step_type,
                "success": step_success, "output_preview": step_output[:200],
            })

            # Store output in variables for next steps
            variables[f"step_{i+1}_output"] = result.get("output", "")
            variables[f"step_{i+1}_success"] = step_success

            # Handle condition branching
            if step_type == "condition" and not result.get("condition_passed", True):
                logger.info("⏭️ Condition failed at step %d, skipping remaining steps", i+1)
                break

            # ── FAIL-SAFE: Halt pipeline on step failure / empty data ──
            # Data-producing steps (fetch_rss, web_scrape, stock_lookup, ai_analyze,
            # youtube_research, http_request) must succeed AND return non-empty output
            # before downstream steps (transform, send_message) can use them.
            data_producing_types = {
                "fetch_rss", "web_scrape", "stock_lookup", "ai_analyze",
                "youtube_research", "http_request", "analyze_sentiment",
            }
            if step_type in data_producing_types and (not step_success or len(step_output.strip()) < 10):
                halted_early = True
                fail_msg = (
                    f"⚠️ *Workflow halted:* `{workflow.get('name', wf_id)}`\n\n"
                    f"Step {i+1} *{step_name}* (`{step_type}`) failed or returned empty data.\n"
                    f"Reason: {step_output[:300] if step_output.strip() else 'No output returned.'}\n\n"
                    f"Remaining steps were skipped to avoid sending broken data."
                )
                logger.warning("⛔ Workflow %s halted at step %d (%s) — data step failed/empty",
                               wf_id, i+1, step_name)
                # Send error notification to user
                if _tg_notify:
                    try:
                        await _tg_notify(int(tg_id), fail_msg)
                    except Exception as notify_err:
                        logger.error("Failed to send halt notification: %s", notify_err)
                break

            # Legacy explicit stop_on_failure flag
            if not step_success and step.get("stop_on_failure", False):
                logger.warning("⛔ Step %d failed with stop_on_failure=True", i+1)
                halted_early = True
                break

        status = "halted" if halted_early else "completed"
    except Exception as e:
        status = "failed"
        logger.error("Workflow %s execution failed: %s", wf_id, e)
        steps_log.append({"error": str(e)})

    # Save execution log
    finished_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO workflow_logs (id, workflow_id, tg_id, status, steps_log, started_at, finished_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (log_id, wf_id, tg_id, status, json.dumps(steps_log), now, finished_at),
        )
        await db.execute(
            """UPDATE workflows SET run_count = run_count + 1, last_run_at = ?, updated_at = ? WHERE id = ?""",
            (finished_at, finished_at, wf_id),
        )
        await db.commit()

    return {"log_id": log_id, "status": status, "steps_log": steps_log, "variables": variables}


# ═══════════════════════════════════════════════════════════════════
#  WORKFLOW EVALUATOR (Called by scheduler every tick)
# ═══════════════════════════════════════════════════════════════════

async def evaluate_workflows():
    """
    Evaluate all active workflows — check triggers, execute if matched.
    Called periodically by APScheduler (every 30 seconds).
    """
    workflows = await get_active_workflows()
    now = datetime.now(timezone.utc)

    for wf in workflows:
        try:
            trigger_type = wf["trigger_type"]
            trigger_config = json.loads(wf["trigger_config"]) if isinstance(wf["trigger_config"], str) else wf["trigger_config"]

            should_fire = False

            if trigger_type == "interval":
                interval_min = trigger_config.get("interval_minutes", 60)
                last_run = wf.get("last_run_at")
                if not last_run:
                    should_fire = True
                else:
                    last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                    if (now - last_dt).total_seconds() >= interval_min * 60:
                        should_fire = True

            elif trigger_type == "price_threshold":
                ticker = trigger_config.get("ticker", "")
                threshold = trigger_config.get("threshold", 0)
                direction = trigger_config.get("direction", "below")
                if ticker:
                    data = await _fetch_stock_data(ticker)
                    # Extract price from the data string
                    import re
                    price_match = re.search(r'Price: `\$([0-9,.]+)`', data)
                    if price_match:
                        current = float(price_match.group(1).replace(",", ""))
                        if direction == "below" and current <= threshold:
                            should_fire = True
                        elif direction == "above" and current >= threshold:
                            should_fire = True

            elif trigger_type == "time_once":
                target_time = trigger_config.get("at")
                if target_time:
                    target_dt = datetime.fromisoformat(target_time.replace("Z", "+00:00"))
                    if now >= target_dt and not wf.get("last_run_at"):
                        should_fire = True

            elif trigger_type == "manual":
                pass  # Only fires on /run_workflow command

            elif trigger_type == "on_chain_event":
                # ── NEW: Algorand on-chain event trigger ──
                from algorand_indexer import check_on_chain_events
                fired, event_data = await check_on_chain_events(trigger_config)
                if fired:
                    should_fire = True
                    # Inject event data into workflow variables for downstream steps
                    wf["_injected_variables"] = {
                        "_whale_txn": json.dumps(event_data.get("whale_txn", {})),
                        "_whale_count": str(event_data.get("count", 0)),
                        "_chain_event": json.dumps(event_data),
                    }

            if should_fire:
                logger.info("🔥 Workflow %s (%s) TRIGGERED", wf["id"], wf["name"])
                result = await execute_workflow(wf)

                # Notify user
                if _tg_notify:
                    status_emoji = "✅" if result["status"] == "completed" else "❌"
                    steps_summary = "\n".join(
                        f"  {'✅' if s.get('success') else '❌'} {s.get('name', 'Step')} — {s.get('output_preview', '')[:80]}"
                        for s in result.get("steps_log", [])
                    )
                    await _tg_notify(
                        wf["tg_id"],
                        f"⚡ *Workflow Executed: {wf['name']}*\n\n"
                        f"Status: {status_emoji} `{result['status']}`\n"
                        f"Steps:\n{steps_summary}\n\n"
                        f"_Run #{wf.get('run_count', 0) + 1}_",
                    )

        except Exception as e:
            logger.error("Error evaluating workflow %s: %s", wf["id"], e)


async def evaluate_scheduled_messages():
    """
    Check and send due scheduled messages.
    Called periodically by APScheduler.
    """
    messages = await get_pending_messages()
    now = datetime.now(timezone.utc)

    for msg in messages:
        try:
            if not _tg_notify:
                continue

            tg_id = msg["tg_id"]
            text = msg["message"]
            await _tg_notify(tg_id, f"📬 *Scheduled Message*\n\n{text}")

            async with aiosqlite.connect(DB_PATH) as db:
                if msg.get("repeat") and msg.get("repeat_interval_min", 0) > 0:
                    # Reschedule
                    next_run = (now + timedelta(minutes=msg["repeat_interval_min"])).isoformat()
                    await db.execute(
                        """UPDATE scheduled_messages
                           SET run_count = run_count + 1, last_run_at = ?, run_at = ?
                           WHERE id = ?""",
                        (now.isoformat(), next_run, msg["id"]),
                    )
                else:
                    # One-shot, mark done
                    await db.execute(
                        "UPDATE scheduled_messages SET status = 'delivered', run_count = 1, last_run_at = ? WHERE id = ?",
                        (now.isoformat(), msg["id"]),
                    )
                await db.commit()

            logger.info("📬 Delivered scheduled message %s to user %d", msg["id"], tg_id)

        except Exception as e:
            logger.error("Failed to deliver scheduled message %s: %s", msg["id"], e)


# ═══════════════════════════════════════════════════════════════════
#  NATURAL LANGUAGE WORKFLOW BUILDER (via Groq)
# ═══════════════════════════════════════════════════════════════════

async def parse_workflow_from_nl(text: str, tg_id: int) -> dict:
    """
    Use Groq Llama to parse natural language into a workflow definition.
    Returns a workflow dict ready to be saved.
    """
    from groq import Groq

    groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = (
        "You are a JSON-only Autonomous DeFi Agent workflow builder. "
        "You MUST respond with ONLY a single raw JSON object. "
        "Do NOT include any markdown formatting, code fences, backticks, "
        "introductory text, explanations, or trailing commentary. "
        "Your entire response must be parseable by json.loads() directly.\n\n"
        "CRITICAL RULES:\n"
        "1. If the user's request involves news/headlines/articles → use \"fetch_rss\" with a real RSS URL. NEVER \"web_scrape\".\n"
        "2. If the user wants sentiment analysis → chain fetch_rss → analyze_sentiment.\n"
        "3. If the user wants autonomous trading/swaps based on sentiment → chain: fetch_rss → analyze_sentiment → execute_dex_swap.\n"
        "4. For on-chain whale detection → use trigger_type \"on_chain_event\".\n"
        "5. Steps reference previous step output via {{step_N_output}} variables."
    )

    user_prompt = f"""Parse this user request into a workflow JSON.

User request: "{text}"

═══ AVAILABLE ACTION TYPES (in order of preference) ═══

1. "fetch_rss": Fetch news/articles from RSS. MANDATORY for any news request.
   config: {{"feed_url": "https://...", "max_items": 5}}
   Known RSS feeds:
     Crypto: "https://cointelegraph.com/rss"
     Crypto alt: "https://www.coindesk.com/arc/outboundfeeds/rss/"
     Tech: "https://feeds.arstechnica.com/arstechnica/index"
     Finance: "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US"
     AI/ML: "https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml"
     General: "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"
     Algorand/Web3: "https://cointelegraph.com/rss"

2. "analyze_sentiment": LLM sentiment analysis of text (usually RSS output). Returns bearish/bullish/neutral + score 0-100.
   config: {{"text": "{{{{step_N_output}}}}"}}  (leave empty to auto-use previous step output)

3. "execute_dex_swap": Build unsigned ALGO→USDC swap & send Telegram approval button.
   config: {{"amount_algo": 2.0, "reason": "Bearish sentiment protection", "tg_id": {tg_id}, "dynamic_amount": true, "bearish_amount": 5.0, "cautious_amount": 2.0}}
   - If dynamic_amount=true: amount scales based on sentiment score (bearish=bearish_amount, cautious=cautious_amount)
   - User must have /connect_wallet linked. They approve the swap in the Mini App.

4. "ai_analyze": Run AI swarm analysis. config: {{"prompt": "what to analyze"}}
5. "stock_lookup": Get stock price data. config: {{"ticker": "AAPL"}}
6. "youtube_research": Analyze a YouTube video. config: {{"url": "youtube url"}}
7. "send_message": Send Telegram message. config: {{"message": "{{{{step_N_output}}}}", "tg_id": {tg_id}}}
8. "http_request": Make HTTP call. config: {{"url": "...", "method": "GET"}}
9. "web_scrape": Scrape a specific non-news webpage ONLY. config: {{"query": "search query"}}
10. "condition": Check a condition. config: {{"condition": "expression"}}
11. "delay": Wait N seconds. config: {{"seconds": 10}}
12. "transform": Format data. config: {{"template": "text with {{{{variables}}}}"}}

═══ AVAILABLE TRIGGER TYPES ═══

- "interval": Repeat every N minutes. config: {{"interval_minutes": 60}}
- "price_threshold": When stock hits price. config: {{"ticker": "AAPL", "threshold": 150, "direction": "below"}}
- "on_chain_event": Algorand on-chain events (whale alerts). config: {{"event_type": "whale_transfer", "min_algo": 10000, "watch_address": ""}}
- "time_once": Run at specific time. config: {{"at": "ISO datetime"}}
- "manual": Only runs when user triggers it.

═══ EXAMPLE PIPELINES ═══

EXAMPLE 1 — "Fetch crypto news, analyze sentiment, and swap if bearish":
{{
  "name": "DeFi Sentiment Guard",
  "description": "Monitors crypto news, analyzes sentiment, triggers protective swap if bearish",
  "trigger_type": "interval",
  "trigger_config": {{"interval_minutes": 30}},
  "steps": [
    {{"name": "Fetch Crypto News", "type": "fetch_rss", "config": {{"feed_url": "https://cointelegraph.com/rss", "max_items": 5}}}},
    {{"name": "Analyze Sentiment", "type": "analyze_sentiment", "config": {{}}}},
    {{"name": "Execute Swap", "type": "execute_dex_swap", "config": {{"amount_algo": 2.0, "reason": "Bearish news detected — protective ALGO→USDC swap", "tg_id": {tg_id}, "dynamic_amount": true, "bearish_amount": 5.0, "cautious_amount": 2.0}}}}
  ]
}}

EXAMPLE 2 — "When a whale moves >10K ALGO, alert me and analyze":
{{
  "name": "Whale Alert Pipeline",
  "description": "Detects large Algorand transfers and sends analysis",
  "trigger_type": "on_chain_event",
  "trigger_config": {{"event_type": "whale_transfer", "min_algo": 10000}},
  "steps": [
    {{"name": "Analyze Event", "type": "ai_analyze", "config": {{"prompt": "A whale just moved {{{{_whale_txn}}}} on Algorand. What does this mean for the market?"}}}},
    {{"name": "Notify User", "type": "send_message", "config": {{"message": "🐋 Whale Alert!\\n\\n{{{{step_1_output}}}}", "tg_id": {tg_id}}}}}
  ]
}}

EXAMPLE 3 — "Every 10 minutes fetch crypto news and send it to me":
{{
  "name": "Crypto News Feed",
  "description": "Fetches latest crypto news from CoinTelegraph RSS and sends to user",
  "trigger_type": "interval",
  "trigger_config": {{"interval_minutes": 10}},
  "steps": [
    {{"name": "Fetch Crypto News", "type": "fetch_rss", "config": {{"feed_url": "https://cointelegraph.com/rss", "max_items": 5}}}},
    {{"name": "Send News", "type": "send_message", "config": {{"message": "{{{{step_1_output}}}}", "tg_id": {tg_id}}}}}
  ]
}}

RULES:
- For ANY request involving "news", "headlines", "articles", "updates", "latest" → use "fetch_rss". NEVER "web_scrape".
- For sentiment/mood/market-feel → chain fetch_rss → analyze_sentiment.
- For autonomous trading/protection/swap → chain fetch_rss → analyze_sentiment → execute_dex_swap.
- For whale watching/large transfers → use trigger_type "on_chain_event".
- send_message should reference data from earlier steps using {{{{step_N_output}}}}.
- Pick the most relevant RSS feed URL based on the user's topic.

Respond with ONLY this JSON structure:
{{
    "name": "short name",
    "description": "what this workflow does",
    "trigger_type": "one of above",
    "trigger_config": {{}},
    "steps": [
        {{"name": "Step Name", "type": "action_type", "config": {{}}}}
    ]
}}"""

    resp = groq.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=800,
    )
    raw = resp.choices[0].message.content
    parsed = _safe_parse_json(raw)

    # ── Post-processing safety net: auto-swap web_scrape → fetch_rss for news ──
    parsed = _enforce_rss_for_news(parsed, text, tg_id)

    return parsed


# RSS feed URL mapping for common news topics
_RSS_FEED_MAP = {
    "crypto":     "https://cointelegraph.com/rss",
    "bitcoin":    "https://cointelegraph.com/rss",
    "blockchain": "https://cointelegraph.com/rss",
    "ethereum":   "https://cointelegraph.com/rss",
    "defi":       "https://cointelegraph.com/rss",
    "web3":       "https://cointelegraph.com/rss",
    "tech":       "https://feeds.arstechnica.com/arstechnica/index",
    "technology": "https://feeds.arstechnica.com/arstechnica/index",
    "ai":         "https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml",
    "artificial intelligence": "https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml",
    "finance":    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    "stock":      "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    "market":     "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
}
_NEWS_KEYWORDS = re.compile(
    r'\b(news|headlines|articles|latest|updates|feed|digest|bulletin)\b', re.IGNORECASE
)


def _enforce_rss_for_news(parsed: dict, user_text: str, tg_id: int) -> dict:
    """
    Post-processing guard: if the LLM still generated a web_scrape step for
    something that looks like a news request, auto-replace it with fetch_rss.
    """
    steps = parsed.get("steps", [])
    user_lower = user_text.lower()
    is_news_request = bool(_NEWS_KEYWORDS.search(user_text))

    changed = False
    for step in steps:
        if step.get("type") != "web_scrape":
            continue

        # Check if this web_scrape step's query or the user's original text
        # indicates a news request
        query = step.get("config", {}).get("query", "").lower()
        step_looks_like_news = bool(_NEWS_KEYWORDS.search(query)) or is_news_request

        if step_looks_like_news:
            # Determine best RSS feed from topic keywords
            feed_url = "https://cointelegraph.com/rss"  # default
            for keyword, url in _RSS_FEED_MAP.items():
                if keyword in user_lower or keyword in query:
                    feed_url = url
                    break

            logger.warning(
                "🔄 Auto-swapping web_scrape → fetch_rss for step '%s' (query=%r → feed=%s)",
                step.get("name", "?"), query, feed_url,
            )
            step["type"] = "fetch_rss"
            step["config"] = {"feed_url": feed_url, "max_items": 5}
            changed = True

    if changed:
        parsed["steps"] = steps

    return parsed


# ═══════════════════════════════════════════════════════════════════
#  NATURAL LANGUAGE SCHEDULED MESSAGE PARSER
# ═══════════════════════════════════════════════════════════════════

async def parse_scheduled_message_nl(text: str) -> dict:
    """Parse natural language into a scheduled message config."""
    from groq import Groq

    groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

    system_prompt = (
        "You are a JSON-only schedule parser. "
        "You MUST respond with ONLY a single raw JSON object. "
        "Do NOT include any markdown formatting, code fences, backticks, "
        "introductory text, explanations, or trailing commentary. "
        "Your entire response must be parseable by json.loads() directly."
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    user_prompt = f"""Parse this scheduling request into JSON. Current UTC time: {now_iso}

User request: "{text}"

Respond with ONLY this JSON structure (no other text):
{{
    "message": "the message to send",
    "run_at": "ISO 8601 datetime in UTC when to send it (null if immediate repeat)",
    "repeat": true/false,
    "repeat_interval_min": minutes between repeats (0 if no repeat)
}}

Examples:
- "remind me to check stocks in 30 minutes" → run_at: 30min from now, repeat: false
- "send me a good morning message every day at 8am" → run_at: next 8am UTC, repeat: true, interval: 1440
- "every hour tell me to stretch" → run_at: null, repeat: true, interval: 60"""

    resp = groq.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=300,
    )
    raw = resp.choices[0].message.content
    return _safe_parse_json(raw)


def _safe_parse_json(raw: str) -> dict:
    """
    Robustly extract JSON from LLM output that may contain markdown fences,
    introductory text, trailing commentary, or other non-JSON content.

    Strategy:
      1. Strip ```json / ``` markdown fences
      2. Try json.loads() on the cleaned string
      3. Use regex to extract the first { ... } block
      4. Fall back to balanced-brace extraction for nested objects
    """
    # ── Step 1: Strip markdown code fences ──
    cleaned = raw.strip()
    cleaned = re.sub(r'^```(?:json|JSON)?\s*\n?', '', cleaned)
    cleaned = re.sub(r'\n?\s*```\s*$', '', cleaned)
    cleaned = cleaned.strip()

    # ── Step 2: Try direct parse ──
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # ── Step 3: Regex extraction — grab first { ... } block ──
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # ── Step 4: Balanced-brace extraction for nested JSON ──
    start = cleaned.find('{')
    if start < 0:
        raise ValueError("No JSON object found in response")

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        c = cleaned[i]
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start:i+1])
                except json.JSONDecodeError:
                    continue

    # ── Last resort: first { to last } ──
    json_end = cleaned.rfind('}') + 1
    if json_end > start:
        return json.loads(cleaned[start:json_end])

    raise ValueError("No JSON object found in response")
