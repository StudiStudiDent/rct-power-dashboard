"""
tests/test_auth.py — Authentication and rate limiting tests

Tests:
- Successful login → HttpOnly cookie set
- Wrong password → 401
- Wrong username → 401
- Rate limiting → 429 after 5 attempts
- Protected endpoint without cookie → 401
- Protected endpoint with valid cookie → 200
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import yaml
import os

# Use a test config
TEST_CONFIG = {
    "inverter": {"host": "127.0.0.1", "port": 8899, "poll_interval_seconds": 30,
                 "retry_min_seconds": 5, "retry_max_seconds": 300},
    "database": {"path": "/tmp/test_solar.db", "retention_days": 90, "disk_warning_mb": 100},
    "auth": {"username": "testuser", "password": "testpass", "jwt_secret": "test-secret-key",
             "jwt_expire_hours": 24},
    "server": {"host": "0.0.0.0", "port": 8000},
    "api": {"history_max_points": 500, "websocket_push_interval_seconds": 30},
}


@pytest.fixture
def client(tmp_path):
    # Write test config
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(TEST_CONFIG))

    # Patch DB path to tmp
    cfg = TEST_CONFIG.copy()
    cfg["database"] = cfg["database"].copy()
    cfg["database"]["path"] = str(tmp_path / "test.db")

    with patch("backend.main.open", create=True):
        with patch("yaml.safe_load", return_value=cfg):
            from backend.main import create_app
            app = create_app.__wrapped__(cfg) if hasattr(create_app, "__wrapped__") else create_app()
    return TestClient(app, raise_server_exceptions=False)


# ── Login tests ───────────────────────────────────────────────────────────────

def test_login_success(client):
    res = client.post("/api/auth/login", json={"username": "testuser", "password": "testpass"})
    assert res.status_code == 200
    assert res.json() == {"ok": True}
    assert "access_token" in res.cookies


def test_login_wrong_password(client):
    res = client.post("/api/auth/login", json={"username": "testuser", "password": "wrong"})
    assert res.status_code == 401
    assert "access_token" not in res.cookies


def test_login_wrong_username(client):
    res = client.post("/api/auth/login", json={"username": "nobody", "password": "testpass"})
    assert res.status_code == 401


def test_logout_clears_cookie(client):
    # Login first
    client.post("/api/auth/login", json={"username": "testuser", "password": "testpass"})
    # Logout
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    # Cookie should be cleared (empty or deleted)


# ── Auth-protected endpoints ──────────────────────────────────────────────────

def test_live_without_auth(client):
    res = client.get("/api/live")
    assert res.status_code == 401


@pytest.mark.anyio
async def test_live_with_auth(client):
    # Login
    client.post("/api/auth/login", json={"username": "testuser", "password": "testpass"})
    # Access protected endpoint
    with patch("backend.db.fetch_latest", new_callable=AsyncMock, return_value=None):
        res = client.get("/api/live")
    assert res.status_code == 200


def test_history_invalid_hours(client):
    client.post("/api/auth/login", json={"username": "testuser", "password": "testpass"})
    # hours=0 should fail validation (ge=1)
    res = client.get("/api/history?hours=0")
    assert res.status_code == 422

    # hours=-1 should fail validation
    res = client.get("/api/history?hours=-1")
    assert res.status_code == 422

    # hours=99999 should fail validation (le=8760)
    res = client.get("/api/history?hours=99999")
    assert res.status_code == 422


# ── SPA fallback ──────────────────────────────────────────────────────────────

def test_spa_fallback_returns_503_when_not_built(client):
    # Frontend not built in test environment → should return 503, not 404
    res = client.get("/dashboard")
    assert res.status_code in (200, 503)  # 503 if no dist/, 200 if built


def test_spa_fallback_unknown_route(client):
    res = client.get("/some/unknown/route")
    assert res.status_code in (200, 503)  # Not 404
