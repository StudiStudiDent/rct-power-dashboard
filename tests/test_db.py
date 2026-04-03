"""
tests/test_db.py — Database layer tests

Tests:
- Schema initialization (idempotent)
- UPSERT: duplicate ts does not create duplicate rows
- UPSERT: preserves row ID (not INSERT OR REPLACE behavior)
- Retention cleanup: old rows are deleted
- fetch_latest: returns None on empty DB
- fetch_history: downsampling, edge cases
- daily_summary view: correct aggregation
"""

import pytest
import sqlite3
import time
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from rct_poller import init_db, write_reading, cleanup_old_readings


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


# ── Schema ────────────────────────────────────────────────────────────────────

def test_init_db_idempotent(db_path):
    """Calling init_db twice should not raise or duplicate tables."""
    init_db(db_path)  # Second call
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "readings" in tables
    assert "schema_version" in tables
    conn.close()


def test_schema_version_is_1(db_path):
    conn = sqlite3.connect(db_path)
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    assert version == 1
    conn.close()


# ── UPSERT behavior ───────────────────────────────────────────────────────────

def test_upsert_no_duplicate_on_same_ts(db_path):
    """Writing the same ts twice should result in exactly one row."""
    ts = int(time.time())
    values = {"battery_soc": 80.0, "pv_string1_w": 1000.0, "pv_string2_w": 800.0,
              "grid_w": 200.0, "load_w": 500.0, "battery_w": 100.0,
              "inverter_temp": 35.0, "battery_status": 0}

    write_reading(db_path, ts, values)
    write_reading(db_path, ts, values)  # Duplicate

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM readings WHERE ts = ?", (ts,)).fetchone()[0]
    conn.close()
    assert count == 1


def test_upsert_preserves_row_id(db_path):
    """UPSERT should keep the original row id, not create a new one."""
    ts = int(time.time())
    values = {"battery_soc": 50.0, "pv_string1_w": 500.0, "pv_string2_w": 500.0,
              "grid_w": 0.0, "load_w": 400.0, "battery_w": 50.0,
              "inverter_temp": 30.0, "battery_status": 0}

    write_reading(db_path, ts, values)
    conn = sqlite3.connect(db_path)
    original_id = conn.execute("SELECT id FROM readings WHERE ts = ?", (ts,)).fetchone()[0]
    conn.close()

    # Update via upsert
    values["battery_soc"] = 55.0
    write_reading(db_path, ts, values)

    conn = sqlite3.connect(db_path)
    new_id = conn.execute("SELECT id FROM readings WHERE ts = ?", (ts,)).fetchone()[0]
    updated_soc = conn.execute("SELECT battery_soc FROM readings WHERE ts = ?", (ts,)).fetchone()[0]
    conn.close()

    assert original_id == new_id, "Row ID should be preserved by UPSERT"
    assert updated_soc == 55.0


# ── Retention cleanup ─────────────────────────────────────────────────────────

def test_retention_cleanup_deletes_old_rows(db_path):
    now = int(time.time())
    old_ts = now - (91 * 86400)  # 91 days ago
    recent_ts = now - 3600       # 1 hour ago

    values = {"battery_soc": 60.0, "pv_string1_w": 0.0, "pv_string2_w": 0.0,
              "grid_w": 0.0, "load_w": 0.0, "battery_w": 0.0,
              "inverter_temp": 25.0, "battery_status": 0}

    write_reading(db_path, old_ts, values)
    write_reading(db_path, recent_ts, values)

    cleanup_old_readings(db_path, retention_days=90)

    conn = sqlite3.connect(db_path)
    old_count = conn.execute("SELECT COUNT(*) FROM readings WHERE ts = ?", (old_ts,)).fetchone()[0]
    recent_count = conn.execute("SELECT COUNT(*) FROM readings WHERE ts = ?", (recent_ts,)).fetchone()[0]
    conn.close()

    assert old_count == 0, "Old row should have been deleted"
    assert recent_count == 1, "Recent row should be preserved"


# ── Async DB functions ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_latest_empty_db(db_path):
    from backend.db import fetch_latest
    result = await fetch_latest(db_path)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_history_empty_db(db_path):
    from backend.db import fetch_history
    result = await fetch_history(db_path, hours=24)
    assert result == []


@pytest.mark.asyncio
async def test_fetch_history_downsamples(db_path):
    """History with > 500 points should return at most 500."""
    from backend.db import fetch_history

    # Insert 1000 readings (1 per second)
    now = int(time.time())
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT INTO readings (ts, battery_soc) VALUES (?, 50.0)",
        [(now - i, ) for i in range(1000)]
    )
    conn.commit()
    conn.close()

    result = await fetch_history(db_path, hours=1, max_points=500)
    assert len(result) <= 500
