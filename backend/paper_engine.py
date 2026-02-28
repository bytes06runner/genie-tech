"""
paper_engine.py — Paper Trading Engine (SQLite)
=================================================
Lightweight demo trading engine with $1,000 virtual starting balance.
Thread-safe async wrapper around synchronous SQLite operations.

Tables:
  users       — Telegram users, wallets, balances
  positions   — Open/closed trade positions
"""

import asyncio
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

logger = logging.getLogger("paper_engine")

DB_PATH = "users.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create tables if they don't already exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            tg_id          INTEGER PRIMARY KEY,
            username       TEXT,
            balance        REAL    NOT NULL DEFAULT 1000.0,
            algo_address   TEXT,
            algo_mnemonic  TEXT,
            created_at     TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS positions (
            id             TEXT    PRIMARY KEY,
            tg_id          INTEGER NOT NULL REFERENCES users(tg_id),
            asset          TEXT    NOT NULL,
            side           TEXT    NOT NULL DEFAULT 'long',
            amount_usd     REAL    NOT NULL,
            entry_price    REAL    NOT NULL,
            exit_price     REAL,
            pnl            REAL,
            status         TEXT    NOT NULL DEFAULT 'open',
            opened_at      TEXT    NOT NULL,
            closed_at      TEXT
        );
    """)
    conn.commit()
    conn.close()
    logger.info("📦 Paper trading DB initialised at %s", DB_PATH)


async def create_user(tg_id: int, username: str = "") -> dict:
    """Register a new user with $1,000 demo balance. Idempotent."""
    def _op():
        conn = _get_conn()
        existing = conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        if existing:
            return dict(existing), False
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users (tg_id, username, balance, created_at) VALUES (?, ?, 1000.0, ?)",
            (tg_id, username, now),
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        conn.close()
        return dict(user), True

    user, is_new = await asyncio.get_event_loop().run_in_executor(None, _op)
    return {**user, "is_new": is_new}


async def get_balance(tg_id: int) -> Optional[float]:
    """Return the user's current virtual balance, or None if not registered."""
    def _op():
        conn = _get_conn()
        row = conn.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        conn.close()
        return row["balance"] if row else None
    return await asyncio.get_event_loop().run_in_executor(None, _op)


async def get_user(tg_id: int) -> Optional[dict]:
    def _op():
        conn = _get_conn()
        row = conn.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        conn.close()
        return dict(row) if row else None
    return await asyncio.get_event_loop().run_in_executor(None, _op)


async def link_wallet(tg_id: int, address: str, mnemonic: str) -> bool:
    """Link an Algorand testnet wallet to the user profile."""
    def _op():
        conn = _get_conn()
        conn.execute(
            "UPDATE users SET algo_address = ?, algo_mnemonic = ? WHERE tg_id = ?",
            (address, mnemonic, tg_id),
        )
        conn.commit()
        conn.close()
    await asyncio.get_event_loop().run_in_executor(None, _op)
    logger.info("🔗 Wallet linked for user %d: %s", tg_id, address[:12] + "…")
    return True


async def open_position(tg_id: int, asset: str, amount_usd: float, current_price: float) -> dict:
    """
    Open a new paper trade. Validates sufficient balance.
    Returns the position dict or raises ValueError.
    """
    def _op():
        conn = _get_conn()
        row = conn.execute("SELECT balance FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
        if not row:
            raise ValueError("User not registered. Use /start first.")
        balance = row["balance"]
        if amount_usd <= 0:
            raise ValueError("Amount must be positive.")
        if amount_usd > balance:
            raise ValueError(f"Insufficient balance. Available: ${balance:.2f}, Requested: ${amount_usd:.2f}")
        if amount_usd > 500:
            raise ValueError("Max allocation per trade is $500 (risk management).")

        new_balance = round(balance - amount_usd, 2)
        conn.execute("UPDATE users SET balance = ? WHERE tg_id = ?", (new_balance, tg_id))

        pos_id = uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO positions (id, tg_id, asset, amount_usd, entry_price, status, opened_at) "
            "VALUES (?, ?, ?, ?, ?, 'open', ?)",
            (pos_id, tg_id, asset.upper(), amount_usd, current_price, now),
        )
        conn.commit()
        pos = conn.execute("SELECT * FROM positions WHERE id = ?", (pos_id,)).fetchone()
        conn.close()
        return dict(pos)

    return await asyncio.get_event_loop().run_in_executor(None, _op)


async def close_position(tg_id: int, position_id: str, current_price: float) -> dict:
    """
    Close an open position at the current price. Calculates PnL
    and credits the balance.
    """
    def _op():
        conn = _get_conn()
        pos = conn.execute(
            "SELECT * FROM positions WHERE id = ? AND tg_id = ? AND status = 'open'",
            (position_id, tg_id),
        ).fetchone()
        if not pos:
            raise ValueError(f"No open position found with ID {position_id}")

        entry_price = pos["entry_price"]
        amount_usd = pos["amount_usd"]
        units = amount_usd / entry_price
        exit_value = units * current_price
        pnl = round(exit_value - amount_usd, 2)
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            "UPDATE positions SET exit_price = ?, pnl = ?, status = 'closed', closed_at = ? WHERE id = ?",
            (current_price, pnl, now, position_id),
        )
        conn.execute(
            "UPDATE users SET balance = balance + ? WHERE tg_id = ?",
            (round(amount_usd + pnl, 2), tg_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
        conn.close()
        return dict(updated)

    return await asyncio.get_event_loop().run_in_executor(None, _op)


async def get_open_positions(tg_id: int) -> list[dict]:
    """Return all open positions for a user."""
    def _op():
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM positions WHERE tg_id = ? AND status = 'open' ORDER BY opened_at DESC",
            (tg_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    return await asyncio.get_event_loop().run_in_executor(None, _op)


async def get_all_positions(tg_id: int) -> list[dict]:
    """Return all positions (open + closed) for a user."""
    def _op():
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM positions WHERE tg_id = ? ORDER BY opened_at DESC",
            (tg_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    return await asyncio.get_event_loop().run_in_executor(None, _op)


async def update_balance_direct(tg_id: int, new_balance: float):
    """Admin/internal: directly set a user's balance."""
    def _op():
        conn = _get_conn()
        conn.execute("UPDATE users SET balance = ? WHERE tg_id = ?", (round(new_balance, 2), tg_id))
        conn.commit()
        conn.close()
    await asyncio.get_event_loop().run_in_executor(None, _op)


init_db()
