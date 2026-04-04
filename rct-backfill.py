#!/usr/bin/env python3
"""
rct-backfill.py — One-shot historical data import from RCT Power inverter.

Queries the inverter's internal day-resolution logger timeseries and writes
the results into the daily_energy table. Run once to populate history;
safe to re-run (UPSERT on date).

Usage:
    python rct-backfill.py [--config config.yaml.local]

The inverter stores several months of daily energy values in its logger.
This script fetches:
  - AC yield per day        (logger.day_eac_log_ts)
  - Grid feed-in per day    (logger.day_egrid_feed_log_ts)
  - Grid draw per day       (logger.day_egrid_load_log_ts)
  - Household load per day  (logger.day_eload_log_ts)
  - PV string A per day     (logger.day_ea_log_ts)
  - PV string B per day     (logger.day_eb_log_ts)
"""

import argparse
import logging
import select
import socket
import sqlite3
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from rctclient.frame import ReceiveFrame, make_frame
from rctclient.registry import REGISTRY as R
from rctclient.types import DataType, Command
from rctclient.utils import decode_value

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# Logger timeseries object IDs for day-resolution data.
# Each returns a TIMESERIES: {datetime → float (Wh)} for past days.
DAY_LOGGER_IDS = {
    "yield_kwh":     0xE04C3900,  # logger.day_eac_log_ts      — AC production Wh/day
    "grid_feed_kwh": 0xB20D1AD6,  # logger.day_egrid_feed_log_ts — Feed-in Wh/day
    "grid_draw_kwh": 0x5C7CFB1,   # logger.day_egrid_load_log_ts — Draw Wh/day
    "load_kwh":      0xCA6D6472,  # logger.day_eload_log_ts      — Load Wh/day
    "pv_a_kwh":      0xFCF4E78D,  # logger.day_ea_log_ts         — PV string A Wh/day
    "pv_b_kwh":      0xDF164DE,   # logger.day_eb_log_ts         — PV string B Wh/day
}


def load_config(path: str | None = None) -> dict:
    if path is None:
        path = "config.yaml.local" if Path("config.yaml.local").exists() else "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def run_migrations(db_path: str) -> None:
    """Apply pending migrations."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    migrations_dir = Path(__file__).parent / "migrations"
    conn = sqlite3.connect(db_path)
    try:
        current_version = conn.execute("PRAGMA user_version").fetchone()[0]
        for f in sorted(migrations_dir.glob("*.sql")):
            try:
                file_version = int(f.stem.split("_")[0])
            except ValueError:
                continue
            if file_version <= current_version:
                continue
            log.info("Applying migration %s", f.name)
            conn.executescript(f.read_text())
            conn.execute(f"PRAGMA user_version = {file_version}")
            conn.commit()
            current_version = file_version
    finally:
        conn.close()


def sock_readable(sock: socket.socket, timeout: float) -> bool:
    r, _, _ = select.select([sock], [], [], timeout)
    return bool(r)


def fetch_timeseries(sock: socket.socket, object_id: int) -> dict[datetime, float] | None:
    """
    Query a TIMESERIES logger object.

    Protocol: send WRITE with current timestamp as INT32 payload.
    Inverter responds with TIMESERIES data: pairs of (timestamp, float Wh).

    Returns {datetime: wh_value} or None on failure.
    The response may come in multiple TCP segments — we keep reading until
    the frame is complete or timeout.
    """
    try:
        # Encode current timestamp as INT32 payload (tells inverter "give me data up to now")
        now_ts = int(time.time())
        payload = struct.pack('>i', now_ts)
        frame = make_frame(command=Command.WRITE, id=object_id, payload=payload)
        sock.sendall(frame)

        recv = ReceiveFrame()
        deadline = time.monotonic() + 10.0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                log.warning("Timeout waiting for timeseries 0x%08X", object_id)
                return None
            if not sock_readable(sock, min(remaining, 2.0)):
                continue
            chunk = sock.recv(4096)
            if not chunk:
                log.warning("Connection closed reading 0x%08X", object_id)
                return None
            for byte in chunk:
                recv.consume(bytes([byte]))
                if recv.complete():
                    break
            if recv.complete():
                break

        if recv.id != object_id:
            log.warning("ID mismatch for 0x%08X: got 0x%08X", object_id, recv.id)
            return None

        obj = R.get_by_id(object_id)
        _ts_header, data_dict = decode_value(DataType.TIMESERIES, recv.data)
        return data_dict

    except Exception as e:
        log.error("Error fetching timeseries 0x%08X: %s", object_id, e)
        return None


def fetch_all_timeseries(host: str, port: int) -> dict[str, dict[datetime, float]]:
    """
    Open one connection and fetch all day-logger timeseries objects.
    Returns {field_name: {datetime: wh_value}}.
    """
    results = {}
    try:
        with socket.create_connection((host, port), timeout=15) as sock:
            sock.settimeout(15)
            for field, obj_id in DAY_LOGGER_IDS.items():
                log.info("Fetching %s (0x%08X)...", field, obj_id)
                data = fetch_timeseries(sock, obj_id)
                if data:
                    log.info("  → %d days of data", len(data))
                    results[field] = data
                else:
                    log.warning("  → no data for %s", field)
                time.sleep(0.3)  # small pause between requests
    except (ConnectionRefusedError, TimeoutError, OSError) as e:
        log.error("Cannot connect to inverter %s:%d — %s", host, port, e)
    return results


def merge_to_daily(all_series: dict[str, dict[datetime, float]]) -> dict[str, dict]:
    """
    Pivot {field: {datetime: wh}} → {date_str: {field: kwh}}.
    Wh → kWh conversion applied here.
    """
    by_date: dict[str, dict] = {}
    for field, series in all_series.items():
        for dt, wh in series.items():
            date_str = dt.strftime("%Y-%m-%d")
            if date_str not in by_date:
                by_date[date_str] = {}
            # grid_feed_kwh is returned as negative by the inverter (feed-in convention)
            by_date[date_str][field] = round(abs(wh) / 1000, 3)
    return by_date


def write_daily_energy(db_path: str, by_date: dict[str, dict]) -> int:
    """
    UPSERT daily_energy rows. Returns count of rows written.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    written = 0
    try:
        for date_str, vals in sorted(by_date.items()):
            conn.execute("""
                INSERT INTO daily_energy (
                    date, yield_kwh, grid_feed_kwh, grid_draw_kwh,
                    load_kwh, pv_a_kwh, pv_b_kwh
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    yield_kwh     = COALESCE(excluded.yield_kwh,     yield_kwh),
                    grid_feed_kwh = COALESCE(excluded.grid_feed_kwh, grid_feed_kwh),
                    grid_draw_kwh = COALESCE(excluded.grid_draw_kwh, grid_draw_kwh),
                    load_kwh      = COALESCE(excluded.load_kwh,      load_kwh),
                    pv_a_kwh      = COALESCE(excluded.pv_a_kwh,      pv_a_kwh),
                    pv_b_kwh      = COALESCE(excluded.pv_b_kwh,      pv_b_kwh)
            """, (
                date_str,
                vals.get("yield_kwh"),
                vals.get("grid_feed_kwh"),
                vals.get("grid_draw_kwh"),
                vals.get("load_kwh"),
                vals.get("pv_a_kwh"),
                vals.get("pv_b_kwh"),
            ))
            written += 1
        conn.commit()
    finally:
        conn.close()
    return written


def main():
    parser = argparse.ArgumentParser(description="Backfill historical daily energy from RCT inverter")
    parser.add_argument("--config", help="Path to config file")
    args = parser.parse_args()

    cfg = load_config(args.config)
    host = cfg["inverter"]["host"]
    port = cfg["inverter"]["port"]
    db_path = cfg["database"]["path"]

    log.info("=== RCT Backfill: historical day-logger import ===")
    log.info("Inverter: %s:%d", host, port)
    log.info("Database: %s", db_path)

    # Ensure daily_energy table + updated daily_summary view exist
    run_migrations(db_path)

    # Fetch timeseries from inverter
    log.info("Connecting to inverter and fetching logger data...")
    all_series = fetch_all_timeseries(host, port)

    if not all_series:
        log.error("No data received from inverter. Exiting.")
        sys.exit(1)

    # Pivot and convert to daily rows
    by_date = merge_to_daily(all_series)
    log.info("Parsed %d unique days of data", len(by_date))

    if not by_date:
        log.error("No daily rows to write. Exiting.")
        sys.exit(1)

    # Show a preview
    dates = sorted(by_date.keys())
    log.info("Date range: %s → %s", dates[0], dates[-1])

    # Write to DB
    written = write_daily_energy(db_path, by_date)
    log.info("Wrote %d rows to daily_energy table.", written)

    # Print a summary table
    print("\n--- Daily Energy Summary (last 10 days) ---")
    print(f"{'Date':<12} {'Yield':>7} {'Feed':>7} {'Draw':>7} {'Load':>7}")
    print("-" * 46)
    for date_str in dates[-10:]:
        v = by_date[date_str]
        print(
            f"{date_str:<12} "
            f"{v.get('yield_kwh', 0):>6.2f}k "
            f"{v.get('grid_feed_kwh', 0):>6.2f}k "
            f"{v.get('grid_draw_kwh', 0):>6.2f}k "
            f"{v.get('load_kwh', 0):>6.2f}k"
        )
    print("\nDone. Refresh the dashboard to see historical stats.")


if __name__ == "__main__":
    main()
