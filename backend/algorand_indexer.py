"""
algorand_indexer.py — Algorand On-Chain Event Listener & Transaction Builder
================================================================================
Autonomous DeFi Agent components:
  • Poll Algorand Indexer for large transactions (whale alerts)
  • Build unsigned payment/swap transactions for Mini App signing
  • Store pending unsigned transactions in SQLite for Telegram→WebApp handoff

Dependencies: py-algorand-sdk, aiohttp, aiosqlite
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Callable

import aiosqlite
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("algorand_indexer")

DB_PATH = os.getenv("USERS_DB_PATH", "users.db")

# ─── Algorand network config ─────────────────────────────────────
ALGOD_URL = "https://testnet-api.algonode.cloud"
INDEXER_URL = "https://testnet-idx.algonode.cloud"
ALGO_DECIMALS = 6

# ─── Notify callback (set by tg_bot.py) ──────────────────────────
_tg_notify: Optional[Callable] = None
_tg_send_swap_prompt: Optional[Callable] = None


def set_indexer_notify(fn):
    global _tg_notify
    _tg_notify = fn


def set_swap_prompt_callback(fn):
    """Register callback for sending inline keyboard swap prompts."""
    global _tg_send_swap_prompt
    _tg_send_swap_prompt = fn


# ═══════════════════════════════════════════════════════════════════
#  DATABASE — Pending unsigned transactions for Mini App handoff
# ═══════════════════════════════════════════════════════════════════

async def init_indexer_db():
    """Create tables for pending transactions and chain event tracking."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_transactions (
                id          TEXT PRIMARY KEY,
                tg_id       INTEGER NOT NULL,
                tx_type     TEXT NOT NULL DEFAULT 'payment',
                sender      TEXT NOT NULL,
                receiver    TEXT NOT NULL,
                amount_algo REAL NOT NULL,
                note        TEXT DEFAULT '',
                status      TEXT DEFAULT 'pending',
                created_at  TEXT,
                signed_at   TEXT,
                tx_id       TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chain_event_cursors (
                id          TEXT PRIMARY KEY DEFAULT 'main',
                last_round  INTEGER DEFAULT 0,
                updated_at  TEXT
            )
        """)
        await db.commit()
    logger.info("✅ Algorand Indexer DB tables initialized")


# ═══════════════════════════════════════════════════════════════════
#  PENDING TRANSACTION CRUD
# ═══════════════════════════════════════════════════════════════════

async def create_pending_transaction(
    tg_id: int,
    sender: str,
    receiver: str,
    amount_algo: float,
    note: str = "X10V DeFi Agent Swap",
    tx_type: str = "payment",
) -> dict:
    """Store an unsigned transaction for the Mini App to sign."""
    tx_id = f"ptx_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO pending_transactions
               (id, tg_id, tx_type, sender, receiver, amount_algo, note, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (tx_id, tg_id, tx_type, sender, receiver, amount_algo, note, now),
        )
        await db.commit()

    logger.info("📝 Pending TX created: %s — %s ALGO from %s to %s",
                tx_id, amount_algo, sender[:8], receiver[:8])
    return {
        "id": tx_id, "tg_id": tg_id, "tx_type": tx_type,
        "sender": sender, "receiver": receiver,
        "amount_algo": amount_algo, "note": note,
        "status": "pending", "created_at": now,
    }


async def get_pending_transaction(tx_id: str) -> Optional[dict]:
    """Get a pending transaction by ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM pending_transactions WHERE id = ? AND status = 'pending'",
            (tx_id,),
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def get_user_pending_transactions(tg_id: int) -> list:
    """Get all pending transactions for a user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM pending_transactions WHERE tg_id = ? AND status = 'pending' ORDER BY created_at DESC",
            (tg_id,),
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def mark_transaction_signed(tx_id: str, algo_tx_id: str):
    """Mark a pending transaction as signed after Mini App submits it."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE pending_transactions SET status = 'signed', signed_at = ?, tx_id = ? WHERE id = ?",
            (now, algo_tx_id, tx_id),
        )
        await db.commit()
    logger.info("✅ TX %s marked signed — Algorand TX ID: %s", tx_id, algo_tx_id)


# ═══════════════════════════════════════════════════════════════════
#  BUILD UNSIGNED ALGORAND TRANSACTIONS
# ═══════════════════════════════════════════════════════════════════

async def build_unsigned_payment(
    sender: str,
    receiver: str,
    amount_algo: float,
    note: str = "X10V DeFi Agent",
) -> dict:
    """
    Build an unsigned Algorand payment transaction.
    Returns a JSON-serializable dict the Mini App can reconstruct & sign.
    """
    import aiohttp

    # Fetch suggested params from algod
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{ALGOD_URL}/v2/transactions/params") as resp:
            if resp.status != 200:
                raise Exception(f"Failed to get tx params: HTTP {resp.status}")
            params = await resp.json()

    amount_micro = int(amount_algo * 1_000_000)

    # Return a serializable transaction descriptor
    # The Mini App will use algosdk to reconstruct and sign
    unsigned_txn = {
        "type": "pay",
        "from": sender,
        "to": receiver,
        "amount": amount_micro,
        "fee": params.get("min-fee", 1000),
        "firstRound": params.get("last-round", 0),
        "lastRound": params.get("last-round", 0) + 1000,
        "genesisID": params.get("genesis-id", "testnet-v1.0"),
        "genesisHash": params.get("genesis-hash", ""),
        "note": note,
    }

    return unsigned_txn


# ═══════════════════════════════════════════════════════════════════
#  ON-CHAIN EVENT MONITOR (Algorand Indexer polling)
# ═══════════════════════════════════════════════════════════════════

async def _get_last_checked_round() -> int:
    """Get the last Algorand round we checked."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT last_round FROM chain_event_cursors WHERE id = 'main'"
        )
        row = await cursor.fetchone()
    return row["last_round"] if row else 0


async def _set_last_checked_round(round_num: int):
    """Update the last checked round."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO chain_event_cursors (id, last_round, updated_at)
               VALUES ('main', ?, ?)
               ON CONFLICT(id) DO UPDATE SET last_round = ?, updated_at = ?""",
            (round_num, now, round_num, now),
        )
        await db.commit()


async def poll_large_transactions(
    min_algo: float = 10_000.0,
    limit: int = 10,
) -> list:
    """
    Poll Algorand Indexer for recent large transactions.
    Returns list of whale transfer dicts.

    Uses the Indexer REST API directly (no SDK needed for simple queries).
    """
    import aiohttp

    min_micro = int(min_algo * 1_000_000)
    last_round = await _get_last_checked_round()

    # If we've never polled, start from a recent round
    if last_round == 0:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ALGOD_URL}/v2/status") as resp:
                if resp.status == 200:
                    status = await resp.json()
                    last_round = status.get("last-round", 0) - 50  # start 50 rounds back
                else:
                    logger.error("Failed to get algod status: %s", resp.status)
                    return []

    # Query Indexer for transactions above the threshold
    params = {
        "min-round": last_round + 1,
        "currency-greater-than": min_micro,
        "tx-type": "pay",
        "limit": limit,
    }

    whale_txns = []
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{INDEXER_URL}/v2/transactions"
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.warning("Indexer query failed: HTTP %s", resp.status)
                    return []

                data = await resp.json()
                txns = data.get("transactions", [])
                current_round = data.get("current-round", last_round)

                for txn in txns:
                    pay_info = txn.get("payment-transaction", {})
                    amount_algo = pay_info.get("amount", 0) / 1_000_000
                    whale_txns.append({
                        "tx_id": txn.get("id", ""),
                        "sender": txn.get("sender", ""),
                        "receiver": pay_info.get("receiver", ""),
                        "amount_algo": amount_algo,
                        "round": txn.get("confirmed-round", 0),
                        "timestamp": txn.get("round-time", 0),
                        "fee": txn.get("fee", 0) / 1_000_000,
                    })

                # Update cursor
                if current_round > last_round:
                    await _set_last_checked_round(current_round)

                if whale_txns:
                    logger.info("🐋 Found %d whale transactions (>%s ALGO) from round %d",
                                len(whale_txns), min_algo, last_round + 1)

    except Exception as e:
        logger.error("Indexer polling error: %s", e)

    return whale_txns


async def check_on_chain_events(trigger_config: dict) -> tuple[bool, dict]:
    """
    Evaluate an on_chain_event trigger.
    Returns (should_fire, event_data).

    Supported trigger_config:
      {
        "event_type": "whale_transfer",
        "min_algo": 10000,
        "watch_address": ""  // optional: filter by sender/receiver
      }
    """
    event_type = trigger_config.get("event_type", "whale_transfer")
    min_algo = float(trigger_config.get("min_algo", 10_000))
    watch_address = trigger_config.get("watch_address", "")

    if event_type == "whale_transfer":
        txns = await poll_large_transactions(min_algo=min_algo, limit=5)

        if watch_address:
            txns = [
                t for t in txns
                if t["sender"] == watch_address or t["receiver"] == watch_address
            ]

        if txns:
            # Return the largest transaction as the trigger event
            biggest = max(txns, key=lambda t: t["amount_algo"])
            return True, {
                "whale_txn": biggest,
                "all_whale_txns": txns,
                "count": len(txns),
            }

    return False, {}


# ═══════════════════════════════════════════════════════════════════
#  EXECUTE DEX SWAP — Build unsigned TX + trigger Telegram prompt
# ═══════════════════════════════════════════════════════════════════

# Dummy USDC-equivalent ASA on TestNet for demonstration
# In production, this would be the real USDC ASA ID
TESTNET_USDC_RECEIVER = "HZ57J3K46JIJXILONBBZOHX6BKPXEM2VVXNRFSUED6DKFD5ZD24PMJ3MVA"


async def execute_dex_swap_action(
    tg_id: int,
    sender_address: str,
    amount_algo: float,
    reason: str = "DeFi Agent autonomous swap",
    sentiment_data: Optional[dict] = None,
) -> dict:
    """
    Build an unsigned ALGO→USDC swap transaction and trigger the
    Telegram inline keyboard prompt for user approval.

    Flow:
      1. Build unsigned transaction
      2. Store in pending_transactions DB
      3. Send Telegram inline keyboard with "Approve Swap" button
      4. User clicks → opens Mini App → signs with Lute wallet
    """
    if not sender_address:
        return {"success": False, "output": "No wallet address connected. Use /connect_wallet first."}

    try:
        # Build the unsigned transaction
        unsigned_txn = await build_unsigned_payment(
            sender=sender_address,
            receiver=TESTNET_USDC_RECEIVER,
            amount_algo=amount_algo,
            note=f"X10V DeFi Agent: {reason}",
        )

        # Store in DB for Mini App retrieval
        pending = await create_pending_transaction(
            tg_id=tg_id,
            sender=sender_address,
            receiver=TESTNET_USDC_RECEIVER,
            amount_algo=amount_algo,
            note=reason,
            tx_type="dex_swap",
        )

        # Craft the sentiment-aware message
        sentiment_label = "⚠️ Market Signal"
        if sentiment_data:
            score = sentiment_data.get("score", 50)
            sentiment = sentiment_data.get("sentiment", "neutral")
            if sentiment == "bearish":
                sentiment_label = f"🚨 Bearish Alert (Score: {score}/100)"
            elif sentiment == "bullish":
                sentiment_label = f"🟢 Bullish Signal (Score: {score}/100)"
            else:
                sentiment_label = f"⚖️ Neutral Signal (Score: {score}/100)"

        # Send Telegram inline keyboard prompt
        if _tg_send_swap_prompt:
            await _tg_send_swap_prompt(
                tg_id=tg_id,
                pending_tx_id=pending["id"],
                amount_algo=amount_algo,
                reason=reason,
                sentiment_label=sentiment_label,
            )

        return {
            "success": True,
            "output": (
                f"🔔 Swap prompt sent to user!\n"
                f"Amount: {amount_algo} ALGO → USDC\n"
                f"Reason: {reason}\n"
                f"Pending TX ID: {pending['id']}\n"
                f"Status: Awaiting user approval in Mini App"
            ),
            "pending_tx_id": pending["id"],
            "unsigned_txn": unsigned_txn,
        }

    except Exception as e:
        logger.error("execute_dex_swap failed: %s", e)
        return {"success": False, "output": f"Swap setup failed: {str(e)[:200]}"}
