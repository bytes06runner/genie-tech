"""
rule_engine.py — Dynamic Rule Engine + Groww Mock Executor
=============================================================
Users can set conditional trading rules via Telegram or the Web Dashboard.
Rules are stored in SQLite alongside user data.

Example rule:
  "If RSI < 30 and YouTube sentiment is bullish, buy 10 shares of AAPL"

Components:
  DynamicRuleEngine — CRUD for rules, evaluation engine
  GrowwMockExecutor — Simulates Groww-style trade execution with realistic
                      slippage, fees, timestamps, and order IDs

APScheduler integration: runs every 60 seconds to evaluate all active rules.
"""

import asyncio
import json
import logging
import os
import random
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("rule_engine")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_rule_tables():
    """Create the rules and mock_trades tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rules (
            id          TEXT    PRIMARY KEY,
            tg_id       INTEGER NOT NULL,
            name        TEXT    NOT NULL,
            asset       TEXT    NOT NULL,
            conditions  TEXT    NOT NULL,
            action_type TEXT    NOT NULL DEFAULT 'buy',
            amount_usd  REAL    NOT NULL DEFAULT 100.0,
            status      TEXT    NOT NULL DEFAULT 'active',
            created_at  TEXT    NOT NULL,
            last_eval   TEXT,
            trigger_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS mock_trades (
            id              TEXT    PRIMARY KEY,
            rule_id         TEXT,
            tg_id           INTEGER NOT NULL,
            asset           TEXT    NOT NULL,
            side            TEXT    NOT NULL,
            quantity_usd    REAL    NOT NULL,
            execution_price REAL    NOT NULL,
            slippage_pct    REAL    NOT NULL,
            fee_usd         REAL    NOT NULL,
            net_cost        REAL    NOT NULL,
            platform        TEXT    NOT NULL DEFAULT 'groww_mock',
            status          TEXT    NOT NULL DEFAULT 'filled',
            executed_at     TEXT    NOT NULL,
            order_id        TEXT    NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    logger.info("📦 Rule engine tables initialised")


# Initialize on import
init_rule_tables()


# ═══════════════════════════════════════════════
#  Dynamic Rule Engine
# ═══════════════════════════════════════════════

class DynamicRuleEngine:
    """CRUD + evaluation for user-defined conditional trading rules."""

    @staticmethod
    async def create_rule(
        tg_id: int,
        name: str,
        asset: str,
        conditions: dict,
        action_type: str = "buy",
        amount_usd: float = 100.0,
    ) -> dict:
        """
        Create a new conditional rule.
        conditions format: {
            "price_below": 150.0,
            "rsi_below": 30,
            "sentiment": "bullish",
            "logic": "AND"  # AND / OR
        }
        """
        def _op():
            conn = _get_conn()
            rule_id = "rule_" + uuid4().hex[:8]
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO rules (id, tg_id, name, asset, conditions, action_type, amount_usd, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)",
                (rule_id, tg_id, name, asset.upper(), json.dumps(conditions), action_type, amount_usd, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
            conn.close()
            return dict(row)

        return await asyncio.get_event_loop().run_in_executor(None, _op)

    @staticmethod
    async def get_user_rules(tg_id: int) -> list:
        def _op():
            conn = _get_conn()
            rows = conn.execute(
                "SELECT * FROM rules WHERE tg_id = ? ORDER BY created_at DESC", (tg_id,)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        return await asyncio.get_event_loop().run_in_executor(None, _op)

    @staticmethod
    async def get_active_rules() -> list:
        def _op():
            conn = _get_conn()
            rows = conn.execute("SELECT * FROM rules WHERE status = 'active'").fetchall()
            conn.close()
            return [dict(r) for r in rows]
        return await asyncio.get_event_loop().run_in_executor(None, _op)

    @staticmethod
    async def deactivate_rule(rule_id: str) -> bool:
        def _op():
            conn = _get_conn()
            conn.execute("UPDATE rules SET status = 'paused' WHERE id = ?", (rule_id,))
            conn.commit()
            conn.close()
        await asyncio.get_event_loop().run_in_executor(None, _op)
        return True

    @staticmethod
    async def delete_rule(rule_id: str) -> bool:
        def _op():
            conn = _get_conn()
            conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            conn.commit()
            conn.close()
        await asyncio.get_event_loop().run_in_executor(None, _op)
        return True

    @staticmethod
    async def evaluate_rule(rule: dict, current_price: Optional[float] = None) -> bool:
        """
        Evaluate a rule's conditions against current market state.
        Returns True if all conditions are met.
        """
        conditions = json.loads(rule["conditions"]) if isinstance(rule["conditions"], str) else rule["conditions"]
        logic = conditions.get("logic", "AND")
        results = []

        # Price conditions
        if "price_below" in conditions and current_price is not None:
            results.append(current_price <= conditions["price_below"])
        if "price_above" in conditions and current_price is not None:
            results.append(current_price >= conditions["price_above"])

        # RSI condition (simulated — real RSI would need historical data)
        if "rsi_below" in conditions:
            simulated_rsi = random.uniform(20, 80)
            results.append(simulated_rsi <= conditions["rsi_below"])
            logger.debug("Simulated RSI for %s: %.1f (threshold: %s)",
                         rule["asset"], simulated_rsi, conditions["rsi_below"])

        if "rsi_above" in conditions:
            simulated_rsi = random.uniform(20, 80)
            results.append(simulated_rsi >= conditions["rsi_above"])

        # Sentiment condition (would integrate with YT research in production)
        if "sentiment" in conditions:
            # In production, this would query the latest YT sentiment analysis
            # For hackathon demo, we evaluate it as True to show the flow
            results.append(True)

        if not results:
            return False

        if logic == "OR":
            return any(results)
        return all(results)  # Default: AND

    @staticmethod
    async def mark_triggered(rule_id: str):
        def _op():
            conn = _get_conn()
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE rules SET trigger_count = trigger_count + 1, last_eval = ? WHERE id = ?",
                (now, rule_id),
            )
            conn.commit()
            conn.close()
        await asyncio.get_event_loop().run_in_executor(None, _op)


# ═══════════════════════════════════════════════
#  Groww Mock Executor
# ═══════════════════════════════════════════════

class GrowwMockExecutor:
    """
    Simulates a Groww-style trade execution with:
    - Realistic slippage (0.01% - 0.15%)
    - Brokerage fee (₹20 flat or 0.03%)
    - Order ID generation mimicking Groww format
    - Execution timestamp + webhook-style response
    """

    PLATFORM = "groww_mock"
    BASE_FEE_USD = 0.25  # $0.25 flat fee equivalent
    FEE_RATE = 0.0003    # 0.03% variable fee

    @staticmethod
    async def execute_trade(
        tg_id: int,
        asset: str,
        side: str,
        quantity_usd: float,
        market_price: float,
        rule_id: Optional[str] = None,
    ) -> dict:
        """
        Execute a mock trade with realistic simulation.
        Returns a Groww-webhook-style response.
        """
        def _op():
            # Calculate slippage (market impact)
            slippage_pct = random.uniform(0.0001, 0.0015)  # 0.01% - 0.15%
            if side == "buy":
                execution_price = market_price * (1 + slippage_pct)
            else:
                execution_price = market_price * (1 - slippage_pct)

            # Calculate fees
            fee_usd = max(GrowwMockExecutor.BASE_FEE_USD,
                          quantity_usd * GrowwMockExecutor.FEE_RATE)
            net_cost = round(quantity_usd + fee_usd, 2) if side == "buy" else round(quantity_usd - fee_usd, 2)

            # Generate Groww-style order ID
            order_id = f"GRW-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"
            trade_id = f"mt_{uuid4().hex[:10]}"
            now = datetime.now(timezone.utc).isoformat()

            # Store in DB
            conn = _get_conn()
            conn.execute(
                """INSERT INTO mock_trades 
                   (id, rule_id, tg_id, asset, side, quantity_usd, execution_price, 
                    slippage_pct, fee_usd, net_cost, platform, status, executed_at, order_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'filled', ?, ?)""",
                (trade_id, rule_id, tg_id, asset.upper(), side, quantity_usd,
                 round(execution_price, 4), round(slippage_pct * 100, 4),
                 round(fee_usd, 4), net_cost, GrowwMockExecutor.PLATFORM, now, order_id),
            )
            conn.commit()
            conn.close()

            # Return Groww-webhook-style response
            return {
                "status": "filled",
                "order_id": order_id,
                "trade_id": trade_id,
                "platform": "Groww (Mock)",
                "asset": asset.upper(),
                "side": side,
                "quantity_usd": quantity_usd,
                "market_price": round(market_price, 4),
                "execution_price": round(execution_price, 4),
                "slippage_pct": round(slippage_pct * 100, 4),
                "fee_usd": round(fee_usd, 4),
                "net_cost": round(net_cost, 2),
                "executed_at": now,
                "webhook_event": "order.filled",
                "message": f"✅ {side.upper()} {asset.upper()} — ${quantity_usd:.2f} filled @ ${execution_price:.4f} "
                           f"(slippage: {slippage_pct*100:.3f}%, fee: ${fee_usd:.4f})",
            }

        return await asyncio.get_event_loop().run_in_executor(None, _op)

    @staticmethod
    async def get_trade_history(tg_id: int, limit: int = 20) -> list:
        def _op():
            conn = _get_conn()
            rows = conn.execute(
                "SELECT * FROM mock_trades WHERE tg_id = ? ORDER BY executed_at DESC LIMIT ?",
                (tg_id, limit),
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        return await asyncio.get_event_loop().run_in_executor(None, _op)


# ═══════════════════════════════════════════════
#  Rule Evaluation Loop (called by APScheduler)
# ═══════════════════════════════════════════════

_tg_notify_fn = None

def set_rule_notify(fn):
    global _tg_notify_fn
    _tg_notify_fn = fn


async def evaluate_all_rules():
    """
    APScheduler callback: evaluate all active rules every 60 seconds.
    If conditions are met → execute via GrowwMockExecutor → notify user.
    """
    from market_monitor import fetch_current_price

    rules = await DynamicRuleEngine.get_active_rules()
    if not rules:
        return

    logger.info("⚙️ Rule engine tick: evaluating %d active rules", len(rules))

    for rule in rules:
        try:
            price = await fetch_current_price(rule["asset"])
            triggered = await DynamicRuleEngine.evaluate_rule(rule, price)

            if triggered:
                logger.info("🚨 Rule triggered: %s (asset: %s)", rule["id"], rule["asset"])

                # Execute via Groww Mock
                trade_result = await GrowwMockExecutor.execute_trade(
                    tg_id=rule["tg_id"],
                    asset=rule["asset"],
                    side=rule.get("action_type", "buy"),
                    quantity_usd=rule["amount_usd"],
                    market_price=price or 100.0,
                    rule_id=rule["id"],
                )

                await DynamicRuleEngine.mark_triggered(rule["id"])

                # Notify user via Telegram
                if _tg_notify_fn:
                    msg = (
                        f"🚨 *Rule Engine — Auto-Execution*\n\n"
                        f"📋 Rule: `{rule['name']}`\n"
                        f"📊 Asset: `{rule['asset']}`\n"
                        f"💰 Order: `{trade_result['order_id']}`\n"
                        f"📈 Price: ${trade_result['execution_price']:.4f}\n"
                        f"💸 Cost: ${trade_result['net_cost']:.2f} (fee: ${trade_result['fee_usd']:.4f})\n"
                        f"📉 Slippage: {trade_result['slippage_pct']:.3f}%\n\n"
                        f"_Executed by X10V Dynamic Rule Engine via Groww Mock_"
                    )
                    await _tg_notify_fn(rule["tg_id"], msg)

        except Exception as e:
            logger.error("Rule evaluation error for %s: %s", rule["id"], e)


# ═══════════════════════════════════════════════
#  Smart Suggestions via Groq
# ═══════════════════════════════════════════════

async def get_smart_suggestions(tg_id: int) -> str:
    """
    Analyze user's current rules and suggest optimisations.
    Uses Groq Llama-3.1-8b for fast inference.
    """
    rules = await DynamicRuleEngine.get_user_rules(tg_id)
    trades = await GrowwMockExecutor.get_trade_history(tg_id, limit=10)

    if not rules and not trades:
        return (
            "📊 *Smart Suggestions*\n\n"
            "You don't have any active rules or trade history yet.\n\n"
            "Try these to get started:\n"
            "• `/set_rule Buy AAPL if price below 180` — set a conditional rule\n"
            "• `/analyze BTC` — get AI swarm analysis\n"
            "• Say *\"Monitor gold below 2000\"* on the web dashboard voice AI"
        )

    from groq import Groq
    groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

    rules_summary = "\n".join([
        f"- {r['name']} | {r['asset']} | conditions: {r['conditions']} | triggered: {r['trigger_count']}x | status: {r['status']}"
        for r in rules
    ])

    trades_summary = "\n".join([
        f"- {t['side']} {t['asset']} ${t['quantity_usd']} @ ${t['execution_price']} | slippage: {t['slippage_pct']}% | {t['executed_at']}"
        for t in trades[:5]
    ])

    prompt = f"""You are an expert financial AI advisor for the X10V trading platform.
Analyze this user's automation rules and recent trades, then suggest 2-3 specific optimizations.

ACTIVE RULES:
{rules_summary or "None"}

RECENT TRADES:
{trades_summary or "None"}

Provide concise, actionable suggestions. Use Telegram Markdown formatting (*bold*, `code`).
Focus on: risk management, diversification, better entry conditions, and automation improvements.
Keep it under 200 words."""

    def _call():
        resp = groq.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=400,
        )
        return resp.choices[0].message.content

    result = await asyncio.get_event_loop().run_in_executor(None, _call)
    return f"🧠 *Smart Suggestions*\n\n{result}"
