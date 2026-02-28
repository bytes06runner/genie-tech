"""
market_monitor.py — Asynchronous Market Monitor (APScheduler)
================================================================
Background price-monitoring engine. When the Gemini Swarm issues a
"monitor_and_execute" decision, this module:

  1. Creates an APScheduler interval job that checks the asset price every 5 min
  2. Uses yfinance (free, no API key) or deep_scraper as fallback
  3. When the target price is hit → auto-executes the paper trade
  4. Sends a Telegram push notification to the user

Integrates with the existing scheduler_node.py APScheduler instance.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Callable, Coroutine, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore

from paper_engine import open_position, get_balance
from deep_scraper import deep_scrape

logger = logging.getLogger("market_monitor")

monitor_scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    job_defaults={"coalesce": True, "max_instances": 5},
)

active_monitors: dict[str, dict] = {}

_tg_notify_fn: Optional[Callable] = None


def set_tg_notify(fn):
    """Register the Telegram notification callback from tg_bot."""
    global _tg_notify_fn
    _tg_notify_fn = fn


async def fetch_price_yfinance(ticker: str) -> Optional[float]:
    """Fetch the current price using yfinance (runs in executor for async safety)."""
    def _fetch():
        try:
            import yfinance as yf
            symbol = _normalize_ticker(ticker)
            data = yf.Ticker(symbol)
            hist = data.history(period="1d")
            if hist.empty:
                return None
            return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning("yfinance fetch failed for %s: %s", ticker, e)
            return None
    return await asyncio.get_event_loop().run_in_executor(None, _fetch)


async def fetch_price_scraper(ticker: str) -> Optional[float]:
    """Fallback: use deep_scraper to find the price via DuckDuckGo + Playwright."""
    try:
        result = await deep_scrape(f"{ticker} current price today", timeout_seconds=5)
        if not result.get("success"):
            return None
        text = result.get("text", "")
        import re
        prices = re.findall(r'\$?([\d,]+\.?\d*)', text)
        if prices:
            price_str = prices[0].replace(",", "")
            return float(price_str)
        return None
    except Exception as e:
        logger.warning("Scraper price fetch failed for %s: %s", ticker, e)
        return None


async def fetch_current_price(ticker: str) -> Optional[float]:
    """Try yfinance first, fallback to deep_scraper."""
    price = await fetch_price_yfinance(ticker)
    if price is not None:
        return price
    logger.info("yfinance miss for %s, trying deep_scraper fallback …", ticker)
    return await fetch_price_scraper(ticker)


def _normalize_ticker(raw: str) -> str:
    """Normalise common ticker formats for yfinance compatibility."""
    mapping = {
        "XAUUSD": "GC=F",
        "XAU/USD": "GC=F",
        "GOLD": "GC=F",
        "EURUSD": "EURUSD=X",
        "EUR/USD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "GBP/USD": "GBPUSD=X",
        "BTC": "BTC-USD",
        "BTCUSD": "BTC-USD",
        "BTC/USD": "BTC-USD",
        "ETH": "ETH-USD",
        "ETHUSD": "ETH-USD",
        "ETH/USD": "ETH-USD",
    }
    upper = raw.upper().strip()
    if upper in mapping:
        return mapping[upper]
    if upper.startswith("NSE:"):
        return upper.replace("NSE:", "") + ".NS"
    if upper.startswith("BSE:"):
        return upper.replace("BSE:", "") + ".BO"
    return upper


async def _monitor_asset(
    job_id: str,
    asset: str,
    target_price: float,
    allocation_usd: float,
    tg_user_id: int,
    direction: str = "below",
):
    """
    Interval callback: check if the asset price has hit the target.
    direction='below' → buy when price drops to/below target
    direction='above' → buy when price rises to/above target
    """
    logger.info("📊 Monitor tick for %s (target: $%.2f, dir: %s, user: %d)", asset, target_price, direction, tg_user_id)

    current_price = await fetch_current_price(asset)
    if current_price is None:
        logger.warning("Could not fetch price for %s — will retry next interval", asset)
        return

    logger.info("📊 %s current: $%.2f, target: $%.2f", asset, current_price, target_price)

    triggered = False
    if direction == "below" and current_price <= target_price:
        triggered = True
    elif direction == "above" and current_price >= target_price:
        triggered = True

    if not triggered:
        return

    logger.info("🚨 TARGET HIT for %s @ $%.2f — auto-executing trade for user %d", asset, current_price, tg_user_id)

    try:
        balance = await get_balance(tg_user_id)
        if balance is None or balance < allocation_usd:
            msg = f"🚨 {asset} hit target ${target_price:.2f} but insufficient balance (${balance or 0:.2f}). Trade skipped."
            logger.warning(msg)
            if _tg_notify_fn:
                await _tg_notify_fn(tg_user_id, msg)
            _remove_monitor(job_id)
            return

        position = await open_position(tg_user_id, asset, allocation_usd, current_price)
        msg = (
            f"🚨 *X10V Auto-Execution*\n\n"
            f"Asset: `{asset}`\n"
            f"Target: ${target_price:.2f} → Filled @ ${current_price:.2f}\n"
            f"Allocated: ${allocation_usd:.2f}\n"
            f"Position ID: `{position['id']}`\n\n"
            f"_Trade auto-executed by your AI swarm._"
        )
        logger.info(msg.replace("*", "").replace("`", "").replace("_", ""))
        if _tg_notify_fn:
            await _tg_notify_fn(tg_user_id, msg)

    except ValueError as e:
        logger.error("Auto-trade failed: %s", e)
        if _tg_notify_fn:
            await _tg_notify_fn(tg_user_id, f"⚠️ Auto-trade failed for {asset}: {e}")
    finally:
        _remove_monitor(job_id)


def _remove_monitor(job_id: str):
    """Remove a completed/failed monitor from the scheduler."""
    try:
        monitor_scheduler.remove_job(job_id)
    except Exception:
        pass
    active_monitors.pop(job_id, None)
    logger.info("🗑️ Monitor %s removed", job_id)


def create_monitor(
    asset: str,
    target_price: float,
    allocation_usd: float,
    tg_user_id: int,
    direction: str = "below",
    interval_minutes: int = 5,
) -> str:
    """
    Create a background APScheduler job to monitor an asset price.
    Returns the job_id.
    """
    from uuid import uuid4
    job_id = f"mon_{uuid4().hex[:8]}"

    monitor_scheduler.add_job(
        _monitor_asset,
        trigger="interval",
        minutes=interval_minutes,
        id=job_id,
        kwargs={
            "job_id": job_id,
            "asset": asset,
            "target_price": target_price,
            "allocation_usd": allocation_usd,
            "tg_user_id": tg_user_id,
            "direction": direction,
        },
        replace_existing=True,
    )

    active_monitors[job_id] = {
        "asset": asset,
        "target_price": target_price,
        "allocation_usd": allocation_usd,
        "tg_user_id": tg_user_id,
        "direction": direction,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "📡 Monitor created: %s watching %s target=$%.2f alloc=$%.2f every %dm",
        job_id, asset, target_price, allocation_usd, interval_minutes,
    )
    return job_id


def get_user_monitors(tg_user_id: int) -> list[dict]:
    """Return all active monitors for a user."""
    return [
        {"job_id": k, **v}
        for k, v in active_monitors.items()
        if v["tg_user_id"] == tg_user_id
    ]


def cancel_monitor(job_id: str) -> bool:
    """Cancel an active monitor by job_id."""
    if job_id not in active_monitors:
        return False
    _remove_monitor(job_id)
    return True


def start_monitor_scheduler():
    if not monitor_scheduler.running:
        monitor_scheduler.start()
        logger.info("🚀 Market Monitor scheduler started.")
