# TODOS — RCT Power Dashboard

## Open

(leer)

## Completed

### ✓ Stale Data Indicator
`frontend/src/lib/components/StatusBadge.svelte` + `frontend/src/lib/stores/live.ts`
Shows "vor 42s" relative timestamp, red badge when data is >2 minutes old.

---

### ✓ Database Migration Strategy
`rct-poller.py` — `run_migrations()` replaces the old `init_db()` schema creation.
Uses `PRAGMA user_version` as version counter. Reads SQL files from `migrations/`
directory, applies any with version number > current, updates `PRAGMA user_version`.
Adding a new migration: create `migrations/002_description.sql`, it auto-applies on next startup.

---

### ✓ Alerting / Push-Benachrichtigungen
`backend/alerts.py` — background task (started in FastAPI lifespan).
Monitors readings every 60s (configurable). Sends ntfy.sh push notifications when:
- Battery SOC drops below `alerts.battery_low_pct` (default: 20%)
- No new inverter data for `alerts.inverter_offline_minutes` (default: 5 min)
30-minute cooldown between repeated alerts of the same type.
Requires `httpx` (added to requirements.txt).
Activate in `config.yaml`: set `alerts.enabled: true` and `alerts.ntfy_topic`.
