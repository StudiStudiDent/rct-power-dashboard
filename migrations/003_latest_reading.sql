-- Migration 003: latest_reading table for fast live display
-- The poller writes here on every poll (e.g. 5s).
-- The readings table is only written every Nth poll (e.g. every 6th = 30s).
-- FastAPI reads from latest_reading for WebSocket push and /api/live.
-- This decouples display refresh rate from DB storage rate.

CREATE TABLE IF NOT EXISTS latest_reading (
    id             INTEGER PRIMARY KEY DEFAULT 1,  -- always row 1, UPSERT pattern
    ts             INTEGER,
    battery_soc    REAL,
    pv_string1_w   REAL,
    pv_string2_w   REAL,
    grid_w         REAL,
    load_w         REAL,
    battery_w      REAL,
    inverter_temp  REAL,
    battery_status INTEGER
);
