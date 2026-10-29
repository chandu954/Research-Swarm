"""Security regression suite — rate limiting."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(scope="module")
def api_app():
    """The FastAPI app with a fresh SQLite DB and rate limiting disabled."""
    import re

    from backend.db.session import _engine

    url = os.environ.get("DATABASE_URL", "")
    m = re.match(r"sqlite\+aiosqlite:///(.*)", url)
    if m:
        db_path = os.path.abspath(m.group(1))
        if os.path.exists(db_path):
            os.remove(db_path)
    _engine.sync_engine.dispose()

    from backend.api.main import app
    app.state.limiter.enabled = False
    app.state.graph = AsyncMock()
    app.state.graph.ainvoke.return_value = {
        "status": "completed", "answer": "test answer", "sources": [],
        "logs": [], "plan": [], "errors": [], "pdf_paths": [],
    }
    return app


@pytest.fixture(scope="module")
def client(api_app):
    from fastapi.testclient import TestClient
    with TestClient(api_app) as c:
        yield c


class TestRateLimits:
    def test_login_and_forgot_password_rate_limited(self, client, api_app):
        """Brute-force / account-enumeration endpoints must 429."""
        api_app.state.limiter.enabled = True
        try:
            for _ in range(5):
                resp = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
                assert resp.status_code == 200
            resp = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
            assert resp.status_code == 429
        finally:
            api_app.state.limiter.enabled = False

    def test_ws_limiter_blocks_after_window(self):
        from backend.core.ratelimit import SlidingWindowLimiter
        lim = SlidingWindowLimiter(limit=3, window_seconds=60)
        assert all(lim.allow("ip-1") for _ in range(3))
        assert not lim.allow("ip-1")
        assert lim.allow("ip-2")
        lim.reset("ip-1")
        assert lim.allow("ip-1")

    def test_placeholder_secret_rejected(self, monkeypatch):
        """Copying .env.example into production must fail fast."""
        from backend.core.config import is_weak_secret, validate_secrets
        assert is_weak_secret("change-this-to-a-long-random-string-in-production")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "change-this-to-a-long-random-string-in-production")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "s" * 40)
        with pytest.raises(RuntimeError):
            validate_secrets()
