"""
dex_automation.py — Smart DEX Trade Automation Engine
========================================================
AI-powered automated trading on DEX Screener tokens.

Features:
  🤖 AI analysis before every trade execution (3-LLM Swarm)
  📊 Limit orders — buy/sell when price hits target
  🔄 Auto-recheck loop every 60 seconds
  🔗 Algorand wallet integration — pre-authorized transactions
  💰 Paper trading fallback when no wallet connected

Order Lifecycle:
  1. User sets an order (token, side, target_price, amount_usd)
  2. Scheduler checks DEX Screener prices every 60s
  3. When price condition is met → AI Swarm re-analyzes the token
  4. If AI confirms → executes trade (paper or on-chain)
  5. User gets notified via WebSocket broadcast

Tables (SQLite):
  dex_orders — Active/completed/cancelled smart orders
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Callable

import aiosqlite

logger = logging.getLogger("dex_automation")

DB_PATH = os.getenv("USERS_DB_PATH", "users.db")

# ── WebSocket broadcast callback (wired by server.py) ──
_ws_broadcast: Optional[Callable] = None


def set_automation_broadcast(fn: Callable):
    """Wire the WebSocket broadcast callback."""
    global _ws_broadcast
    _ws_broadcast = fn
    logger.info("✅ DEX Automation broadcast callback wired")


async def _broadcast(msg: str):
    if _ws_broadcast:
        try:
            await _ws_broadcast(msg)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════════

async def init_dex_automation_db():
    """Create the dex_orders table."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dex_orders (
                id              TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL DEFAULT 'web',
                wallet_address  TEXT DEFAULT '',
                symbol          TEXT NOT NULL,
                chain           TEXT NOT NULL DEFAULT '',
                dex             TEXT NOT NULL DEFAULT '',
                side            TEXT NOT NULL DEFAULT 'buy',
                order_type      TEXT NOT NULL DEFAULT 'limit',
                target_price    REAL NOT NULL,
                amount_usd      REAL NOT NULL DEFAULT 100.0,
                stop_loss       REAL DEFAULT 0,
                take_profit     REAL DEFAULT 0,
                current_price   REAL DEFAULT 0,
                ai_confirmed    INTEGER DEFAULT 0,
                ai_reason       TEXT DEFAULT '',
                ai_score        REAL DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'active',
                fills           INTEGER DEFAULT 0,
                pnl             REAL DEFAULT 0,
                created_at      TEXT NOT NULL,
                executed_at     TEXT,
                cancelled_at    TEXT,
                last_checked    TEXT,
                pair_address    TEXT DEFAULT '',
                search_query    TEXT DEFAULT ''
            )
        """)
        await db.commit()
    logger.info("✅ DEX Automation DB initialized")


# ═══════════════════════════════════════════════════════════════════
#  ORDER CRUD
# ═══════════════════════════════════════════════════════════════════

async def create_order(
    symbol: str,
    chain: str,
    side: str,
    target_price: float,
    amount_usd: float,
    user_id: str = "web",
    wallet_address: str = "",
    stop_loss: float = 0,
    take_profit: float = 0,
    order_type: str = "limit",
    dex: str = "",
    pair_address: str = "",
    search_query: str = "",
) -> dict:
    """Create a new smart order."""
    order_id = f"dxo_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()

    order = {
        "id": order_id,
        "user_id": user_id,
        "wallet_address": wallet_address,
        "symbol": symbol.upper(),
        "chain": chain,
        "dex": dex,
        "side": side.lower(),
        "order_type": order_type,
        "target_price": target_price,
        "amount_usd": amount_usd,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "current_price": 0,
        "ai_confirmed": 0,
        "ai_reason": "",
        "ai_score": 0,
        "status": "active",
        "fills": 0,
        "pnl": 0,
        "created_at": now,
        "executed_at": None,
        "cancelled_at": None,
        "last_checked": None,
        "pair_address": pair_address,
        "search_query": search_query or symbol,
    }

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO dex_orders
               (id, user_id, wallet_address, symbol, chain, dex, side, order_type,
                target_price, amount_usd, stop_loss, take_profit, status, created_at,
                pair_address, search_query)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (order_id, user_id, wallet_address, symbol.upper(), chain, dex, side.lower(),
             order_type, target_price, amount_usd, stop_loss, take_profit, "active", now,
             pair_address, search_query or symbol),
        )
        await db.commit()

    logger.info("📝 Order created: %s %s %s @ $%s ($%s)",
                order_id, side, symbol, target_price, amount_usd)
    await _broadcast(
        f"[DexAuto] 📝 New {side.upper()} order: {symbol} @ ${target_price} (${amount_usd})"
    )
    return order


async def get_active_orders(user_id: str = None) -> list:
    """Get all active orders, optionally filtered by user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if user_id:
            cursor = await db.execute(
                "SELECT * FROM dex_orders WHERE status = 'active' AND user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM dex_orders WHERE status = 'active' ORDER BY created_at DESC"
            )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_all_orders(user_id: str = None, limit: int = 50) -> list:
    """Get all orders (active + history)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if user_id:
            cursor = await db.execute(
                "SELECT * FROM dex_orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM dex_orders ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def cancel_order(order_id: str) -> bool:
    """Cancel an active order."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE dex_orders SET status = 'cancelled', cancelled_at = ? WHERE id = ? AND status = 'active'",
            (now, order_id),
        )
        await db.commit()
        changed = cursor.rowcount > 0

    if changed:
        logger.info("❌ Order cancelled: %s", order_id)
        await _broadcast(f"[DexAuto] ❌ Order {order_id} cancelled")
    return changed


async def _mark_executed(order_id: str, ai_reason: str, ai_score: float, current_price: float, pnl: float = 0):
    """Mark order as executed after AI confirmation."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE dex_orders SET
                status = 'executed', executed_at = ?, ai_confirmed = 1,
                ai_reason = ?, ai_score = ?, current_price = ?, pnl = ?, fills = fills + 1
               WHERE id = ?""",
            (now, ai_reason, ai_score, current_price, pnl, order_id),
        )
        await db.commit()


async def _update_check(order_id: str, current_price: float, ai_reason: str = "", ai_score: float = 0):
    """Update the last check timestamp and current price."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE dex_orders SET last_checked = ?, current_price = ?, ai_reason = ?, ai_score = ? WHERE id = ?",
            (now, current_price, ai_reason, ai_score, order_id),
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════════════
#  AI TRADE ANALYSIS — Should we execute this order right now?
# ═══════════════════════════════════════════════════════════════════

async def _ai_should_execute(symbol: str, side: str, current_price: float, target_price: float,
                              pair_data: dict) -> dict:
    """
    Ask the 3-LLM Swarm whether this trade should execute NOW.
    Returns: {should_execute: bool, confidence: float, reason: str}
    """
    from swarm_brain import run_swarm

    vol_24h = pair_data.get("volume_24h", 0)
    liq = pair_data.get("liquidity_usd", 0)
    buys_1h = pair_data.get("buys_1h", 0)
    sells_1h = pair_data.get("sells_1h", 0)
    change_1h = pair_data.get("price_change_1h", 0)
    change_24h = pair_data.get("price_change_24h", 0)
    bs_ratio = pair_data.get("buy_sell_ratio_1h", 0)
    mcap = pair_data.get("market_cap", 0)

    prompt = (
        f"You are an expert crypto trader making a REAL trade decision.\n\n"
        f"TRADE ORDER:\n"
        f"  Token: {symbol}\n"
        f"  Side: {side.upper()}\n"
        f"  Target price: ${target_price}\n"
        f"  Current price: ${current_price}\n\n"
        f"LIVE MARKET DATA:\n"
        f"  Volume 24h: ${vol_24h:,.0f}\n"
        f"  Liquidity: ${liq:,.0f}\n"
        f"  Buy/Sell ratio (1h): {bs_ratio:.2f} ({buys_1h} buys / {sells_1h} sells)\n"
        f"  Price change 1h: {change_1h:+.2f}%\n"
        f"  Price change 24h: {change_24h:+.2f}%\n"
        f"  Market cap: ${mcap:,.0f}\n\n"
        f"DECISION CRITERIA:\n"
        f"  For BUY: Confirm price has reached/dipped to target. Check if momentum supports entry.\n"
        f"  For SELL: Confirm price has reached/risen to target. Check if selling pressure indicates top.\n"
        f"  Consider: volume spike, liquidity risk, buy/sell imbalance, trend direction.\n\n"
        f"RESPOND with EXACTLY this JSON format:\n"
        f'{{"should_execute": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}'
    )

    try:
        verdict = await run_swarm(
            text_data=prompt,
            user_command=f"Trade decision: {side} {symbol} @ ${target_price}",
        )

        # Parse the structured data from swarm
        sd = verdict.get("structured_data", {})
        summary = sd.get("summary", "")

        # Try to extract the decision from the verdict
        should_execute = False
        confidence = 0.5
        reason = summary[:300] if summary else "AI analysis completed"

        # Check for positive signals in the swarm output
        action = sd.get("action", "").lower()
        if action in ("execute", "buy", "sell", "green"):
            should_execute = True
            confidence = 0.8
        elif action in ("abort", "hold", "wait", "red"):
            should_execute = False
            confidence = 0.7

        # Also look at the signal color
        signal = sd.get("signal", "").lower()
        if signal == "green":
            should_execute = True
            confidence = max(confidence, 0.75)
        elif signal == "red":
            should_execute = False

        # Buy-side: strong buying pressure is good
        if side == "buy" and bs_ratio > 1.3 and change_1h > 0:
            confidence = min(confidence + 0.1, 1.0)
        # Sell-side: strong selling pressure confirms sell
        if side == "sell" and bs_ratio < 0.7:
            confidence = min(confidence + 0.1, 1.0)

        return {
            "should_execute": should_execute,
            "confidence": round(confidence, 2),
            "reason": reason,
        }

    except Exception as e:
        logger.error("AI trade analysis failed for %s: %s", symbol, e)
        return {
            "should_execute": False,
            "confidence": 0.0,
            "reason": f"AI analysis failed: {str(e)[:100]}",
        }


# ═══════════════════════════════════════════════════════════════════
#  TRADE EXECUTION
# ═══════════════════════════════════════════════════════════════════

async def _execute_paper_trade(order: dict, current_price: float, ai_result: dict):
    """Execute via paper trading engine."""
    from paper_engine import open_position

    try:
        pos = await open_position(
            tg_id=0,  # Web user
            asset=order["symbol"],
            amount_usd=order["amount_usd"],
            current_price=current_price,
        )
        await _mark_executed(
            order["id"],
            ai_reason=ai_result["reason"],
            ai_score=ai_result["confidence"],
            current_price=current_price,
            pnl=0,
        )
        await _broadcast(
            f"[DexAuto] ✅ EXECUTED {order['side'].upper()} {order['symbol']} "
            f"@ ${current_price:.8f} (${order['amount_usd']}) — "
            f"AI: {ai_result['confidence']*100:.0f}% confident"
        )
        logger.info("✅ Paper trade executed: %s %s @ %s", order["side"], order["symbol"], current_price)
        return True
    except Exception as e:
        logger.error("Paper trade execution failed: %s", e)
        return False


async def _execute_onchain_trade(order: dict, current_price: float, ai_result: dict):
    """Execute via Algorand on-chain transaction."""
    from algorand_indexer import build_unsigned_payment, create_pending_transaction, SAFE_VAULT_ADDRESS

    try:
        # Convert USD amount to ALGO equivalent (simplified)
        # In production, you'd use a real price oracle
        algo_price_usd = 0.25  # Approximate ALGO price
        amount_algo = order["amount_usd"] / algo_price_usd

        pending = await create_pending_transaction(
            tg_id=0,
            sender=order["wallet_address"],
            receiver=SAFE_VAULT_ADDRESS,
            amount_algo=amount_algo,
            note=f"X10V Auto-Trade: {order['side']} {order['symbol']} @ ${current_price}",
            tx_type="dex_auto_trade",
        )

        await _mark_executed(
            order["id"],
            ai_reason=ai_result["reason"],
            ai_score=ai_result["confidence"],
            current_price=current_price,
        )

        await _broadcast(
            f"[DexAuto] 🔗 ON-CHAIN {order['side'].upper()} {order['symbol']} "
            f"@ ${current_price:.8f} — TX pending: {pending['id']} "
            f"({amount_algo:.2f} ALGO)"
        )
        logger.info("🔗 On-chain trade queued: %s → %s", order["id"], pending["id"])
        return True

    except Exception as e:
        logger.error("On-chain execution failed: %s", e)
        # Fallback to paper trade
        return await _execute_paper_trade(order, current_price, ai_result)


# ═══════════════════════════════════════════════════════════════════
#  EVALUATION LOOP — Called by scheduler every 60s
# ═══════════════════════════════════════════════════════════════════

async def evaluate_dex_orders():
    """
    Scheduled job — runs every 60 seconds.
    Checks all active orders against live DEX prices.
    If price condition met → runs AI analysis → executes if confirmed.
    """
    from dex_screener import search_pairs, format_pair_data

    orders = await get_active_orders()
    if not orders:
        return

    logger.info("🔍 Evaluating %d active DEX orders…", len(orders))
    await _broadcast(f"[DexAuto] 🔍 Checking {len(orders)} active orders…")

    for order in orders:
        try:
            # Fetch current price from DEX Screener
            query = order.get("search_query") or order["symbol"]
            pairs = await search_pairs(query)

            if not pairs:
                await _update_check(order["id"], 0, "No pairs found on DEX Screener")
                continue

            # Find the best matching pair
            best_pair = None
            for p in pairs:
                pd = format_pair_data(p)
                if pd["symbol"].upper() == order["symbol"].upper():
                    if order["chain"] and pd["chain"] != order["chain"]:
                        continue
                    best_pair = pd
                    break

            if not best_pair:
                best_pair = format_pair_data(pairs[0])

            current_price = float(best_pair.get("price_usd", 0))
            if current_price <= 0:
                continue

            target = order["target_price"]
            side = order["side"]

            # Check if price condition is met
            condition_met = False
            if side == "buy" and current_price <= target:
                condition_met = True
            elif side == "sell" and current_price >= target:
                condition_met = True

            # Also check stop-loss
            if order.get("stop_loss", 0) > 0:
                if side == "buy" and current_price > order["stop_loss"]:
                    # Price went above stop-loss for a buy order — skip
                    pass
                elif side == "sell" and current_price < order["stop_loss"]:
                    condition_met = True  # Emergency sell at stop-loss

            if not condition_met:
                await _update_check(order["id"], current_price,
                                    f"Price ${current_price:.8f} hasn't reached target ${target}")
                continue

            # ── Price condition met → Run AI analysis ──
            await _broadcast(
                f"[DexAuto] 🎯 {order['symbol']} hit target! "
                f"Price: ${current_price:.8f} (target: ${target}). Running AI analysis…"
            )

            ai_result = await _ai_should_execute(
                symbol=order["symbol"],
                side=side,
                current_price=current_price,
                target_price=target,
                pair_data=best_pair,
            )

            logger.info("🤖 AI decision for %s: execute=%s confidence=%.2f",
                        order["symbol"], ai_result["should_execute"], ai_result["confidence"])

            if not ai_result["should_execute"]:
                await _update_check(
                    order["id"], current_price,
                    f"AI rejected: {ai_result['reason'][:200]}",
                    ai_result["confidence"],
                )
                await _broadcast(
                    f"[DexAuto] 🛑 AI REJECTED {side.upper()} {order['symbol']} — "
                    f"{ai_result['reason'][:100]}"
                )
                continue

            # ── AI confirmed → Execute trade ──
            if order.get("wallet_address"):
                await _execute_onchain_trade(order, current_price, ai_result)
            else:
                await _execute_paper_trade(order, current_price, ai_result)

        except Exception as e:
            logger.error("Order evaluation error for %s: %s", order["id"], e)

        # Rate limit between orders
        await asyncio.sleep(0.5)


# ═══════════════════════════════════════════════════════════════════
#  AI ANALYSIS FOR A SPECIFIC TOKEN (on-demand)
# ═══════════════════════════════════════════════════════════════════

async def analyze_token_for_trade(symbol: str, chain: str = "") -> dict:
    """
    Run AI analysis on a specific token to generate buy/sell recommendation.
    Returns: {recommendation, confidence, entry_price, target_price, stop_loss, reason, data}
    """
    from dex_screener import search_pairs, format_pair_data
    from swarm_brain import run_swarm

    pairs = await search_pairs(symbol)
    if not pairs:
        return {"recommendation": "none", "confidence": 0, "reason": "Token not found on DEX Screener"}

    # Filter by chain if specified
    if chain:
        filtered = [p for p in pairs if p.get("chainId", "") == chain]
        if filtered:
            pairs = filtered

    best = pairs[0]
    pd = format_pair_data(best)
    current_price = float(pd.get("price_usd", 0))

    prompt = (
        f"You are an expert crypto trader. Analyze this token and provide a trade recommendation.\n\n"
        f"TOKEN: {pd.get('symbol')} on {pd.get('chain')} ({pd.get('dex')})\n"
        f"Current Price: ${current_price}\n"
        f"Volume 24h: ${pd.get('volume_24h', 0):,.0f}\n"
        f"Liquidity: ${pd.get('liquidity_usd', 0):,.0f}\n"
        f"Market Cap: ${pd.get('market_cap', 0):,.0f}\n"
        f"Buy/Sell Ratio 1h: {pd.get('buy_sell_ratio_1h', 0):.2f}\n"
        f"Buys 1h: {pd.get('buys_1h', 0)} | Sells 1h: {pd.get('sells_1h', 0)}\n"
        f"Price Change 5m: {pd.get('price_change_5m', 0):+.2f}%\n"
        f"Price Change 1h: {pd.get('price_change_1h', 0):+.2f}%\n"
        f"Price Change 24h: {pd.get('price_change_24h', 0):+.2f}%\n\n"
        f"Provide your analysis as JSON:\n"
        f'{{"recommendation": "buy"/"sell"/"hold", "confidence": 0.0-1.0, '
        f'"entry_price": suggested_entry, "target_price": take_profit_price, '
        f'"stop_loss": stop_loss_price, "reason": "detailed explanation"}}'
    )

    try:
        verdict = await run_swarm(
            text_data=prompt,
            user_command=f"Trade analysis: {symbol}",
        )
        sd = verdict.get("structured_data", {})
        summary = sd.get("summary", "")
        action = sd.get("action", "hold").lower()

        recommendation = "hold"
        if action in ("buy", "execute", "green"):
            recommendation = "buy"
        elif action in ("sell", "abort", "red"):
            recommendation = "sell"

        signal = sd.get("signal", "").lower()
        if signal == "green":
            recommendation = "buy"
        elif signal == "red":
            recommendation = "sell"

        confidence = 0.5
        if recommendation != "hold":
            confidence = 0.7
            bs = pd.get("buy_sell_ratio_1h", 1)
            if recommendation == "buy" and bs > 1.3:
                confidence = min(confidence + 0.15, 0.95)
            elif recommendation == "sell" and bs < 0.7:
                confidence = min(confidence + 0.15, 0.95)

        return {
            "recommendation": recommendation,
            "confidence": round(confidence, 2),
            "entry_price": current_price,
            "target_price": current_price * (1.1 if recommendation == "buy" else 0.9),
            "stop_loss": current_price * (0.92 if recommendation == "buy" else 1.08),
            "reason": summary[:500] if summary else "Analysis complete",
            "data": pd,
            "swarm_verdict": sd,
        }

    except Exception as e:
        logger.error("Token analysis failed: %s", e)
        return {
            "recommendation": "hold",
            "confidence": 0,
            "entry_price": current_price,
            "reason": f"Analysis failed: {str(e)[:200]}",
            "data": pd,
        }
