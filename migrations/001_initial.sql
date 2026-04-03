-- Migration 001: Initial schema
-- Applied automatically by rct-poller.py on first run

PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS readings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             INTEGER NOT NULL UNIQUE,
    battery_soc    REAL,
    pv_string1_w   REAL,
    pv_string2_w   REAL,
    grid_w         REAL,
    load_w         REAL,
    battery_w      REAL,
    inverter_temp  REAL,
    battery_status INTEGER
);

CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings(ts);

-- daily_summary is a VIEW (no write process needed)
CREATE VIEW IF NOT EXISTS daily_summary AS
    SELECT
        date(ts, 'unixepoch', 'localtime')                                         AS date,
        MIN(battery_soc)                                                            AS battery_min_pct,
        MAX(battery_soc)                                                            AS battery_max_pct,
        ROUND(SUM(CASE WHEN pv_string1_w IS NOT NULL THEN (pv_string1_w + COALESCE(pv_string2_w, 0)) * (30.0/3600) ELSE 0 END) / 1000, 3)  AS yield_kwh,
        ROUND(SUM(CASE WHEN grid_w > 0  THEN grid_w  * (30.0/3600) ELSE 0 END) / 1000, 3)  AS grid_feed_kwh,
        ROUND(SUM(CASE WHEN grid_w < 0  THEN ABS(grid_w) * (30.0/3600) ELSE 0 END) / 1000, 3) AS grid_draw_kwh,
        ROUND(SUM(CASE WHEN load_w IS NOT NULL THEN load_w * (30.0/3600) ELSE 0 END) / 1000, 3) AS load_kwh
    FROM readings
    GROUP BY date(ts, 'unixepoch', 'localtime');

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES (1);
