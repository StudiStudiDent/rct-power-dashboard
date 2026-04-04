"""
main.py — FastAPI application for the RCT Power Dashboard.

Architecture:
  rct-poller.py → SQLite → this backend → REST API + WebSocket → SvelteKit PWA

Key decisions (from eng review):
- FastAPI NEVER calls rctclient directly (rctclient is sync, FastAPI is async)
- SPA fallback: all non-API GET routes return index.html (SvelteKit routing)
- JWT as HttpOnly Cookie (not localStorage)
- WebSocket IPC: internal asyncio task polls SQLite every 30s,
  pushes to all connected clients when ts changes
- Rate limiting on login: 5 req/min/IP via slowapi

Endpoints:
  POST /api/auth/login    — returns HttpOnly JWT cookie
  POST /api/auth/logout   — clears cookie
  GET  /api/live          — latest reading (auth required)
  GET  /api/history       — downsampled history (auth required)
  GET  /api/summary       — daily summary from SQL view (auth required)
  WS   /ws/live           — real-time push after each poll (auth required)
  GET  /{path}            — SPA fallback → index.html
"""

import asyncio
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import yaml
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.auth import create_access_token, hash_password, limiter, require_auth, verify_password
from backend.db import fetch_history, fetch_latest, fetch_latest_ts, fetch_summary
from backend.alerts import alerts_task

log = logging.getLogger(__name__)
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


# ─── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections for live data push.

    Tracks per-connection visibility state (tab active vs background).
    Push behaviour:
      - visible clients  → push on every new reading (~30 s)
      - background clients → push at most every BACKGROUND_PUSH_INTERVAL seconds
      - no clients        → skip entirely
    """

    BACKGROUND_PUSH_INTERVAL = 300  # 5 minutes

    def __init__(self):
        self._connections: dict[WebSocket, dict] = {}  # ws → {visible, last_push}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections[ws] = {"visible": True, "last_push": 0.0}

    def disconnect(self, ws: WebSocket):
        self._connections.pop(ws, None)

    def set_visible(self, ws: WebSocket, visible: bool):
        if ws in self._connections:
            self._connections[ws]["visible"] = visible
            log.debug("Client visibility → %s", "active" if visible else "background")

    async def broadcast(self, data: dict):
        now = time.time()
        dead = []
        for ws, state in self._connections.items():
            # Skip background clients unless enough time has passed
            if not state["visible"] and (now - state["last_push"]) < self.BACKGROUND_PUSH_INTERVAL:
                continue
            try:
                await ws.send_json(data)
                state["last_push"] = now
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.pop(ws, None)

    @property
    def count(self) -> int:
        return len(self._connections)

    @property
    def visible_count(self) -> int:
        return sum(1 for s in self._connections.values() if s["visible"])


manager = ConnectionManager()


# ─── Background WebSocket pusher ──────────────────────────────────────────────

async def ws_push_task(app: FastAPI):
    """
    Internal asyncio task: polls SQLite every 30s for new readings.
    When ts changes (new data from poller), broadcasts to all WebSocket clients.

    This is the IPC mechanism between rct-poller.py (separate process) and
    FastAPI WebSocket clients — no shared memory, no message queue needed.
    """
    cfg = app.state.config
    db_path = cfg["database"]["path"]
    interval = cfg["api"]["websocket_push_interval_seconds"]
    last_ts: Optional[int] = None

    while True:
        await asyncio.sleep(interval)
        if manager.count == 0:
            continue
        try:
            ts = await fetch_latest_ts(db_path)
            if ts is not None and ts != last_ts:
                last_ts = ts
                reading = await fetch_latest(db_path)
                if reading:
                    await manager.broadcast(reading)
        except Exception as e:
            log.warning("WebSocket push error: %s", e)


# ─── App lifespan ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(ws_push_task(app))
    alert_task = asyncio.create_task(alerts_task(app.state.config))
    yield
    task.cancel()
    alert_task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    try:
        await alert_task
    except asyncio.CancelledError:
        pass


# ─── App factory ──────────────────────────────────────────────────────────────

def create_app(config_path: str | None = None) -> FastAPI:
    if config_path is None:
        config_path = "config.yaml.local" if Path("config.yaml.local").exists() else "config.yaml"
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    app = FastAPI(title="RCT Power Dashboard", lifespan=lifespan)
    app.state.config = cfg

    # Hashed password stored at startup (not on every request)
    app.state.hashed_password = hash_password(cfg["auth"]["password"])

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ─── Auth endpoints ──────────────────────────────────────────────────────

    @app.post("/api/auth/login")
    @limiter.limit("5/minute")
    async def login(request: Request, response: Response):
        """
        Validates credentials, sets HttpOnly JWT cookie on success.
        Rate limited: 5 attempts/minute/IP.
        """
        body = await request.json()
        username = body.get("username", "")
        password = body.get("password", "")

        expected_user = cfg["auth"]["username"]
        if username != expected_user or not verify_password(password, app.state.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        token = create_access_token(
            subject=username,
            secret=cfg["auth"]["jwt_secret"],
            expire_hours=cfg["auth"]["jwt_expire_hours"],
        )
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="strict",
            secure=cfg["auth"].get("secure_cookie", False),
            max_age=cfg["auth"]["jwt_expire_hours"] * 3600,
        )
        return {"ok": True}

    @app.post("/api/auth/logout")
    async def logout(response: Response):
        response.delete_cookie("access_token")
        return {"ok": True}

    # ─── Data endpoints ──────────────────────────────────────────────────────

    @app.get("/api/live")
    async def live(
        _user=Depends(require_auth),
        db_path: str = cfg["database"]["path"],
    ):
        """Latest reading. Returns null values if DB is empty (poller not yet run)."""
        reading = await fetch_latest(db_path)
        if reading is None:
            return {
                "ts": None,
                "battery_soc": None,
                "pv_string1_w": None,
                "pv_string2_w": None,
                "grid_w": None,
                "load_w": None,
                "battery_w": None,
                "inverter_temp": None,
                "battery_status": None,
            }
        return reading

    @app.get("/api/history")
    async def history(
        hours: int = Query(default=24, ge=1, le=8760),
        _user=Depends(require_auth),
    ):
        """
        Downsampled history. Max 500 points regardless of time window.
        hours: 1-8760 (1 hour to 1 year). Validated by FastAPI.
        """
        db_path = cfg["database"]["path"]
        max_points = cfg["api"]["history_max_points"]
        return await fetch_history(db_path, hours, max_points)

    @app.get("/api/summary")
    async def summary(_user=Depends(require_auth)):
        """Daily summary from SQL view. Last 90 days."""
        return await fetch_summary(cfg["database"]["path"])

    # ─── WebSocket ────────────────────────────────────────────────────────────

    @app.websocket("/ws/live")
    async def websocket_live(ws: WebSocket):
        """
        Real-time data push. Validates auth cookie before accepting.
        Background task (ws_push_task) broadcasts when new data arrives.
        """
        token = ws.cookies.get("access_token")
        secret = cfg["auth"]["jwt_secret"]

        from backend.auth import decode_token
        if not token or not decode_token(token, secret):
            await ws.close(code=4001)
            return

        await manager.connect(ws)
        try:
            # Send current reading immediately on connect
            reading = await fetch_latest(cfg["database"]["path"])
            if reading:
                await ws.send_json(reading)
            # Listen for visibility messages from client
            while True:
                msg = await ws.receive_text()
                try:
                    data = json.loads(msg)
                    if "visible" in data:
                        manager.set_visible(ws, bool(data["visible"]))
                except Exception:
                    pass
        except WebSocketDisconnect:
            pass
        finally:
            manager.disconnect(ws)

    # ─── Static files + SPA fallback ─────────────────────────────────────────
    # NOTE: API routes above MUST be defined before the catch-all below.
    # SvelteKit static adapter puts compiled JS/CSS in _app/, not assets/

    if FRONTEND_DIST.exists() and (FRONTEND_DIST / "_app").exists():
        app.mount(
            "/_app",
            StaticFiles(directory=str(FRONTEND_DIST / "_app")),
            name="_app",
        )

    if FRONTEND_DIST.exists():
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            """
            SPA catch-all: returns index.html for all non-API routes.
            Required for SvelteKit client-side routing to work when navigating
            directly to a URL (e.g. /history, /stats).
            Also serves manifest.json, sw.js etc. from dist/ directly.
            """
            # Serve static files from dist root (manifest.json, sw.js, favicon...)
            static_file = FRONTEND_DIST / full_path
            if static_file.exists() and static_file.is_file():
                return FileResponse(str(static_file))
            index = FRONTEND_DIST / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return JSONResponse(
                {"error": "Frontend not built. Run: cd frontend && npm run build"},
                status_code=503,
            )
    else:
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_not_built(full_path: str):
            return JSONResponse(
                {"error": "Frontend not built. Run: cd frontend && npm run build"},
                status_code=503,
            )

    return app


app = create_app()
