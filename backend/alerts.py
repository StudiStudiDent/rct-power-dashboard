"""
backend/alerts.py — Push notification alerts via ntfy.sh

Monitors the readings table and sends push notifications when:
  1. Battery SOC falls below the configured threshold (e.g. 20%)
  2. No new readings for longer than inverter_offline_minutes (e.g. 5 min)

Runs as a FastAPI background task (started in lifespan).
Uses httpx for async HTTP to ntfy.sh. No external message queue needed.

ntfy.sh integration:
  POST https://ntfy.sh/{topic}
  Body: alert message
  Headers: Title, Priority, Tags

Config section (config.yaml):
  alerts:
    enabled: false
    ntfy_topic: "my-solar-alerts"      # unique topic name, keep private
    ntfy_server: "https://ntfy.sh"     # or self-hosted ntfy instance
    battery_low_pct: 20                # alert when SOC drops below this
    inverter_offline_minutes: 5        # alert when no data for this long
    check_interval_seconds: 60         # how often to check (default: 60)
"""

import asyncio
import logging
import time
from typing import Optional

import httpx

from backend.db import fetch_latest

log = logging.getLogger(__name__)

# Cooldown between repeated alerts of the same type (seconds)
# Prevents notification spam if the condition persists
ALERT_COOLDOWN_SECONDS = 30 * 60  # 30 minutes


async def send_ntfy(server: str, topic: str, message: str, title: str, priority: str = "default", tags: list[str] | None = None) -> None:
    """Send a push notification via ntfy.sh."""
    url = f"{server.rstrip('/')}/{topic}"
    headers = {
        "Title": title,
        "Priority": priority,
    }
    if tags:
        headers["Tags"] = ",".join(tags)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=message.encode(), headers=headers)
            resp.raise_for_status()
            log.info("Alert sent to ntfy topic '%s': %s", topic, title)
    except httpx.HTTPError as e:
        log.warning("Failed to send ntfy alert: %s", e)
    except Exception as e:
        log.warning("Unexpected error sending ntfy alert: %s", e)


async def alerts_task(cfg: dict) -> None:
    """
    Background task that monitors readings and sends alerts.
    Runs forever, checking every check_interval_seconds.
    """
    alerts_cfg = cfg.get("alerts", {})
    if not alerts_cfg.get("enabled", False):
        log.info("Alerts disabled (alerts.enabled = false in config)")
        return

    db_path: str = cfg["database"]["path"]
    ntfy_server: str = alerts_cfg.get("ntfy_server", "https://ntfy.sh")
    ntfy_topic: str = alerts_cfg.get("ntfy_topic", "")
    battery_low_pct: float = float(alerts_cfg.get("battery_low_pct", 20))
    offline_minutes: int = int(alerts_cfg.get("inverter_offline_minutes", 5))
    check_interval: int = int(alerts_cfg.get("check_interval_seconds", 60))

    if not ntfy_topic:
        log.warning("Alerts enabled but alerts.ntfy_topic is not set — alerts will not be sent")
        return

    log.info(
        "Alert monitor started: topic=%s battery_low=%.0f%% offline=%dmin",
        ntfy_topic, battery_low_pct, offline_minutes,
    )

    # Track last alert times to enforce cooldown
    last_battery_alert: Optional[float] = None
    last_offline_alert: Optional[float] = None
    # Track previous battery SOC to detect threshold crossing (not just being below)
    was_battery_low: bool = False

    while True:
        await asyncio.sleep(check_interval)

        try:
            reading = await fetch_latest(db_path)
            now = time.time()

            # ── Inverter offline check ──────────────────────────────────────
            if reading is None or reading.get("ts") is None:
                # No data at all — only alert after the offline threshold has passed
                # since we don't know when data was last available
                pass
            else:
                data_age_seconds = now - reading["ts"]
                offline_threshold = offline_minutes * 60

                if data_age_seconds > offline_threshold:
                    if last_offline_alert is None or (now - last_offline_alert) > ALERT_COOLDOWN_SECONDS:
                        age_min = int(data_age_seconds // 60)
                        await send_ntfy(
                            server=ntfy_server,
                            topic=ntfy_topic,
                            message=f"Wechselrichter antwortet seit {age_min} Minuten nicht mehr.",
                            title="Solar: Wechselrichter offline",
                            priority="high",
                            tags=["warning", "solar"],
                        )
                        last_offline_alert = now
                else:
                    # Data is fresh — reset offline alert state
                    last_offline_alert = None

            # ── Battery low check ───────────────────────────────────────────
            if reading is not None and reading.get("battery_soc") is not None:
                soc = reading["battery_soc"]
                is_low = soc < battery_low_pct

                # Alert on crossing the threshold (not every check while low)
                if is_low and not was_battery_low:
                    if last_battery_alert is None or (now - last_battery_alert) > ALERT_COOLDOWN_SECONDS:
                        await send_ntfy(
                            server=ntfy_server,
                            topic=ntfy_topic,
                            message=f"Batterie bei {soc:.0f}% — unter dem Schwellwert von {battery_low_pct:.0f}%.",
                            title=f"Solar: Batterie niedrig ({soc:.0f}%)",
                            priority="default",
                            tags=["battery", "solar"],
                        )
                        last_battery_alert = now

                was_battery_low = is_low

        except Exception as e:
            log.warning("Alert check error: %s", e)
