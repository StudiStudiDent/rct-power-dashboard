"""
db.py — Database access layer for the FastAPI backend.

Architecture rule: FastAPI NEVER calls rctclient. All inverter data
comes from SQLite, written by rct-poller.py.

Data flow:
  rct-poller.py → SQLite (writes)
  FastAPI → SQLite (reads only) → API responses
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional

import aiosqlite


async def get_db(db_path: str):
    """Async context manager for aiosqlite connections."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        yield db


async def fetch_latest(db_path: str) -> Optional[dict]:
    """
    Returns the most recent reading from latest_reading (updated every poll).
    Falls back to readings table if latest_reading is empty (first start).
    Used by GET /api/live and WebSocket push.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")
        async with db.execute(
            "SELECT * FROM latest_reading WHERE id = 1"
        ) as cur:
            row = await cur.fetchone()
            if row is not None:
                return dict(row)
        # Fallback: latest_reading not yet populated
        async with db.execute(
            "SELECT * FROM readings ORDER BY ts DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def fetch_history(db_path: str, hours: int, max_points: int = 500) -> list[dict]:
    """
    Returns up to max_points downsampled readings for the last N hours.

    Downsampling: evenly spaced LIMIT using SQLite row_number trick.
    No external dependencies — pure SQL.

    At 30s intervals:
      - 24h = 2880 raw rows → max 500 returned
      - 7d  = 20160 raw rows → max 500 returned
    """
    hours = max(1, min(hours, 8760))  # clamp: 1h to 1 year
    cutoff = int(time.time()) - (hours * 3600)

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")

        # Count total rows in window
        async with db.execute(
            "SELECT COUNT(*) FROM readings WHERE ts >= ?", (cutoff,)
        ) as cur:
            total = (await cur.fetchone())[0]

        if total == 0:
            return []

        # Calculate step for downsampling
        step = max(1, total // max_points)

        # Select every N-th row using rowid-based trick
        async with db.execute("""
            SELECT * FROM (
                SELECT *, ROW_NUMBER() OVER (ORDER BY ts) AS rn
                FROM readings WHERE ts >= ?
            ) WHERE rn % ? = 0
            ORDER BY ts
        """, (cutoff, step)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def fetch_summary(db_path: str, limit: int = 3650) -> list[dict]:
    """
    Returns daily summary. Default limit 3650 (~10 years) — effectively all data
    for a home solar system. Caller can pass a smaller limit for performance.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")
        async with db.execute("""
            SELECT * FROM daily_summary
            ORDER BY date DESC
            LIMIT ?
        """, (limit,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def fetch_day_readings(db_path: str, date: str) -> list[dict]:
    """
    Returns all readings for a specific date (YYYY-MM-DD) in local time.
    Used by Statistik page single-day view.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")
        async with db.execute("""
            SELECT * FROM readings
            WHERE date(ts, 'unixepoch', 'localtime') = ?
            ORDER BY ts
        """, (date,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def fetch_latest_ts(db_path: str) -> Optional[int]:
    """Returns timestamp of the most recent reading from latest_reading. Used by WebSocket watcher."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        async with db.execute(
            "SELECT ts FROM latest_reading WHERE id = 1"
        ) as cur:
            row = await cur.fetchone()
            if row:
                return row[0]
        # Fallback
        async with db.execute(
            "SELECT ts FROM readings ORDER BY ts DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None
