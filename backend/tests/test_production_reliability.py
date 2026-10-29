"""Production-reliability regression suite.

Locks in the provider-reliability fixes:
- LLM retry/backoff: transient upstream failures (429/5xx/timeouts/resets)
  are retried with bounded exponential backoff; permanent failures are
  never retried; exhaustion surfaces as a terminal ProviderUnavailableError
- Cross-provider fallback: when the primary provider is exhausted, an
  alternate registered + configured LLM provider takes over
- Cancel: research runs execute as tracked background tasks; the cancel
  endpoint terminates in-flight provider work and the run handler reaches
  a terminal "cancelled"/"failed" state instead of hanging forever
- Terminal status normalization: a run can never be stuck in "running"

These tests are permanent: they must keep passing so the failure classes
cannot silently reappear.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from backend.core.plugin import PluginSpec
from backend.llm.base import LLMProvider
from backend.llm.retry import (
    ProviderConfigError,
    ProviderUnavailableError,
    classify_exception,
    retry_after_seconds,
    with_retry,
)

# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_app():
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


def register(client, email: str, name: str = "Test User", password: str = "test-password-123"):
    resp = client.post("/auth/register", json={
        "email": email, "password": password, "name": name,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_headers(tokens: dict, org_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    if org_id:
        headers["X-Organization-Id"] = org_id
    return headers


def my_orgs(client, tokens) -> list[dict]:
    resp = client.get("/organizations", headers=auth_headers(tokens))
    assert resp.status_code == 200, resp.text
    return resp.json()


def jwt_sub(access_token: str) -> str:
    import jwt as pyjwt
    payload = pyjwt.decode(access_token, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"])
    return str(payload.get("sub", ""))


@pytest.fixture(scope="module")
def users(client):
    alice = register(client, "reliability-alice@example.com", "Alice")
    bob = register(client, "reliability-bob@example.com", "Bob")
    alice_org = my_orgs(client, alice)[0]
    bob_org = my_orgs(client, bob)[0]
    try:
        import jwt as pyjwt
        alice_id = str(pyjwt.decode(alice["access_token"], os.environ["JWT_SECRET_KEY"], algorithms=["HS256"])["sub"])
    except Exception:
        alice_id = ""
    return {"alice": alice, "bob": bob, "alice_org": alice_org, "bob_org": bob_org, "alice_id": alice_id}


# ═════════════════════════════════════════════════════════════════
# Retry classification + bounded retry
# ═════════════════════════════════════════════════════════════════

def _status_error(status: int, text: str = "", headers: dict | None = None) -> httpx.HTTPStatusError:
    req = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    resp = httpx.Response(status, request=req, text=text, headers=headers or {})
    return httpx.HTTPStatusError("upstream response", request=req, response=resp)


def _network_error() -> httpx.ConnectError:
    return httpx.ConnectError("connection refused", request=httpx.Request("POST", "https://example.invalid"))


class TestClassifyException:
    def test_429_transient(self):
        assert classify_exception(_status_error(429)) == "transient"

    def test_5xx_transient(self):
        for status in (500, 502, 503, 504):
            assert classify_exception(_status_error(status)) == "transient"

    def test_408_transient(self):
        assert classify_exception(_status_error(408)) == "transient"

    def test_401_403_404_permanent(self):
        for status in (401, 403, 404):
            assert classify_exception(_status_error(status)) == "permanent"

    def test_other_4xx_permanent(self):
        assert classify_exception(_status_error(400)) == "permanent"
        assert classify_exception(_status_error(422)) == "permanent"

    def test_exhaustion_marker_beats_4xx(self):
        exc = _status_error(402, text="ResourceExhausted: Worker local total request limit reached")
        assert classify_exception(exc) == "transient"

    def test_exhaustion_marker_in_5xx_body(self):
        exc = _status_error(502, text="proxy error: backend overloaded; retry later")
        assert classify_exception(exc) == "transient"

    def test_timeout_and_network_transient(self):
        assert classify_exception(httpx.TimeoutException("took too long")) == "transient"
        assert classify_exception(_network_error()) == "transient"
        assert classify_exception(ConnectionError("reset")) == "transient"

    def test_marker_in_message_text(self):
        assert classify_exception(RuntimeError("Too many requests, slow down")) == "transient"

    def test_unclassifiable_returns_none(self):
        assert classify_exception(ValueError("boom")) is None
        assert classify_exception(RuntimeError("weird")) is None


class TestRetryAfter:
    def test_numeric_header(self):
        exc = _status_error(503, headers={"Retry-After": "12"})
        assert retry_after_seconds(exc) == 12.0

    def test_http_date_header(self):
        from email.utils import formatdate
        future = formatdate(time.time() + 30, usegmt=True)
        exc = _status_error(429, headers={"Retry-After": future})
        wait = retry_after_seconds(exc)
        assert wait is not None and 20 <= wait <= 30

    def test_missing_header(self):
        assert retry_after_seconds(_status_error(503)) is None

    def test_garbage_header(self):
        exc = _status_error(503, headers={"Retry-After": "sometime soon"})
        assert retry_after_seconds(exc) is None


class TestWithRetry:
    def test_succeeds_on_first_attempt(self, monkeypatch):
        calls = []
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: calls.append(s))
        out = with_retry(
            lambda: "ok",
            provider="openrouter", model="m",
        )
        assert out == "ok"
        assert calls == []

    def test_retries_transient_then_succeeds(self, monkeypatch):
        calls = []
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: calls.append(s))
        attempts = {"n": 0}
        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise _status_error(503, text="temporarily unavailable")
            return "recovered"
        out = with_retry(flaky, provider="openrouter", model="m", max_attempts=3)
        assert out == "recovered"
        assert attempts["n"] == 3
        assert len(calls) == 2

    def test_exhaustion_raises_provider_unavailable(self, monkeypatch):
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: None)
        with pytest.raises(ProviderUnavailableError) as ei:
            with_retry(
                lambda: (_ for _ in ()).throw(_status_error(500)),
                provider="openrouter", model="m", max_attempts=2,
            )
        assert ei.value.provider == "openrouter"
        assert ei.value.model == "m"
        assert "temporarily unavailable" in str(ei.value)

    def test_permanent_error_never_retried(self, monkeypatch):
        calls = []
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: calls.append(s))
        with pytest.raises(ProviderConfigError):
            with_retry(
                lambda: (_ for _ in ()).throw(_status_error(404)),
                provider="openrouter", model="m", max_attempts=3,
            )
        assert calls == []

    def test_network_error_exhausted_becomes_unavailable(self, monkeypatch):
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: None)
        with pytest.raises(ProviderUnavailableError):
            with_retry(
                lambda: (_ for _ in ()).throw(_network_error()),
                provider="ollama", model="m", max_attempts=2,
            )

    def test_unclassifiable_error_propagates_untouched(self, monkeypatch):
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: None)
        with pytest.raises(ValueError, match="boom"):
            with_retry(
                lambda: (_ for _ in ()).throw(ValueError("boom")),
                provider="openrouter", model="m", max_attempts=2,
            )

    def test_respects_env_max_attempts(self, monkeypatch):
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: None)
        attempts = {"n": 0}
        def flaky():
            attempts["n"] += 1
            raise _status_error(502)
        with pytest.raises(ProviderUnavailableError):
            with_retry(flaky, provider="openrouter", model="m", max_attempts=4)
        assert attempts["n"] == 4


# ═════════════════════════════════════════════════════════════════
# Retry + cross-provider fallback through the LLMProvider base
# ═════════════════════════════════════════════════════════════════

class _FlakyLLM(LLMProvider):
    def __init__(self, name: str, failures: int = 0, fail_forever: bool = False):
        self.spec = PluginSpec(name=name, description=f"flaky {name}", version="1.0.0")
        self._failures = failures
        self._fail_forever = fail_forever
        self.calls = 0

    async def initialize(self):
        pass

    async def cleanup(self):
        pass

    def _generate_once(self, prompt, model, system_prompt=None, options=None):
        self.calls += 1
        if self._fail_forever or self.calls <= self._failures:
            raise _status_error(429, text="rate limit exceeded")
        return f"{self.spec.name}:{prompt[:20]}"

    def is_configured(self) -> bool:
        return True


class _HealthyLLM(LLMProvider):
    def __init__(self, name: str):
        self.spec = PluginSpec(name=name, description=f"healthy {name}", version="1.0.0")

    async def initialize(self):
        pass

    async def cleanup(self):
        pass

    def _generate_once(self, prompt, model, system_prompt=None, options=None):
        return f"{self.spec.name}:{prompt[:20]}"

    def is_configured(self) -> bool:
        return True


@pytest.fixture
def llm_registry():
    """Swap in a fresh plugin registry so fallback tests see only the
    providers they register (the shared registry already holds the
    built-in ollama/openrouter providers)."""
    import backend.core.registry as reg_module

    original = reg_module._registry
    fresh = reg_module.PluginRegistry()
    reg_module._registry = fresh
    try:
        yield fresh
    finally:
        reg_module._registry = original


class TestProviderFallback:
    def test_retry_recovers_without_fallback(self, api_app, llm_registry, monkeypatch):
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: None)
        from backend.core.registry import get_plugin_registry
        primary = _FlakyLLM("flaky_once", failures=2)
        get_plugin_registry().register(primary, "llm")
        out = primary.generate("hello", model="m")
        assert out == "flaky_once:hello"
        assert primary.calls == 3

    def test_fallback_used_when_primary_exhausted(self, api_app, llm_registry, monkeypatch):
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: None)
        from backend.core.registry import get_plugin_registry
        registry = get_plugin_registry()
        primary = _FlakyLLM("flaky_forever", fail_forever=True)
        backup = _HealthyLLM("healthy_backup")
        registry.register(primary, "llm")
        registry.register(backup, "llm")
        out = primary.generate("hello", model="m")
        assert out == "healthy_backup:hello"
        assert primary.calls == 3

    def test_fallback_survives_its_own_transient_blip(self, api_app, llm_registry, monkeypatch):
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: None)
        from backend.core.registry import get_plugin_registry
        registry = get_plugin_registry()
        primary = _FlakyLLM("flaky_forever", fail_forever=True)
        backup = _FlakyLLM("backup_blip", failures=1)
        registry.register(primary, "llm")
        registry.register(backup, "llm")
        out = primary.generate("hello", model="m")
        assert out == "backup_blip:hello"
        assert backup.calls == 2

    def test_no_alt_provider_raises_unavailable(self, api_app, llm_registry, monkeypatch):
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: None)
        from backend.core.registry import get_plugin_registry
        primary = _FlakyLLM("only_provider", fail_forever=True)
        get_plugin_registry().register(primary, "llm")
        with pytest.raises(ProviderUnavailableError):
            primary.generate("hello", model="m")

    def test_unconfigured_alternate_is_skipped(self, api_app, llm_registry, monkeypatch):
        monkeypatch.setattr("backend.llm.retry.time.sleep", lambda s: None)
        from backend.core.registry import get_plugin_registry
        registry = get_plugin_registry()
        primary = _FlakyLLM("flaky_a", fail_forever=True)
        registry.register(primary, "llm")
        unconfigured = _HealthyLLM("unconfigured_b")
        unconfigured.is_configured = lambda: False
        registry.register(unconfigured, "llm")
        with pytest.raises(ProviderUnavailableError):
            primary.generate("hello", model="m")


# ═════════════════════════════════════════════════════════════════
# Terminal status normalization
# ═════════════════════════════════════════════════════════════════

class TestNormalizeRunStatus:
    def test_completed_terminals_pass_through(self):
        from backend.api.main import _normalize_run_status
        assert _normalize_run_status({"status": "completed"}) == "completed"
        assert _normalize_run_status({"status": "failed"}) == "failed"
        assert _normalize_run_status({"status": "cancelled"}) == "cancelled"

    def test_none_result_marked_failed(self):
        from backend.api.main import _normalize_run_status
        assert _normalize_run_status(None) == "failed"

    def test_empty_result_marked_failed_with_note(self):
        from backend.api.main import _normalize_run_status
        result = {}
        assert _normalize_run_status(result) == "failed"
        assert any("terminal status" in str(e) for e in result.get("errors", []))

    def test_stuck_running_marked_failed(self):
        """A graph that returns without a terminal state must not leave the
        run permanently stuck at "running"."""
        from backend.api.main import _normalize_run_status
        result = {"status": "running", "errors": []}
        assert _normalize_run_status(result) == "failed"
        assert result["errors"]

    def test_unknown_status_marked_failed(self):
        from backend.api.main import _normalize_run_status
        result = {"status": "weird"}
        assert _normalize_run_status(result) == "failed"


# ═════════════════════════════════════════════════════════════════
# POST /research + POST /research/{task_id}/cancel
# ═════════════════════════════════════════════════════════════════

class _SlowGraph:
    """Graph whose run blocks until cancelled; records lifecycle events."""

    def __init__(self):
        self.started = threading.Event()
        self.cancelled = threading.Event()

    async def ainvoke(self, state, config=None):
        self.started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        return {"status": "completed", "answer": "never reaches here"}


class TestCancelEndpoint:
    def test_cancel_requires_auth(self, client):
        resp = client.post("/research/anything/cancel")
        assert resp.status_code == 401

    def test_cancel_unknown_task_is_benign(self, client, users):
        resp = client.post(
            f"/research/does-not-exist-{uuid.uuid4().hex[:8]}/cancel",
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["already_done"] is True

    def test_cancel_terminates_inflight_run(self, client, users, api_app):
        slow = _SlowGraph()
        original_graph = api_app.state.graph
        api_app.state.graph = slow
        task_id = f"cancel-{uuid.uuid4().hex[:8]}"
        raised = []

        def run_request():
            try:
                client.post(
                    "/research",
                    json={"query": "cancel me", "stream_task_id": task_id},
                    headers=auth_headers(users["alice"], users["alice_org"]["id"]),
                )
            except Exception as e:  # the handler is cancelled: no response
                raised.append(e)

        thread = threading.Thread(target=run_request)
        thread.start()
        try:
            assert slow.started.wait(10), "graph run never started"
            resp = client.post(
                f"/research/{task_id}/cancel",
                headers=auth_headers(users["alice"], users["alice_org"]["id"]),
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "cancelled"
            assert slow.cancelled.wait(10), "graph task was not cancelled"
        finally:
            thread.join(10)
            api_app.state.graph = original_graph

    def test_cancel_by_non_owner_rejected(self, client, users, api_app):
        slow = _SlowGraph()
        original_graph = api_app.state.graph
        api_app.state.graph = slow
        task_id = f"nope-{uuid.uuid4().hex[:8]}"

        thread = threading.Thread(
            target=lambda: client.post(
                "/research",
                json={"query": "secret", "stream_task_id": task_id},
                headers=auth_headers(users["alice"], users["alice_org"]["id"]),
            )
        )
        thread.start()
        try:
            assert slow.started.wait(10), "graph run never started"
            resp = client.post(
                f"/research/{task_id}/cancel",
                headers=auth_headers(users["bob"], users["bob_org"]["id"]),
            )
            assert resp.status_code == 403
        finally:
            # Cleanup: owner cancels so the run terminates.
            client.post(
                f"/research/{task_id}/cancel",
                headers=auth_headers(users["alice"], users["alice_org"]["id"]),
            )
            thread.join(10)
            api_app.state.graph = original_graph

    def test_run_reports_terminal_failed_without_an_answer(self, client, users, api_app):
        """A completed graph run that produced no answer still finishes with
        a terminal status (never 'running'), with the response surfaced."""
        original_graph = api_app.state.graph
        api_app.state.graph = AsyncMock()
        api_app.state.graph.ainvoke.return_value = {
            "status": "running",  # graph forgot to set a terminal status
            "answer": None, "sources": [], "logs": [], "plan": [],
            "errors": [], "pdf_paths": [],
        }
        try:
            resp = client.post(
                "/research",
                json={"query": "anything", "stream_task_id": "terminal-check"},
                headers=auth_headers(users["alice"], users["alice_org"]["id"]),
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["status"] == "failed"
            assert body["errors"], "a failed run must carry an error note"
        finally:
            api_app.state.graph = original_graph

    def test_run_reports_completed_status(self, client, users, api_app):
        original_graph = api_app.state.graph
        api_app.state.graph = AsyncMock()
        api_app.state.graph.ainvoke.return_value = {
            "status": "completed", "answer": "a real answer", "sources": [],
            "logs": [], "plan": [], "errors": [], "pdf_paths": [],
        }
        try:
            resp = client.post(
                "/research",
                json={"query": "anything", "stream_task_id": "terminal-ok"},
                headers=auth_headers(users["alice"], users["alice_org"]["id"]),
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["status"] == "completed"
            assert resp.json()["answer"] == "a real answer"
        finally:
            api_app.state.graph = original_graph
