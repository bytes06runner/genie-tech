"""
dex_screener.py — DEX Screener Intelligence Module
=====================================================
Real-time on-chain token data from DEX Screener's free API.
Provides:
  🔍 Token/Pair search (buyers, sellers, volume, liquidity)
  📈 Trending tokens (boosted, top gainers)
  🤖 AI-powered trade opportunity detection via 3-LLM Swarm
  🔔 Scheduled alert engine — scans every 5 minutes and notifies

API Endpoints Used (all free, no key required):
  GET /latest/dex/search?q=...             — Search pairs (300 req/min)
  GET /token-boosts/top/v1                 — Top boosted tokens (60 req/min)
  GET /token-profiles/latest/v1            — Latest token profiles (60 req/min)
  GET /token-boosts/latest/v1              — Latest boosted tokens (60 req/min)
  GET /tokens/v1/{chainId}/{tokenAddress}  — Token pair data (300 req/min)
  GET /token-pairs/v1/{chainId}/{address}  — Token pools (300 req/min)
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, Callable, Awaitable

import aiohttp
import aiosqlite

logger = logging.getLogger("dex_screener")

BASE_URL = "https://api.dexscreener.com"

# ── Notify callback (wired by tg_bot.py) ──
_tg_notify: Optional[Callable] = None
_alert_subscribers: dict[int, dict] = {}  # tg_id → {chain, min_volume, min_liquidity, enabled}


def set_dex_notify(fn: Callable):
    """Wire the Telegram notification callback."""
    global _tg_notify
    _tg_notify = fn
    logger.info("✅ DEX Screener notify callback wired")


# ═══════════════════════════════════════════════════════════════════
#  API CLIENT — Zero-cost, no API key required
# ═══════════════════════════════════════════════════════════════════

async def _api_get(path: str, params: dict = None) -> dict | list | None:
    """Make a GET request to DEX Screener API."""
    url = f"{BASE_URL}{path}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 429:
                    logger.warning("DEX Screener rate limit hit on %s", path)
                    return None
                else:
                    logger.error("DEX Screener API %d on %s", resp.status, path)
                    return None
    except Exception as e:
        logger.error("DEX Screener request failed: %s", e)
        return None


async def search_pairs(query: str) -> list[dict]:
    """
    Search for token pairs matching a query.
    Returns enriched pair data with buy/sell counts, volume, liquidity.
    """
    data = await _api_get("/latest/dex/search", params={"q": query})
    if not data or not data.get("pairs"):
        return []
    return data["pairs"][:20]  # Top 20 results


async def get_token_pairs(chain_id: str, token_address: str) -> list[dict]:
    """Get all pools for a specific token on a specific chain."""
    data = await _api_get(f"/token-pairs/v1/{chain_id}/{token_address}")
    if not data:
        return []
    return data if isinstance(data, list) else [data]


async def get_token_data(chain_id: str, token_addresses: str) -> list[dict]:
    """Get pair data for one or multiple token addresses (comma-separated)."""
    data = await _api_get(f"/tokens/v1/{chain_id}/{token_addresses}")
    if not data:
        return []
    return data if isinstance(data, list) else [data]


async def get_top_boosted() -> list[dict]:
    """Get tokens with the most active boosts (trending/promoted)."""
    data = await _api_get("/token-boosts/top/v1")
    if not data:
        return []
    return data if isinstance(data, list) else [data]


async def get_latest_boosted() -> list[dict]:
    """Get the latest boosted tokens."""
    data = await _api_get("/token-boosts/latest/v1")
    if not data:
        return []
    return data if isinstance(data, list) else [data]


async def get_latest_profiles() -> list[dict]:
    """Get latest token profiles (newly listed/updated tokens)."""
    data = await _api_get("/token-profiles/latest/v1")
    if not data:
        return []
    return data if isinstance(data, list) else [data]


# ═══════════════════════════════════════════════════════════════════
#  DATA FORMATTING — Rich display for Telegram + Frontend
# ═══════════════════════════════════════════════════════════════════

def format_pair_data(pair: dict) -> dict:
    """Extract and format key metrics from a DEX Screener pair object."""
    base = pair.get("baseToken", {})
    quote = pair.get("quoteToken", {})
    txns = pair.get("txns", {})
    volume = pair.get("volume", {})
    price_change = pair.get("priceChange", {})
    liquidity = pair.get("liquidity", {})

    # Extract buy/sell data across timeframes
    buys_5m = txns.get("m5", {}).get("buys", 0)
    sells_5m = txns.get("m5", {}).get("sells", 0)
    buys_1h = txns.get("h1", {}).get("buys", 0)
    sells_1h = txns.get("h1", {}).get("sells", 0)
    buys_6h = txns.get("h6", {}).get("buys", 0)
    sells_6h = txns.get("h6", {}).get("sells", 0)
    buys_24h = txns.get("h24", {}).get("buys", 0)
    sells_24h = txns.get("h24", {}).get("sells", 0)

    return {
        "name": base.get("name", "Unknown"),
        "symbol": base.get("symbol", "???"),
        "chain": pair.get("chainId", "unknown"),
        "dex": pair.get("dexId", "unknown"),
        "pair_address": pair.get("pairAddress", ""),
        "url": pair.get("url", ""),
        "price_usd": pair.get("priceUsd", "0"),
        "price_native": pair.get("priceNative", "0"),
        "quote_symbol": quote.get("symbol", ""),
        # Transaction data
        "buys_5m": buys_5m,
        "sells_5m": sells_5m,
        "buys_1h": buys_1h,
        "sells_1h": sells_1h,
        "buys_6h": buys_6h,
        "sells_6h": sells_6h,
        "buys_24h": buys_24h,
        "sells_24h": sells_24h,
        "total_txns_24h": buys_24h + sells_24h,
        # Buy/Sell ratio
        "buy_sell_ratio_1h": round(buys_1h / sells_1h, 2) if sells_1h > 0 else (999.99 if buys_1h > 0 else 0),
        "buy_sell_ratio_24h": round(buys_24h / sells_24h, 2) if sells_24h > 0 else (999.99 if buys_24h > 0 else 0),
        # Volume
        "volume_5m": volume.get("m5", 0),
        "volume_1h": volume.get("h1", 0),
        "volume_6h": volume.get("h6", 0),
        "volume_24h": volume.get("h24", 0),
        # Price changes
        "price_change_5m": price_change.get("m5", 0),
        "price_change_1h": price_change.get("h1", 0),
        "price_change_6h": price_change.get("h6", 0),
        "price_change_24h": price_change.get("h24", 0),
        # Liquidity
        "liquidity_usd": liquidity.get("usd", 0) if liquidity else 0,
        "fdv": pair.get("fdv", 0),
        "market_cap": pair.get("marketCap", 0),
        # Metadata
        "pair_created_at": pair.get("pairCreatedAt"),
        "boosts": pair.get("boosts", {}).get("active", 0),
    }


def format_pair_telegram(pair_data: dict) -> str:
    """Format a single pair for Telegram display."""
    bs_ratio = pair_data['buy_sell_ratio_1h']
    if bs_ratio >= 999:
        ratio_str = "∞ (all buys)"
    elif bs_ratio == 0:
        ratio_str = "0 (all sells)"
    else:
        ratio_str = f"{bs_ratio:.2f}"

    # Sentiment emoji based on buy/sell ratio
    if bs_ratio > 1.5:
        sentiment = "🟢 Bullish"
    elif bs_ratio > 1.0:
        sentiment = "🟡 Slightly Bullish"
    elif bs_ratio > 0.7:
        sentiment = "🟠 Neutral"
    else:
        sentiment = "🔴 Bearish"

    price_str = f"${float(pair_data['price_usd']):.8f}" if pair_data['price_usd'] else "N/A"

    vol_24h = pair_data['volume_24h']
    vol_str = f"${vol_24h:,.0f}" if vol_24h else "N/A"

    liq_str = f"${pair_data['liquidity_usd']:,.0f}" if pair_data['liquidity_usd'] else "N/A"

    mc_str = f"${pair_data['market_cap']:,.0f}" if pair_data.get('market_cap') else "N/A"

    pc_5m = pair_data['price_change_5m']
    pc_1h = pair_data['price_change_1h']
    pc_24h = pair_data['price_change_24h']

    return (
        f"*{pair_data['symbol']}* / {pair_data['quote_symbol']} "
        f"_({pair_data['chain']} · {pair_data['dex']})_\n"
        f"💰 Price: `{price_str}`\n"
        f"📊 Volume 24h: `{vol_str}`\n"
        f"💧 Liquidity: `{liq_str}`\n"
        f"🏦 Market Cap: `{mc_str}`\n\n"
        f"📈 *Price Change:*\n"
        f"  5m: `{pc_5m:+.2f}%` | 1h: `{pc_1h:+.2f}%` | 24h: `{pc_24h:+.2f}%`\n\n"
        f"🔄 *Buyers vs Sellers (1h):*\n"
        f"  🟢 Buys: `{pair_data['buys_1h']}` | 🔴 Sells: `{pair_data['sells_1h']}`\n"
        f"  Ratio: `{ratio_str}` — {sentiment}\n\n"
        f"🔄 *Buyers vs Sellers (24h):*\n"
        f"  🟢 Buys: `{pair_data['buys_24h']}` | 🔴 Sells: `{pair_data['sells_24h']}`\n"
        f"  Total TXNs: `{pair_data['total_txns_24h']:,}`\n"
    )


# ═══════════════════════════════════════════════════════════════════
#  AI-POWERED OPPORTUNITY DETECTION — 3-LLM Swarm Analysis
# ═══════════════════════════════════════════════════════════════════
#  WHALE DETECTOR — Scan for large USD buy/sell activity
# ═══════════════════════════════════════════════════════════════════

async def scan_whale_activity(min_volume_usd: float = 100_000, limit: int = 10) -> list[dict]:
    """
    Scan DEX Screener for tokens showing whale-level activity.
    Whales are identified by:
      - Extremely high USD volume in short timeframes (5m, 1h)
      - Large buy/sell imbalances (massive one-sided pressure)
      - Volume spikes relative to liquidity (> 2× liq = whale dump/pump)
    Returns a list of whale events sorted by volume intensity.
    """
    whale_events: list[dict] = []

    # Strategy 1: Scan boosted/trending tokens for volume spikes
    boosted = await get_top_boosted()
    if not boosted:
        boosted = await get_latest_boosted()

    profiles = await get_latest_profiles()

    # Combine and deduplicate token candidates
    candidates: list[dict] = []
    seen = set()
    for src in [boosted or [], profiles or []]:
        for token in src[:15]:
            chain = token.get("chainId", "")
            addr = token.get("tokenAddress", "")
            key = f"{chain}:{addr}"
            if chain and addr and key not in seen:
                seen.add(key)
                candidates.append(token)

    # Fetch pair data for each candidate
    for token in candidates[:20]:
        chain = token.get("chainId", "")
        addr = token.get("tokenAddress", "")
        pairs = await get_token_data(chain, addr)
        if not pairs:
            await asyncio.sleep(0.15)
            continue

        best = max(pairs, key=lambda p: p.get("volume", {}).get("h24", 0))
        pd = format_pair_data(best)

        vol_24h = pd.get("volume_24h", 0)
        vol_1h = pd.get("volume_1h", 0)
        vol_5m = pd.get("volume_5m", 0)
        liq = pd.get("liquidity_usd", 0) or 1  # avoid div/0

        buys_1h = pd.get("buys_1h", 0)
        sells_1h = pd.get("sells_1h", 0)
        buys_24h = pd.get("buys_24h", 0)
        sells_24h = pd.get("sells_24h", 0)

        # Skip if below minimum volume threshold
        if vol_24h < min_volume_usd and vol_1h < (min_volume_usd / 24):
            await asyncio.sleep(0.15)
            continue

        # Calculate whale indicators
        vol_liq_ratio = vol_24h / liq if liq > 0 else 0
        buy_sell_diff_1h = abs(buys_1h - sells_1h)
        buy_sell_diff_24h = abs(buys_24h - sells_24h)

        # Determine whale type
        if buys_1h > sells_1h * 2 and vol_1h > 50_000:
            whale_type = "🟢 WHALE BUY"
            intensity = buys_1h / max(sells_1h, 1)
        elif sells_1h > buys_1h * 2 and vol_1h > 50_000:
            whale_type = "🔴 WHALE SELL"
            intensity = sells_1h / max(buys_1h, 1)
        elif vol_liq_ratio > 2.0:
            whale_type = "🟡 VOLUME SPIKE"
            intensity = vol_liq_ratio
        elif vol_5m > 20_000:
            whale_type = "⚡ RAPID FLOW"
            intensity = vol_5m / 1000
        else:
            whale_type = "📊 HIGH VOLUME"
            intensity = vol_24h / 100_000

        whale_events.append({
            "symbol": pd.get("symbol", "???"),
            "name": pd.get("name", "Unknown"),
            "chain": pd.get("chain", ""),
            "dex": pd.get("dex", ""),
            "price_usd": pd.get("price_usd", "0"),
            "whale_type": whale_type,
            "intensity": round(intensity, 2),
            "volume_5m": vol_5m,
            "volume_1h": vol_1h,
            "volume_24h": vol_24h,
            "liquidity_usd": liq,
            "vol_liq_ratio": round(vol_liq_ratio, 2),
            "buys_1h": buys_1h,
            "sells_1h": sells_1h,
            "buys_24h": buys_24h,
            "sells_24h": sells_24h,
            "price_change_1h": pd.get("price_change_1h", 0),
            "price_change_24h": pd.get("price_change_24h", 0),
            "market_cap": pd.get("market_cap", 0),
            "url": pd.get("url", ""),
        })

        await asyncio.sleep(0.15)

    # Sort by intensity (strongest whale signals first)
    whale_events.sort(key=lambda x: x["intensity"], reverse=True)
    return whale_events[:limit]


# ═══════════════════════════════════════════════════════════════════

async def analyze_opportunity(pairs: list[dict]) -> dict:
    """
    Run the 3-LLM Swarm on DEX Screener data to detect
    trade opportunities. Returns structured verdict.
    """
    from swarm_brain import run_swarm

    # Build a rich data context for the swarm
    summary_lines = []
    for p in pairs[:10]:  # Max 10 pairs to keep token budget sane
        pd = format_pair_data(p) if not isinstance(p, dict) or "symbol" not in p else p
        if isinstance(p, dict) and "baseToken" in p:
            pd = format_pair_data(p)

        summary_lines.append(
            f"• {pd.get('symbol','?')}/{pd.get('quote_symbol','?')} on {pd.get('chain','?')}: "
            f"Price ${pd.get('price_usd','0')}, "
            f"Vol24h ${pd.get('volume_24h',0):,.0f}, "
            f"Liq ${pd.get('liquidity_usd',0):,.0f}, "
            f"Buys1h={pd.get('buys_1h',0)} Sells1h={pd.get('sells_1h',0)} "
            f"(ratio {pd.get('buy_sell_ratio_1h',0):.2f}), "
            f"PriceΔ 1h={pd.get('price_change_1h',0):+.2f}% 24h={pd.get('price_change_24h',0):+.2f}%, "
            f"MCap ${pd.get('market_cap',0):,.0f}"
        )

    data_block = "\n".join(summary_lines)

    prompt = (
        "You are an expert DEX/memecoin analyst. Analyze these tokens from DEX Screener "
        "and identify the BEST trade opportunities. Consider:\n"
        "1. Buy/Sell ratio (>1.5 = strong buying pressure)\n"
        "2. Volume vs Liquidity (high vol/liq ratio = hot token)\n"
        "3. Price momentum (positive across timeframes = trending)\n"
        "4. Liquidity depth (>$50K = safer, <$10K = risky)\n"
        "5. Market cap vs volume ratio\n\n"
        "For each token provide: opportunity_score (1-10), risk_level (low/medium/high/extreme), "
        "and a brief reason.\n\n"
        f"TOKEN DATA:\n{data_block}"
    )

    verdict = await run_swarm(text_data=prompt, user_command="DEX Screener opportunity analysis")
    return verdict


async def get_trending_with_analysis() -> dict:
    """
    Fetch trending/boosted tokens, get their pair data, then run AI analysis.
    Returns {tokens: [...], analysis: {...}}
    """
    # Get boosted tokens
    boosted = await get_top_boosted()
    if not boosted:
        boosted = await get_latest_boosted()

    if not boosted:
        return {"tokens": [], "analysis": None}

    # For each boosted token, fetch pair data
    enriched_pairs = []
    seen = set()
    for token in boosted[:8]:  # Limit to 8 to avoid rate limits
        chain = token.get("chainId", "")
        address = token.get("tokenAddress", "")
        if not chain or not address or f"{chain}:{address}" in seen:
            continue
        seen.add(f"{chain}:{address}")

        pairs = await get_token_data(chain, address)
        if pairs:
            # Pick the highest-volume pair
            best = max(pairs, key=lambda p: p.get("volume", {}).get("h24", 0))
            enriched_pairs.append(best)

        await asyncio.sleep(0.2)  # Gentle rate limiting

    if not enriched_pairs:
        return {"tokens": [], "analysis": None}

    formatted = [format_pair_data(p) for p in enriched_pairs]

    # Run AI analysis
    analysis = await analyze_opportunity(enriched_pairs)

    return {"tokens": formatted, "analysis": analysis}


# ═══════════════════════════════════════════════════════════════════
#  ALERT ENGINE — Scheduled DEX Screener scanning
# ═══════════════════════════════════════════════════════════════════

async def init_dex_db():
    """Initialize the dex_alerts table."""
    db_path = os.getenv("USERS_DB_PATH", "users.db")
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dex_alerts (
                tg_id       INTEGER PRIMARY KEY,
                chain       TEXT DEFAULT 'all',
                min_volume  REAL DEFAULT 50000,
                min_liquidity REAL DEFAULT 10000,
                enabled     INTEGER DEFAULT 1,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("✅ dex_alerts table ready")


async def subscribe_alerts(tg_id: int, chain: str = "all", min_volume: float = 50000, min_liquidity: float = 10000):
    """Subscribe a user to DEX Screener alerts."""
    db_path = os.getenv("USERS_DB_PATH", "users.db")
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            INSERT INTO dex_alerts (tg_id, chain, min_volume, min_liquidity, enabled)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(tg_id) DO UPDATE SET
                chain = excluded.chain,
                min_volume = excluded.min_volume,
                min_liquidity = excluded.min_liquidity,
                enabled = 1
        """, (tg_id, chain, min_volume, min_liquidity))
        await db.commit()
    _alert_subscribers[tg_id] = {"chain": chain, "min_volume": min_volume, "min_liquidity": min_liquidity, "enabled": True}
    logger.info("✅ User %d subscribed to DEX alerts (chain=%s, vol>%.0f)", tg_id, chain, min_volume)


async def unsubscribe_alerts(tg_id: int):
    """Unsubscribe a user from DEX alerts."""
    db_path = os.getenv("USERS_DB_PATH", "users.db")
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE dex_alerts SET enabled = 0 WHERE tg_id = ?", (tg_id,))
        await db.commit()
    _alert_subscribers.pop(tg_id, None)
    logger.info("❌ User %d unsubscribed from DEX alerts", tg_id)


async def get_alert_status(tg_id: int) -> dict | None:
    """Get a user's alert subscription status."""
    db_path = os.getenv("USERS_DB_PATH", "users.db")
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM dex_alerts WHERE tg_id = ?", (tg_id,))
        row = await cursor.fetchone()
        if row:
            return dict(row)
    return None


async def load_all_subscribers():
    """Load all active alert subscribers from DB on startup."""
    db_path = os.getenv("USERS_DB_PATH", "users.db")
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM dex_alerts WHERE enabled = 1")
            rows = await cursor.fetchall()
            for row in rows:
                _alert_subscribers[row["tg_id"]] = {
                    "chain": row["chain"],
                    "min_volume": row["min_volume"],
                    "min_liquidity": row["min_liquidity"],
                    "enabled": True,
                }
        logger.info("📋 Loaded %d DEX alert subscribers", len(_alert_subscribers))
    except Exception as e:
        logger.error("Failed to load DEX subscribers: %s", e)


async def evaluate_dex_alerts():
    """
    Scheduled job — runs every 5 minutes.
    Fetches trending tokens, runs AI analysis, sends alerts to subscribers.
    """
    if not _alert_subscribers:
        return

    if not _tg_notify:
        logger.warning("DEX alert tick skipped — no notify callback")
        return

    logger.info("🔍 DEX Alert scan — %d subscribers", len(_alert_subscribers))

    try:
        result = await get_trending_with_analysis()
        tokens = result.get("tokens", [])
        analysis = result.get("analysis")

        if not tokens:
            return

        # Filter tokens by subscriber preferences and notify
        for tg_id, prefs in list(_alert_subscribers.items()):
            if not prefs.get("enabled"):
                continue

            chain_filter = prefs.get("chain", "all")
            min_vol = prefs.get("min_volume", 50000)
            min_liq = prefs.get("min_liquidity", 10000)

            matching = []
            for t in tokens:
                if chain_filter != "all" and t.get("chain", "") != chain_filter:
                    continue
                if t.get("volume_24h", 0) < min_vol:
                    continue
                if t.get("liquidity_usd", 0) < min_liq:
                    continue
                matching.append(t)

            if not matching:
                continue

            # Build alert message
            msg = "🚨 *DEX Screener Alert — Trade Opportunities*\n\n"

            for t in matching[:5]:  # Max 5 per alert
                bs_ratio = t.get('buy_sell_ratio_1h', 0)
                if bs_ratio >= 999:
                    ratio_str = "∞"
                else:
                    ratio_str = f"{bs_ratio:.2f}"

                if bs_ratio > 1.5:
                    emoji = "🟢"
                elif bs_ratio > 1.0:
                    emoji = "🟡"
                else:
                    emoji = "🔴"

                msg += (
                    f"{emoji} *{t['symbol']}* ({t['chain']})\n"
                    f"  💰 `${float(t.get('price_usd', 0)):.6f}`"
                    f" | Vol: `${t.get('volume_24h', 0):,.0f}`"
                    f" | B/S: `{ratio_str}`\n"
                    f"  Δ1h: `{t.get('price_change_1h', 0):+.2f}%`"
                    f" | Δ24h: `{t.get('price_change_24h', 0):+.2f}%`\n\n"
                )

            # Add AI analysis summary if available
            if analysis:
                sd = analysis.get("structured_data", {})
                summary = sd.get("summary", "")
                if summary:
                    msg += f"🧠 *AI Analysis:*\n_{summary[:500]}_\n\n"

            msg += "_Powered by DEX Screener + X10V 3-LLM Swarm_\n`/dex_alerts off` to unsubscribe"

            try:
                await _tg_notify(tg_id, msg)
                logger.info("📨 DEX alert sent to user %d (%d tokens)", tg_id, len(matching))
            except Exception as e:
                logger.error("Failed to send DEX alert to %d: %s", tg_id, e)

    except Exception as e:
        logger.error("DEX alert evaluation failed: %s", e)
