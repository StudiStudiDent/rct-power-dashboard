#!/usr/bin/env python3
"""
rct-poller.py — RCT Power Inverter Data Collector

Polls the inverter every 30s via rctclient and writes readings to SQLite.
Runs as a standalone process / systemd service, separate from the web backend.

Architecture rule: this is the ONLY place rctclient is called.
FastAPI reads SQLite, never calls rctclient directly.

Data flow:
  RCT Inverter :8899
       ↓ TCP (rctclient, sync)
  poll_once()
       ↓
  SQLite readings table (WAL mode, UPSERT on ts)
       ↓
  FastAPI reads SQLite → serves API → WebSocket push
"""

import asyncio
import logging
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import yaml
from rctclient.registry import REGISTRY as R
from rctclient.frame import ReceiveFrame
from rctclient.types import DataType
import socket
import struct

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# RCT object IDs we care about — verified against rctclient registry
OBJECT_IDS = {
    "battery_soc":      0x959930BF,  # battery.soc — 0..1 (multiply by 100 for %)
    "pv_string1_w":     0xB5317B78,  # dc_conv.dc_conv_struct[0].p_dc — Watt
    "pv_string2_w":     0xAA9AA253,  # dc_conv.dc_conv_struct[1].p_dc — Watt
    "grid_w":           0x91617C58,  # g_sync.p_ac_grid_sum_lp — W (+= feed-in, -= draw)
    "load_w":           0x1AC87AA0,  # g_sync.p_ac_load_sum_lp — W
    "battery_w":        0x400F015B,  # g_sync.p_acc_lp — W (-= charging, += discharging)
    "inverter_temp":    0xC24E85D0,  # db.core_temp — °C
    "battery_status":   0x70A2AF4F,  # battery.bat_status — integer status code
}


def load_config(path: str | None = None) -> dict:
    if path is None:
        path = "config.yaml.local" if Path("config.yaml.local").exists() else "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def run_migrations(db_path: str) -> None:
    """
    Apply pending SQL migrations from the migrations/ directory.

    Uses PRAGMA user_version as the schema version counter.
    Each migration file is named NNN_description.sql where NNN is an integer.
    Files with NNN > current user_version are applied in order, then user_version
    is updated. Idempotent: safe to call on every startup.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    migrations_dir = Path(__file__).parent / "migrations"

    conn = sqlite3.connect(db_path)
    try:
        current_version = conn.execute("PRAGMA user_version").fetchone()[0]
        log.info("DB schema version: %d", current_version)

        sql_files = sorted(migrations_dir.glob("*.sql"))
        applied = 0
        for f in sql_files:
            try:
                file_version = int(f.stem.split("_")[0])
            except ValueError:
                log.warning("Skipping migration file with non-integer prefix: %s", f.name)
                continue

            if file_version <= current_version:
                continue

            log.info("Applying migration %s", f.name)
            conn.executescript(f.read_text())
            conn.execute(f"PRAGMA user_version = {file_version}")
            conn.commit()
            current_version = file_version
            applied += 1

        if applied == 0:
            log.info("Database schema up to date (version %d)", current_version)
        else:
            log.info("Applied %d migration(s), schema now at version %d", applied, current_version)
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    """Initialize database by running all pending migrations. Idempotent."""
    run_migrations(db_path)
    log.info("Database initialized at %s", db_path)


def check_disk_space(db_path: str, warn_mb: int) -> bool:
    """Returns False if free disk space is below warn_mb. Logs a warning."""
    try:
        usage = shutil.disk_usage(str(Path(db_path).parent))
        free_mb = usage.free / (1024 * 1024)
        if free_mb < warn_mb:
            log.warning(
                "Low disk space: %.0f MB free (threshold: %d MB). Skipping write.",
                free_mb, warn_mb,
            )
            return False
    except Exception as e:
        log.warning("Could not check disk space: %s", e)
    return True


def read_object(sock: socket.socket, object_id: int) -> float | int | None:
    """
    Read a single value from the inverter via rctclient protocol.
    Returns None on any failure.

    Protocol: send read-request frame, receive response frame.
    Connection is managed by caller (one connection per poll cycle).
    """
    try:
        from rctclient.frame import make_frame
        from rctclient.exceptions import FrameCRCMismatch

        frame = make_frame(command=0x01, id=object_id)
        sock.sendall(frame)

        recv = ReceiveFrame()
        while True:
            ready = select_readable(sock, timeout=5.0)
            if not ready:
                log.warning("Timeout reading object 0x%08X", object_id)
                return None
            data = sock.recv(1024)
            if not data:
                return None
            for byte in data:
                recv.consume(bytes([byte]))
                if recv.complete():
                    break
            if recv.complete():
                break

        # Verify response matches request — inverter can return stale frames
        if recv.id != object_id:
            log.debug("ID mismatch: expected 0x%08X, got 0x%08X", object_id, recv.id)
            return None

        obj = R.get_by_id(object_id)
        data_type = obj.response_data_type
        if data_type == DataType.FLOAT:
            return struct.unpack('>f', recv.data)[0]
        elif data_type in (DataType.INT32, DataType.INT16, DataType.INT8):
            fmt = {DataType.INT32: '>i', DataType.INT16: '>h', DataType.INT8: '>b'}[data_type]
            return struct.unpack(fmt, recv.data)[0]
        elif data_type in (DataType.UINT32, DataType.UINT16, DataType.UINT8):
            fmt = {DataType.UINT32: '>I', DataType.UINT16: '>H', DataType.UINT8: '>B'}[data_type]
            return struct.unpack(fmt, recv.data)[0]
        else:
            log.debug("Unhandled data_type %s for object 0x%08X", data_type, object_id)
            return None

    except Exception as e:
        log.debug("Error reading object 0x%08X: %s", object_id, e)
        return None


def select_readable(sock: socket.socket, timeout: float) -> bool:
    """Non-blocking readability check with timeout."""
    import select
    r, _, _ = select.select([sock], [], [], timeout)
    return bool(r)


def poll_once(host: str, port: int) -> dict | None:
    """
    Open a TCP connection, read all configured values, close connection.
    Returns dict of values or None if connection failed.

    Connection is closed after each poll to avoid firmware connection-limit issues.
    """
    result = {}
    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            sock.settimeout(10)
            for field, obj_id in OBJECT_IDS.items():
                val = read_object(sock, obj_id)
                result[field] = val

        # battery_soc comes as 0..1 from inverter, convert to 0..100
        if result.get("battery_soc") is not None:
            result["battery_soc"] = round(result["battery_soc"] * 100, 1)

        return result

    except (ConnectionRefusedError, TimeoutError, OSError) as e:
        log.warning("Could not connect to inverter %s:%d — %s", host, port, e)
        return None


def write_latest(db_path: str, ts: int, values: dict) -> None:
    """
    Overwrite the single-row latest_reading table with the most recent poll.
    Always id=1 — UPSERT pattern. Used by FastAPI for live display.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""
        INSERT INTO latest_reading (
            id, ts, battery_soc, pv_string1_w, pv_string2_w,
            grid_w, load_w, battery_w, inverter_temp, battery_status
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            ts             = excluded.ts,
            battery_soc    = excluded.battery_soc,
            pv_string1_w   = excluded.pv_string1_w,
            pv_string2_w   = excluded.pv_string2_w,
            grid_w         = excluded.grid_w,
            load_w         = excluded.load_w,
            battery_w      = excluded.battery_w,
            inverter_temp  = excluded.inverter_temp,
            battery_status = excluded.battery_status
    """, (
        ts,
        values.get("battery_soc"),
        values.get("pv_string1_w"),
        values.get("pv_string2_w"),
        values.get("grid_w"),
        values.get("load_w"),
        values.get("battery_w"),
        values.get("inverter_temp"),
        values.get("battery_status"),
    ))
    conn.commit()
    conn.close()


def write_reading(db_path: str, ts: int, values: dict) -> None:
    """
    Write a reading to SQLite using UPSERT (ON CONFLICT(ts) DO UPDATE).
    Preserves existing row ID — safer than INSERT OR REPLACE.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("""
        INSERT INTO readings (
            ts, battery_soc, pv_string1_w, pv_string2_w,
            grid_w, load_w, battery_w, inverter_temp, battery_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ts) DO UPDATE SET
            battery_soc    = excluded.battery_soc,
            pv_string1_w   = excluded.pv_string1_w,
            pv_string2_w   = excluded.pv_string2_w,
            grid_w         = excluded.grid_w,
            load_w         = excluded.load_w,
            battery_w      = excluded.battery_w,
            inverter_temp  = excluded.inverter_temp,
            battery_status = excluded.battery_status
    """, (
        ts,
        values.get("battery_soc"),
        values.get("pv_string1_w"),
        values.get("pv_string2_w"),
        values.get("grid_w"),
        values.get("load_w"),
        values.get("battery_w"),
        values.get("inverter_temp"),
        values.get("battery_status"),
    ))
    conn.commit()
    conn.close()


def cleanup_old_readings(db_path: str, retention_days: int) -> None:
    """Delete readings older than retention_days. Runs once per poll cycle."""
    cutoff = int(time.time()) - (retention_days * 86400)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    cur = conn.execute("DELETE FROM readings WHERE ts < ?", (cutoff,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if deleted > 0:
        log.info("Retention cleanup: deleted %d readings older than %d days", deleted, retention_days)


def main():
    cfg = load_config()
    inv = cfg["inverter"]
    db_cfg = cfg["database"]

    host = inv["host"]
    port = inv["port"]
    interval = inv["poll_interval_seconds"]
    db_write_every = inv.get("db_write_every", 1)  # default: write every poll
    retry_min = inv["retry_min_seconds"]
    retry_max = inv["retry_max_seconds"]
    db_path = db_cfg["path"]
    retention_days = db_cfg["retention_days"]
    disk_warn_mb = db_cfg["disk_warning_mb"]

    init_db(db_path)

    retry_delay = retry_min
    poll_count = 0

    log.info("Polling %s:%d every %ds, DB write every %d polls (%ds)",
             host, port, interval, db_write_every, interval * db_write_every)

    while True:
        start = time.monotonic()

        if not check_disk_space(db_path, disk_warn_mb):
            time.sleep(interval)
            continue

        values = poll_once(host, port)

        if values is None:
            log.warning("Poll failed. Retrying in %ds", retry_delay)
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, retry_max)
            continue

        # Successful poll — reset retry backoff
        retry_delay = retry_min

        ts = int(time.time())

        # Always update latest_reading for live display
        write_latest(db_path, ts, values)

        # Write to history readings table only every Nth poll
        if poll_count % db_write_every == 0:
            write_reading(db_path, ts, values)

        poll_count += 1
        if poll_count % 10 == 0:
            pv_total = (values.get("pv_string1_w") or 0) + (values.get("pv_string2_w") or 0)
            log.info(
                "Poll #%d — Bat: %.0f%% | PV: %.0fW | Grid: %.0fW | Load: %.0fW",
                poll_count,
                values.get("battery_soc") or 0,
                pv_total,
                values.get("grid_w") or 0,
                values.get("load_w") or 0,
            )

        # Run retention cleanup every ~10 minutes (every 20 polls at 30s)
        if poll_count % 20 == 0:
            cleanup_old_readings(db_path, retention_days)

        # Sleep for remaining interval time
        elapsed = time.monotonic() - start
        sleep_for = max(0, interval - elapsed)
        time.sleep(sleep_for)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Poller stopped.")
    except FileNotFoundError as e:
        log.error("Config file not found: %s", e)
        sys.exit(1)
