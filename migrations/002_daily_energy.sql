-- Migration 002: Daily energy table for historical data from inverter logger
-- Stores day-resolution energy values fetched via logger.day_*_log_ts timeseries objects.
-- These are authoritative kWh values from the inverter, more accurate than
-- the readings-derived estimates (which require continuous 30s polling).

CREATE TABLE IF NOT EXISTS daily_energy (
    date           TEXT NOT NULL PRIMARY KEY,  -- 'YYYY-MM-DD' local time
    yield_kwh      REAL,   -- AC production (energy.e_ac_day)
    grid_feed_kwh  REAL,   -- Feed-in to grid (energy.e_grid_feed_day)
    grid_draw_kwh  REAL,   -- Draw from grid (energy.e_grid_load_day)
    load_kwh       REAL,   -- Household consumption (energy.e_load_day)
    pv_a_kwh       REAL,   -- PV string A (energy.e_dc_day[0])
    pv_b_kwh       REAL    -- PV string B (energy.e_dc_day[1])
);

-- Replace the view so it prefers daily_energy rows but falls back to
-- readings-derived estimates for days not yet in daily_energy.
DROP VIEW IF EXISTS daily_summary;

CREATE VIEW daily_summary AS
    -- Days with authoritative data from inverter logger
    SELECT
        date,
        yield_kwh,
        grid_feed_kwh,
        grid_draw_kwh,
        load_kwh,
        NULL AS battery_min_pct,
        NULL AS battery_max_pct
    FROM daily_energy

    UNION ALL

    -- Days derived from 30s readings that have no entry in daily_energy
    SELECT
        date(ts, 'unixepoch', 'localtime')                                                        AS date,
        ROUND(SUM(CASE WHEN pv_string1_w IS NOT NULL
                       THEN (pv_string1_w + COALESCE(pv_string2_w, 0)) * (30.0/3600)
                       ELSE 0 END) / 1000, 3)                                                     AS yield_kwh,
        ROUND(SUM(CASE WHEN grid_w < 0  THEN ABS(grid_w) * (30.0/3600) ELSE 0 END) / 1000, 3)   AS grid_feed_kwh,
        ROUND(SUM(CASE WHEN grid_w > 0  THEN grid_w      * (30.0/3600) ELSE 0 END) / 1000, 3)   AS grid_draw_kwh,
        ROUND(SUM(CASE WHEN load_w IS NOT NULL THEN load_w * (30.0/3600) ELSE 0 END) / 1000, 3)  AS load_kwh,
        MIN(battery_soc)                                                                           AS battery_min_pct,
        MAX(battery_soc)                                                                           AS battery_max_pct
    FROM readings
    WHERE date(ts, 'unixepoch', 'localtime') NOT IN (SELECT date FROM daily_energy)
    GROUP BY date(ts, 'unixepoch', 'localtime');
