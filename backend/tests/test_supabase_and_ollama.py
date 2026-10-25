"""Unit coverage for the Ollama client and Supabase persistence layer."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.models.ollama import OllamaClient, OllamaConfig


class FakeResponse:
    def __init__(self, payload=None, status_error=None):
        self.payload = payload or {}
        self.status_error = status_error
        self.raised = False

    def raise_for_status(self):
        self.raised = True
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.payload


class TestOllamaClient:
    def test_client_is_lazy_and_closable(self):
        client = OllamaClient(OllamaConfig(base_url="http://ollama.test", timeout=5))
        assert client._client is None
        assert isinstance(client.client, httpx.Client)
        assert client.client is client.client
        client.close()
        assert client._client is None
        # Closing twice is safe.
        client.close()

    def test_list_models_uses_cache(self):
        client = OllamaClient()
        client.models_cache = [{"name": "cached"}]
        client._client = MagicMock()
        assert client.list_models() == [{"name": "cached"}]
        client._client.get.assert_not_called()

    def test_list_models_success(self):
        client = OllamaClient()
        response = FakeResponse({"models": [{"name": "llama"}]})
        client._client = MagicMock()
        client._client.get.return_value = response
        assert client.list_models() == [{"name": "llama"}]
        assert response.raised is True
        client._client.get.assert_called_once_with("/api/tags")

    def test_list_models_handles_http_error(self):
        client = OllamaClient()
        client._client = MagicMock()
        client._client.get.side_effect = httpx.ConnectError("down")
        assert client.list_models() == []

    def test_generate_includes_optional_fields(self):
        client = OllamaClient()
        response = FakeResponse({"response": "  answer  "})
        client._client = MagicMock()
        client._client.post.return_value = response

        result = client.generate(
            "llama",
            "prompt",
            system_prompt="system",
            options={"temperature": 0},
            context=[1, 2],
        )

        assert result == "answer"
        payload = client._client.post.call_args.kwargs["json"]
        assert payload == {
            "model": "llama",
            "prompt": "prompt",
            "stream": False,
            "system": "system",
            "options": {"temperature": 0},
            "context": [1, 2],
        }

    def test_generate_minimal_payload(self):
        client = OllamaClient()
        client._client = MagicMock()
        client._client.post.return_value = FakeResponse({"response": ""})
        assert client.generate("llama", "prompt") == ""
        payload = client._client.post.call_args.kwargs["json"]
        assert "system" not in payload
        assert "options" not in payload
        assert "context" not in payload

    def test_generate_reraises_http_errors(self):
        client = OllamaClient()
        client._client = MagicMock()
        client._client.post.side_effect = httpx.ReadTimeout("slow")
        with pytest.raises(httpx.ReadTimeout):
            client.generate("llama", "prompt")

    def test_create_embedding_success(self):
        client = OllamaClient()
        client._client = MagicMock()
        client._client.post.return_value = FakeResponse({"embedding": [0.1, 0.2]})
        assert client.create_embedding("nomic", "text", truncate=False) == [0.1, 0.2]
        payload = client._client.post.call_args.kwargs["json"]
        assert payload == {"model": "nomic", "prompt": "text", "truncate": False}

    def test_create_embedding_handles_http_error(self):
        client = OllamaClient()
        client._client = MagicMock()
        client._client.post.side_effect = httpx.ConnectError("down")
        assert client.create_embedding("nomic", "text") == []


# ── Supabase persistence ────────────────────────────────────────


def _fake_client():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "row-1"}
    ]
    client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": "row-1"}
    ]
    client.table.return_value.upsert.return_value.execute.return_value.data = [
        {"id": "row-1"}
    ]
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
        []
    )
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = (
        []
    )
    client.auth.admin.list_users.return_value = []
    client.auth.admin.create_user.return_value = SimpleNamespace(
        user=SimpleNamespace(id="sb-new", email="new@example.com")
    )
    client.auth.sign_in_with_password.return_value = SimpleNamespace(
        session=SimpleNamespace(access_token="a", refresh_token="r")
    )
    return client


class TestSupabasePersistence:
    def test_get_bridge_secret_and_password_are_deterministic(self, monkeypatch):
        import backend.core.supabase as sb

        monkeypatch.setattr(sb, "_BRIDGE_SECRET", "secret-value")
        first = sb._bridge_password("user-1")
        second = sb._bridge_password("user-1")
        assert first == second
        assert first != sb._bridge_password("user-2")
        assert len(first) == 64

    def test_get_bridge_secret_fails_closed(self, monkeypatch):
        import backend.core.supabase as sb

        monkeypatch.setattr(sb, "_BRIDGE_SECRET", "")
        with pytest.raises(RuntimeError, match="SUPABASE_BRIDGE_SECRET"):
            sb.get_bridge_secret()

    def test_get_supabase_requires_service_key(self, monkeypatch):
        import backend.core.supabase as sb

        monkeypatch.setattr(sb, "_client", None)
        monkeypatch.setattr(sb, "_SERVICE_ROLE_KEY", "")
        with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
            sb.get_supabase()

    def test_get_supabase_creates_and_caches_client(self, monkeypatch):
        import backend.core.supabase as sb

        fake = _fake_client()
        monkeypatch.setattr(sb, "_client", None)
        monkeypatch.setattr(sb, "_SERVICE_ROLE_KEY", "service-key")
        with patch("backend.core.supabase.create_client", return_value=fake) as create:
            assert sb.get_supabase() is fake
            assert sb.get_supabase() is fake
        create.assert_called_once()

    def test_upsert_profile_returns_row_or_payload(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)

        row = sb.upsert_profile(
            supabase_user_id="sb-1",
            legacy_user_id="u-1",
            email="u@example.com",
            name="User",
        )
        assert row == {"id": "row-1"}
        payload = client.table.return_value.upsert.call_args.args[0]
        assert payload["legacy_user_id"] == "u-1"

        client.table.return_value.upsert.return_value.execute.return_value.data = []
        fallback = sb.upsert_profile(
            supabase_user_id="sb-1",
            legacy_user_id="u-1",
            email="u@example.com",
            name="User",
        )
        assert fallback["id"] == "sb-1"

    def test_get_profile_found_and_missing(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        assert sb.get_profile("u-1") is None

        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "profile"}
        ]
        assert sb.get_profile("u-1") == {"id": "profile"}

    def test_ensure_supabase_user_reuses_existing_email(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        client.auth.admin.list_users.return_value = [
            SimpleNamespace(id="sb-existing", email="User@Example.com")
        ]
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        monkeypatch.setattr(sb, "_bridge_password", lambda _: "derived")

        user = sb.ensure_supabase_user(email="user@example.com", legacy_user_id="u-1")
        assert user == {"id": "sb-existing", "email": "User@Example.com"}
        client.auth.admin.create_user.assert_not_called()

    def test_ensure_supabase_user_creates_missing(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        monkeypatch.setattr(sb, "_bridge_password", lambda _: "derived")

        user = sb.ensure_supabase_user(
            email="new@example.com",
            legacy_user_id="u-1",
            user_metadata={"name": "New"},
        )
        assert user == {"id": "sb-new", "email": "new@example.com"}
        payload = client.auth.admin.create_user.call_args.args[0]
        assert payload["email_confirm"] is True
        assert payload["password"] == "derived"

    def test_create_browser_session(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        monkeypatch.setattr(sb, "_bridge_password", lambda _: "derived")
        with patch("supabase.create_client", return_value=client) as create:
            session = sb.create_browser_session("u@example.com", "u-1")
        assert session == {"access_token": "a", "refresh_token": "r"}
        create.assert_called_once()

        client.auth.sign_in_with_password.return_value = SimpleNamespace(session=None)
        with patch("supabase.create_client", return_value=client):
            assert sb.create_browser_session("u@example.com", "u-1") == {
                "access_token": None,
                "refresh_token": None,
            }

    def test_create_session_inserts_planning_row(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        row = sb.create_session(
            user_id="u-1",
            title="T",
            prompt="P",
            mode="deep",
            debate_enabled=True,
        )
        assert row == {"id": "row-1"}
        payload = client.table.return_value.insert.call_args.args[0]
        assert payload["status"] == "planning"
        assert payload["debate_enabled"] is True

    def test_update_session(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        sb.update_session("s-1", status="completed")
        client.table.assert_called_with("rs_research_sessions")
        client.table.return_value.update.assert_called_with({"status": "completed"})
        client.table.return_value.update.return_value.eq.assert_called_with("id", "s-1")

    def test_insert_message(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        sb.insert_message(session_id="s-1", role="user", content="hi")
        payload = client.table.return_value.insert.call_args.args[0]
        assert payload == {
            "session_id": "s-1",
            "role": "user",
            "content": "hi",
            "metadata": {},
        }

    def test_upsert_agent_run_updates_existing(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        client.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"id": "run-1"}
        ]
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        sb.upsert_agent_run(
            session_id="s-1",
            agent_key="planner",
            status="completed",
            latency_ms=12.7,
        )
        client.table.return_value.update.assert_called_once()
        update_payload = client.table.return_value.update.call_args.args[0]
        assert update_payload["latency_ms"] == 12.7
        client.table.return_value.insert.assert_not_called()

    def test_upsert_agent_run_inserts_new(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        sb.upsert_agent_run(
            session_id="s-1",
            agent_key="planner",
            status="completed",
            started_at="2026-01-01T00:00:00Z",
        )
        insert_payload = client.table.return_value.insert.call_args.args[0]
        assert insert_payload["started_at"] == "2026-01-01T00:00:00Z"

    def test_save_run_metrics_defaults_total(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        sb.save_run_metrics(session_id="s-1", prompt_tokens=3, completion_tokens=4)
        payload = client.table.return_value.insert.call_args.args[0]
        assert payload["total_tokens"] == 7

        sb.save_run_metrics(session_id="s-1", total_tokens=99)
        assert client.table.return_value.insert.call_args.args[0]["total_tokens"] == 99

    def test_save_report_and_storage_helpers(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        report = sb.save_report(
            user_id="u-1",
            session_id="s-1",
            title="Title",
            content_md="Body",
            sources=[{"url": "https://x"}],
        )
        assert report == {"id": "row-1"}
        payload = client.table.return_value.insert.call_args.args[0]
        assert payload["status"] == "ready"
        assert payload["storage_path"] is None

        sb.set_report_storage_path("r-1", "path")
        client.table.return_value.update.assert_called_with({"storage_path": "path"})

        sb.set_report_status("r-1", "failed")
        client.table.return_value.update.assert_called_with({"status": "failed"})

    def test_upload_report_file_encodes_strings(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)
        path = sb.upload_report_file(
            user_id="u-1", report_id="r-1", filename="report.md", content="hello"
        )
        assert path == "u-1/r-1/report.md"
        upload = client.storage.from_.return_value.upload
        assert upload.call_args.args[0] == "u-1/r-1/report.md"
        assert upload.call_args.args[1] == b"hello"

        sb.upload_report_file(
            user_id="u-1", report_id="r-1", filename="raw.bin", content=b"bytes"
        )
        assert client.storage.from_.return_value.upload.call_args.args[1] == b"bytes"

    def test_log_activity_save_document_and_update_document(self, monkeypatch):
        import backend.core.supabase as sb

        client = _fake_client()
        monkeypatch.setattr(sb, "get_supabase", lambda: client)

        sb.log_activity(user_id="u-1", action="research.completed", entity_id="s-1")
        payload = client.table.return_value.insert.call_args.args[0]
        assert payload["action"] == "research.completed"

        doc = sb.save_document(
            user_id="u-1",
            name="file.pdf",
            storage_path="u-1/file.pdf",
            mime_type="application/pdf",
            size_bytes=10,
        )
        assert doc == {"id": "row-1"}
        assert (
            client.table.return_value.insert.call_args.args[0]["status"] == "indexing"
        )

        sb.update_document("d-1", status="ready")
        client.table.return_value.update.assert_called_with({"status": "ready"})

    def test_now_is_timezone_aware_isoformat(self):
        from backend.core.supabase import _now

        value = _now()
        assert "T" in value
        assert value.endswith("+00:00") or value.endswith("Z")
