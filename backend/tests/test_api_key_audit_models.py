"""Tests for API key, audit log, and model catalog routes.

Split from backend/tests/test_workspace_documents_units.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.tests.test_workspace_doc_helpers import (
    NOW,
    APIKey,
    APIKeyCreate,
    Session,
    _audit,
    _ctx,
    _user,
    asyncio_run,
)
from fastapi import HTTPException


class TestAPIKeyAndAuditRoutes:
    def test_list_and_create_api_key(self):
        from backend.api.workspace import create_api_key, list_api_keys

        key = APIKey(
            id="key-1",
            organization_id="org-1",
            user_id="user-1",
            name="CLI",
            key_prefix="rs_abcd",
            key_hash="hash",
            permissions=["read"],
            is_active=True,
            created_at=NOW,
        )
        response = asyncio_run(
            list_api_keys(current_user=_user(), session=Session([key]), ctx=_ctx())
        )
        assert response[0].name == "CLI"

        session = Session()
        with patch("backend.api.workspace.log_audit", new=AsyncMock()):
            created = asyncio_run(
                create_api_key(
                    APIKeyCreate(name="New", permissions=["read"]),
                    current_user=_user(),
                    session=session,
                    ctx=_ctx(),
                )
            )
        assert created.raw_key.startswith("rs_")
        assert created.key_prefix == created.raw_key[:8]
        assert session.added[0].key_hash != created.raw_key

    def test_delete_api_key(self):
        from backend.api.workspace import delete_api_key

        key = APIKey(
            id="key-1",
            organization_id="org-1",
            user_id="user-1",
            name="CLI",
            key_prefix="rs_abcd",
            key_hash="hash",
            permissions=[],
            is_active=True,
            created_at=NOW,
        )
        with patch("backend.api.workspace.log_audit", new=AsyncMock()):
            assert asyncio_run(
                delete_api_key(
                    "key-1", current_user=_user(), session=Session(key), ctx=_ctx()
                )
            ) == {"status": "deleted"}
        assert key.is_active is False

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                delete_api_key(
                    "missing", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )
        assert missing.value.status_code == 404

    def test_audit_logs_filter(self):
        from backend.api.workspace import get_audit_logs

        session = Session([_audit()])
        response = asyncio_run(
            get_audit_logs(
                action="research.completed",
                limit=10,
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert response[0].action == "research.completed"

        session = Session([])
        assert (
            asyncio_run(
                get_audit_logs(
                    action=None,
                    limit=10,
                    current_user=_user(),
                    session=session,
                    ctx=_ctx(),
                )
            )
            == []
        )


class TestModelCatalog:
    def _client(self, response):
        client = AsyncMock()
        client.get.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False
        return client

    def test_openrouter_requires_key(self, monkeypatch):
        from backend.api.workspace import list_models

        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        result = asyncio_run(list_models())
        assert result["models"] == []
        assert "No API key" in result["error"]

    def test_openrouter_success_and_failure(self, monkeypatch):
        from backend.api.workspace import list_models

        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        response = MagicMock()
        response.json.return_value = {"data": [{"id": "b"}, {"id": "a"}, {"id": "a"}]}
        with patch("httpx.AsyncClient", return_value=self._client(response)):
            result = asyncio_run(list_models())
        assert result["models"] == ["a", "b"]
        assert result["count"] == 2

        response.raise_for_status.side_effect = RuntimeError("api down")
        with patch("httpx.AsyncClient", return_value=self._client(response)):
            result = asyncio_run(list_models())
        assert result["models"] == []
        assert "api down" in result["error"]

    def test_ollama_success_and_failure(self, monkeypatch):
        from backend.api.workspace import list_models

        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        response = MagicMock()
        response.json.return_value = {"models": [{"name": "llama"}, {"name": "llama"}]}
        with patch("httpx.AsyncClient", return_value=self._client(response)):
            result = asyncio_run(list_models())
        assert result["models"] == ["llama"]

        response.raise_for_status.side_effect = RuntimeError("down")
        with patch("httpx.AsyncClient", return_value=self._client(response)):
            result = asyncio_run(list_models())
        assert result["provider"] == "ollama"
        assert result["models"] == []

    def test_other_provider_lists_plugin_types(self, monkeypatch):
        from backend.api.workspace import list_models

        monkeypatch.setenv("LLM_PROVIDER", "custom")
        with patch("backend.core.registry.get_plugin_registry") as registry:
            registry.return_value.list_types.return_value = ["llm"]
            result = asyncio_run(list_models())
        assert result == {
            "provider": "custom",
            "models": [],
            "available_providers": ["llm"],
        }
