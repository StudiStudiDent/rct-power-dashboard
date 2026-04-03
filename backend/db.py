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
    Returns the most recent reading, or None if the DB is empty.
    Used by GET /api/live.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")
        async with db.execute(
            "SELECT * FROM readings ORDER BY ts DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            if row is None:
                return None
            return dict(row)


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
            ) WHERE rn % ? = 1
            ORDER BY ts
        """, (cutoff, step)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def fetch_summary(db_path: str) -> list[dict]:
    """
    Returns daily summary from the SQL view (last 90 days).
    View is computed live from readings — no separate write process needed.
    """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA busy_timeout=5000")
        async with db.execute("""
            SELECT * FROM daily_summary
            ORDER BY date DESC
            LIMIT 90
        """) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def fetch_latest_ts(db_path: str) -> Optional[int]:
    """Returns only the timestamp of the most recent reading. Used by WebSocket watcher."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA busy_timeout=5000")
        async with db.execute(
            "SELECT ts FROM readings ORDER BY ts DESC LIMIT 1"
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else None
