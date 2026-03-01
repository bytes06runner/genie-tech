"""
algorand_indexer.py — Algorand On-Chain Event Listener & Transaction Builder
================================================================================
Autonomous DeFi Agent components:
  • Poll Algorand Indexer for large transactions (whale alerts)
  • Build unsigned payment transactions for Mini App signing
  • Store pending unsigned transactions in SQLite for Telegram→WebApp handoff

Uses the official py-algorand-sdk (IndexerClient + AlgodClient).
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, Callable

import aiosqlite
from algosdk.v2client import algod, indexer
from algosdk import transaction, encoding
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("algorand_indexer")

DB_PATH = os.getenv("USERS_DB_PATH", "users.db")

# ─── Algorand network config (TestNet via Algonode) ──────────────
ALGOD_URL = "https://testnet-api.algonode.cloud"
INDEXER_URL = "https://testnet-idx.algonode.cloud"
ALGO_DECIMALS = 6

# ─── py-algorand-sdk clients ─────────────────────────────────────
algod_client = algod.AlgodClient("", ALGOD_URL)
indexer_client = indexer.IndexerClient("", INDEXER_URL)

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
#  ON-CHAIN BALANCE LOOKUP
# ═══════════════════════════════════════════════════════════════════

async def get_algo_balance(address: str) -> Optional[dict]:
    """
    Fetch real on-chain ALGO balance for an address via algod.
    Returns dict with balance info or None on error.
    """
    if not address:
        return None
    loop = asyncio.get_event_loop()

    def _fetch():
        try:
            info = algod_client.account_info(address)
            amount_micro = info.get("amount", 0)
            min_balance_micro = info.get("min-balance", 100_000)
            return {
                "address": address,
                "balance_micro": amount_micro,
                "balance_algo": amount_micro / 1_000_000,
                "min_balance_algo": min_balance_micro / 1_000_000,
                "available_algo": max(0, (amount_micro - min_balance_micro)) / 1_000_000,
                "total_assets": info.get("total-assets-opted-in", 0),
                "total_apps": info.get("total-apps-opted-in", 0),
                "status": info.get("status", "Offline"),
            }
        except Exception as e:
            logger.error("Failed to fetch balance for %s: %s", address[:12], e)
            return None

    return await loop.run_in_executor(None, _fetch)


async def get_account_transactions(address: str, limit: int = 5) -> list:
    """
    Fetch recent transactions for an address from the Indexer.
    Returns list of simplified transaction dicts.
    """
    if not address:
        return []
    loop = asyncio.get_event_loop()

    def _fetch():
        try:
            data = indexer_client.search_transactions_by_address(
                address, limit=limit, txn_type="pay"
            )
            txns = data.get("transactions", [])
            result = []
            for txn in txns:
                pay = txn.get("payment-transaction", {})
                result.append({
                    "tx_id": txn.get("id", "")[:12] + "…",
                    "sender": txn.get("sender", ""),
                    "receiver": pay.get("receiver", ""),
                    "amount_algo": pay.get("amount", 0) / 1_000_000,
                    "round": txn.get("confirmed-round", 0),
                    "type": "sent" if txn.get("sender") == address else "received",
                })
            return result
        except Exception as e:
            logger.error("Failed to fetch txns for %s: %s", address[:12], e)
            return []

    return await loop.run_in_executor(None, _fetch)


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
    Build an unsigned Algorand PaymentTxn using py-algorand-sdk.
    Returns a JSON-serializable dict the Mini App can reconstruct & sign.
    """
    loop = asyncio.get_event_loop()

    def _build():
        sp = algod_client.suggested_params()
        amount_micro = int(amount_algo * 1_000_000)
        txn = transaction.PaymentTxn(
            sender=sender,
            sp=sp,
            receiver=receiver,
            amt=amount_micro,
            note=note.encode("utf-8"),
        )
        return {
            "type": "pay",
            "from": sender,
            "to": receiver,
            "amount": amount_micro,
            "fee": txn.fee,
            "firstRound": txn.first_valid_round,
            "lastRound": txn.last_valid_round,
            "genesisID": txn.genesis_id,
            "genesisHash": txn.genesis_hash,
            "note": note,
        }

    return await loop.run_in_executor(None, _build)


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
    Poll Algorand Indexer for recent large payment transactions using
    the official py-algorand-sdk IndexerClient.search_transactions().

    10,000 ALGO = 10_000_000_000 microAlgos.
    """
    min_micro = int(min_algo * 1_000_000)
    last_round = await _get_last_checked_round()

    # If we've never polled, start from a recent round
    if last_round == 0:
        loop = asyncio.get_event_loop()
        try:
            status = await loop.run_in_executor(None, algod_client.status)
            last_round = status.get("last-round", 0) - 50
        except Exception as e:
            logger.error("Failed to get algod status: %s", e)
            return []

    whale_txns = []
    try:
        loop = asyncio.get_event_loop()

        def _search():
            return indexer_client.search_transactions(
                min_round=last_round + 1,
                min_amount=min_micro,
                txn_type="pay",
                limit=limit,
            )

        data = await loop.run_in_executor(None, _search)
        txns = data.get("transactions", [])
        current_round = data.get("current-round", last_round)

        for txn in txns:
            pay_info = txn.get("payment-transaction", {})
            amount_algo_val = pay_info.get("amount", 0) / 1_000_000
            whale_txns.append({
                "tx_id": txn.get("id", ""),
                "sender": txn.get("sender", ""),
                "receiver": pay_info.get("receiver", ""),
                "amount_algo": amount_algo_val,
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
#  EXECUTE ON-CHAIN ACTION — Build unsigned TX + trigger Telegram prompt
# ═══════════════════════════════════════════════════════════════════

# Safe vault/escrow address for protective transfers (TestNet)
SAFE_VAULT_ADDRESS = "HZ57J3K46JIJXILONBBZOHX6BKPXEM2VVXNRFSUED6DKFD5ZD24PMJ3MVA"

# Hardcoded sender (user's Lute wallet on TestNet)
DEFAULT_SENDER = "NEIQN3C2UPPWEX7PT67JQGZACSGDDFQR4AZCY6WFVEWQ43YJW3JQT6RIWU"


async def execute_onchain_action(
    tg_id: int,
    sender_address: str,
    amount_algo: float,
    reason: str = "DeFi Agent protective transfer",
    sentiment_data: Optional[dict] = None,
) -> dict:
    """
    Build an unsigned protective ALGO transfer and trigger the
    Telegram inline keyboard prompt for user approval.

    Flow:
      1. Build unsigned PaymentTxn on backend (using py-algorand-sdk)
      2. Store in pending_transactions DB
      3. Send Telegram inline keyboard with "Approve & Sign" button
      4. User clicks → opens Mini App → signs with Lute wallet
      5. Mini App submits to TestNet and notifies backend

    The bot NEVER signs the transaction — only the user's Lute wallet can.
    """
    # Use the connected wallet or fall back to the hardcoded TestNet address
    if not sender_address:
        sender_address = DEFAULT_SENDER
        logger.info("Using default sender address: %s", sender_address[:12])

    try:
        # Build the unsigned transaction via py-algorand-sdk
        unsigned_txn = await build_unsigned_payment(
            sender=sender_address,
            receiver=SAFE_VAULT_ADDRESS,
            amount_algo=amount_algo,
            note=f"X10V DeFi Agent: {reason}",
        )

        # Store in DB for Mini App retrieval
        pending = await create_pending_transaction(
            tg_id=tg_id,
            sender=sender_address,
            receiver=SAFE_VAULT_ADDRESS,
            amount_algo=amount_algo,
            note=reason,
            tx_type="protective_transfer",
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
                f"🔔 Protective transfer prompt sent!\n"
                f"Amount: {amount_algo} ALGO → Safe Vault\n"
                f"Reason: {reason}\n"
                f"Pending TX ID: {pending['id']}\n"
                f"Status: Awaiting user approval in Mini App"
            ),
            "pending_tx_id": pending["id"],
            "unsigned_txn": unsigned_txn,
        }

    except Exception as e:
        logger.error("execute_onchain_action failed: %s", e)
        return {"success": False, "output": f"On-chain action failed: {str(e)[:200]}"}
