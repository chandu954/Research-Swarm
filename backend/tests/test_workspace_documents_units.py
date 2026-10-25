"""Direct-route coverage for workspace utilities and document handling."""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.auth.tenant import _resolve_permissions
from backend.core.ratelimit import limiter
from backend.db.models import (
    APIKey,
    AuditLog,
    Conversation,
    Document,
    DocumentVersion,
    Message,
    Notification,
    User,
)
from backend.db.schemas import APIKeyCreate, SearchRequest


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


NOW = datetime.now(timezone.utc)


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self.value, list):
            return self.value
        return [] if self.value is None else [self.value]

    def one(self):
        return self.value


class Session:
    def __init__(self, *results, scalar_values=()):
        self.results = list(results)
        self.scalar_values = list(scalar_values)
        self.added = []
        self.deleted = []
        self.flushes = 0

    async def execute(self, *_args, **_kwargs):
        return Result(self.results.pop(0) if self.results else None)

    async def scalar(self, *_args, **_kwargs):
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def flush(self):
        self.flushes += 1
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = str(uuid.uuid4())
            for attr in ("created_at", "updated_at", "joined_at"):
                if hasattr(item, attr) and getattr(item, attr) is None:
                    setattr(item, attr, NOW)
            for attr in ("is_active", "is_read", "is_deleted", "has_ocr"):
                if hasattr(item, attr) and getattr(item, attr) is None:
                    setattr(item, attr, True if attr != "is_read" else False)

    def add(self, item):
        self.added.append(item)

    async def delete(self, item):
        self.deleted.append(item)


def _user(user_id="user-1"):
    return User(
        id=user_id,
        email=f"{user_id}@example.com",
        name="User",
        is_active=True,
        mfa_enabled=False,
        created_at=NOW,
        updated_at=NOW,
    )


def _ctx(**overrides):
    values = {
        "organization_id": "org-1",
        "organization_slug": "org",
        "workspace_id": None,
        "project_id": None,
        "user_id": "user-1",
        "user_role": "owner",
        "permissions": _resolve_permissions("owner"),
    }
    values.update(overrides)
    from backend.auth.tenant import TenantContext

    return TenantContext(**values)


def _document(**overrides):
    values = {
        "id": "doc-1",
        "user_id": "user-1",
        "organization_id": "org-1",
        "workspace_id": "ws-1",
        "project_id": None,
        "filename": "stored.pdf",
        "original_filename": "report.pdf",
        "size_bytes": 10,
        "mime_type": "application/pdf",
        "storage_path": "/tmp/report.pdf",
        "storage_backend": "local",
        "auto_tags": [],
        "is_deleted": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Document(**values)


def _notification(**overrides):
    values = {
        "id": "notif-1",
        "user_id": "user-1",
        "organization_id": "org-1",
        "type": "info",
        "title": "Hello",
        "body": "Body",
        "data": {},
        "is_read": False,
        "created_at": NOW,
    }
    values.update(overrides)
    return Notification(**values)


def _audit(**overrides):
    values = {
        "id": "audit-1",
        "organization_id": "org-1",
        "workspace_id": None,
        "user_id": "user-1",
        "action": "research.completed",
        "resource_type": "session",
        "resource_id": "s-1",
        "details": {},
        "ip_address": None,
        "user_agent": None,
        "created_at": NOW,
    }
    values.update(overrides)
    return AuditLog(**values)


def _conversation(**overrides):
    values = {
        "id": "conv-12345678",
        "user_id": "user-1",
        "organization_id": "org-1",
        "workspace_id": "ws-1",
        "project_id": None,
        "title": "Title",
        "description": "Description",
        "is_archived": False,
        "is_pinned": False,
        "is_favorited": False,
        "is_deleted": False,
        "visibility": "workspace",
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Conversation(**values)


# ── Notifications ───────────────────────────────────────────────


class TestNotificationRoutes:
    def test_list_unread_and_all(self):
        from backend.api.workspace import list_notifications

        session = Session([_notification()])
        response = asyncio_run(
            list_notifications(
                include_read=False,
                limit=10,
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert response[0].title == "Hello"

        session = Session([])
        assert (
            asyncio_run(
                list_notifications(
                    include_read=True,
                    limit=10,
                    current_user=_user(),
                    session=session,
                    ctx=_ctx(),
                )
            )
            == []
        )

    def test_mark_read(self):
        from backend.api.workspace import mark_notification_read

        notification = _notification()
        assert asyncio_run(
            mark_notification_read(
                "notif-1", current_user=_user(), session=Session(notification)
            )
        ) == {"status": "read"}
        assert notification.is_read is True
        assert notification.read_at is not None

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                mark_notification_read(
                    "missing", current_user=_user(), session=Session(None)
                )
            )
        assert missing.value.status_code == 404

    def test_mark_all_read(self):
        from backend.api.workspace import mark_all_read

        session = Session()
        assert asyncio_run(mark_all_read(current_user=_user(), session=session)) == {
            "status": "all_read"
        }
        assert session.flushes == 1


# ── Global search ───────────────────────────────────────────────


class TestGlobalSearch:
    def test_searches_all_resource_types_and_sorts(self):
        from backend.api.workspace import global_search

        message = Message(
            id="msg-1",
            conversation_id="conv-12345678",
            role="user",
            content="A message about RAG",
            sources=[],
            metadata_={},
            created_at=NOW,
        )
        session = Session(
            [_conversation()],
            [_document()],
            [message],
        )
        response = asyncio_run(
            global_search(
                SearchRequest(query="RAG"),
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert [item.resource_type for item in response] == [
            "conversation",
            "document",
            "message",
        ]
        assert response[-1].title.startswith("Message in conv-123")

    def test_searches_selected_types_only(self):
        from backend.api.workspace import global_search

        session = Session([])
        response = asyncio_run(
            global_search(
                SearchRequest(query="x", resource_types=["documents"]),
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert response == []
        assert len(session.results) == 0


# ── Billing ─────────────────────────────────────────────────────


class TestBilling:
    def test_usage_for_own_org(self):
        from backend.api.workspace import get_billing_usage

        session = Session((1, 2, 3, 4, 5.5, 0.25))
        response = asyncio_run(
            get_billing_usage(
                organization_id="org-1",
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert response.tokens_in == 1
        assert response.compute_seconds == 5.5
        assert response.estimated_cost == 0.25

    def test_usage_rejects_foreign_org(self):
        from backend.api.workspace import get_billing_usage

        with pytest.raises(HTTPException) as denied:
            asyncio_run(
                get_billing_usage(
                    organization_id="other",
                    current_user=_user(),
                    session=Session(),
                    ctx=_ctx(),
                )
            )
        assert denied.value.status_code == 403


# ── API keys and audit logs ─────────────────────────────────────


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


# ── Model catalog ───────────────────────────────────────────────


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


# ── Documents ───────────────────────────────────────────────────


class FakeUpload:
    def __init__(self, filename, content, error=None):
        self.filename = filename
        self.content = content
        self.error = error

    async def read(self):
        if self.error:
            raise self.error
        return self.content


class TestDocumentUpload:
    @pytest.fixture(autouse=True)
    def _disable_limiter(self):
        with patch.object(limiter, "enabled", False):
            yield

    def _request(self, content_length=None):
        headers = {}
        if content_length:
            headers["content-length"] = str(content_length)
        return SimpleNamespace(headers=headers)

    def test_rejects_non_pdf(self):
        from backend.api.documents import upload_document

        with pytest.raises(HTTPException) as error:
            asyncio_run(
                upload_document(
                    self._request(),
                    FakeUpload("notes.txt", b"hello"),
                    current_user=_user(),
                    session=Session(),
                    ctx=_ctx(),
                )
            )
        assert error.value.status_code == 400

    def test_rejects_oversized_content_length(self):
        from backend.api.documents import upload_document

        with pytest.raises(HTTPException) as error:
            asyncio_run(
                upload_document(
                    self._request(51 * 1024 * 1024),
                    FakeUpload("doc.pdf", b"%PDF-1.4"),
                    current_user=_user(),
                    session=Session(),
                    ctx=_ctx(),
                )
            )
        assert error.value.status_code == 413

    def test_rejects_empty_filename(self):
        from backend.api.documents import upload_document

        with pytest.raises(HTTPException) as error:
            asyncio_run(
                upload_document(
                    self._request(),
                    FakeUpload("", b"%PDF-1.4"),
                    current_user=_user(),
                    session=Session(),
                    ctx=_ctx(),
                )
            )
        assert error.value.status_code == 400

    def test_rejects_invalid_pdf_magic(self):
        from backend.api.documents import upload_document

        with patch("backend.api.documents.UPLOAD_DIR", "/tmp"):
            with pytest.raises(HTTPException) as error:
                asyncio_run(
                    upload_document(
                        self._request(),
                        FakeUpload("doc.pdf", b"not a pdf"),
                        current_user=_user(),
                        session=Session(),
                        ctx=_ctx(),
                    )
                )
        assert error.value.status_code == 400

    def test_upload_success_and_failure(self, tmp_path):
        from backend.api.documents import upload_document

        session = Session()
        with patch("backend.api.documents.UPLOAD_DIR", str(tmp_path)), patch(
            "backend.api.documents._mirror_document_upload"
        ) as mirror, patch("backend.api.documents.log_audit", new=AsyncMock()):
            response = asyncio_run(
                upload_document(
                    self._request(),
                    FakeUpload("report.pdf", b"%PDF-1.4 content"),
                    current_user=_user(),
                    session=session,
                    ctx=_ctx(),
                )
            )
        assert response["filename"] == "report.pdf"
        assert response["size"] == len(b"%PDF-1.4 content")
        assert mirror.called
        assert os.path.exists(
            os.path.join(
                tmp_path, response["document_id"] and session.added[0].filename
            )
        )

        with patch("backend.api.documents.UPLOAD_DIR", str(tmp_path)):
            with pytest.raises(HTTPException) as error:
                asyncio_run(
                    upload_document(
                        self._request(),
                        FakeUpload("doc.pdf", b"%PDF", error=RuntimeError("disk")),
                        current_user=_user(),
                        session=Session(),
                        ctx=_ctx(),
                    )
                )
        assert error.value.status_code == 500

    def test_mirror_skips_without_profile_and_handles_errors(self):
        from backend.api.documents import _mirror_document_upload

        supabase = MagicMock()
        supabase.get_profile.return_value = None
        with patch.dict("sys.modules", {"backend.core.supabase": supabase}):
            _mirror_document_upload(
                user_id="u", document_id="d", filename="f.pdf", content=b"x"
            )
        supabase.get_supabase.assert_not_called()

        supabase.get_profile.return_value = {"id": "sb-1"}
        supabase.save_document.return_value = {"id": "row-1"}
        with patch.dict("sys.modules", {"backend.core.supabase": supabase}):
            _mirror_document_upload(
                user_id="u", document_id="d", filename="f.pdf", content=b"x"
            )
        supabase.update_document.assert_called_once_with("row-1", status="ready")
        supabase.log_activity.assert_called_once()

        supabase.get_profile.side_effect = RuntimeError("down")
        with patch.dict("sys.modules", {"backend.core.supabase": supabase}):
            _mirror_document_upload(
                user_id="u", document_id="d", filename="f.pdf", content=b"x"
            )


class TestDocumentReadRoutes:
    def test_list_with_filters(self):
        from backend.api.documents import list_documents

        session = Session([_document()])
        response = asyncio_run(
            list_documents(
                search="report",
                include_deleted=False,
                current_user=_user(),
                session=session,
                ctx=_ctx(project_id="proj-1"),
            )
        )
        assert response[0].filename == "stored.pdf"

        session = Session([])
        assert (
            asyncio_run(
                list_documents(
                    search=None,
                    include_deleted=True,
                    current_user=_user(),
                    session=session,
                    ctx=_ctx(workspace_id="ws-1"),
                )
            )
            == []
        )

    def test_get_document(self):
        from backend.api.documents import get_document

        response = asyncio_run(
            get_document(
                "doc-1",
                current_user=_user(),
                session=Session(_document()),
                ctx=_ctx(),
            )
        )
        assert response.id == "doc-1"

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                get_document(
                    "missing", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )
        assert missing.value.status_code == 404

    def test_versions(self):
        from backend.api.documents import get_document_versions

        version = DocumentVersion(
            id="v-1",
            document_id="doc-1",
            version_number=2,
            storage_path="/tmp/v2.pdf",
            size_bytes=10,
            created_at=NOW,
        )
        response = asyncio_run(
            get_document_versions(
                "doc-1",
                current_user=_user(),
                session=Session(_document(), [version]),
                ctx=_ctx(),
            )
        )
        assert response[0].version_number == 2

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                get_document_versions(
                    "missing", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )
        assert missing.value.status_code == 404

    def test_soft_delete_and_restore(self):
        from backend.api.documents import restore_document, soft_delete_document

        document = _document()
        with patch("backend.api.documents.log_audit", new=AsyncMock()):
            assert asyncio_run(
                soft_delete_document(
                    "doc-1", current_user=_user(), session=Session(document), ctx=_ctx()
                )
            ) == {"status": "deleted"}
        assert document.is_deleted is True

        assert asyncio_run(
            restore_document(
                "doc-1", current_user=_user(), session=Session(document), ctx=_ctx()
            )
        ) == {"status": "restored"}
        assert document.is_deleted is False

        with pytest.raises(HTTPException):
            asyncio_run(
                soft_delete_document(
                    "missing", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )
        with pytest.raises(HTTPException):
            asyncio_run(
                restore_document(
                    "missing", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )


class TestDocumentDownloads:
    def test_signed_download_valid_and_invalid(self, tmp_path):
        from backend.api.documents import download_document

        path = tmp_path / "doc.pdf"
        path.write_bytes(b"%PDF-1.4")
        document = _document(storage_path=str(path))

        with patch("backend.api.documents.verify_document_download", return_value=True):
            response = asyncio_run(
                download_document(
                    "doc-1",
                    current_user=None,
                    session=Session(document),
                    ctx=None,
                    sig="sig",
                    exp=123,
                )
            )
        assert response.path == str(path)

        with patch(
            "backend.api.documents.verify_document_download", return_value=False
        ):
            with pytest.raises(HTTPException) as invalid:
                asyncio_run(
                    download_document(
                        "doc-1",
                        current_user=None,
                        session=Session(document),
                        ctx=None,
                        sig="sig",
                        exp=123,
                    )
                )
        assert invalid.value.status_code == 403

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                download_document(
                    "missing",
                    current_user=None,
                    session=Session(None),
                    ctx=None,
                    sig="sig",
                    exp=123,
                )
            )
        assert missing.value.status_code == 403

    def test_authenticated_download_requires_auth_and_tenant(self, tmp_path):
        from backend.api.documents import download_document

        with pytest.raises(HTTPException) as unauth:
            asyncio_run(
                download_document(
                    "doc-1",
                    current_user=None,
                    session=Session(),
                    ctx=None,
                    sig=None,
                    exp=None,
                )
            )
        assert unauth.value.status_code == 401

        with pytest.raises(HTTPException) as no_tenant:
            asyncio_run(
                download_document(
                    "doc-1",
                    current_user=_user(),
                    session=Session(),
                    ctx=None,
                    sig=None,
                    exp=None,
                )
            )
        assert no_tenant.value.status_code == 403

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                download_document(
                    "missing",
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                    sig=None,
                    exp=None,
                )
            )
        assert missing.value.status_code == 404

        path = tmp_path / "doc.pdf"
        path.write_bytes(b"%PDF-1.4")
        response = asyncio_run(
            download_document(
                "doc-1",
                current_user=_user(),
                session=Session(_document(storage_path=str(path))),
                ctx=_ctx(),
                sig=None,
                exp=None,
            )
        )
        assert response.path == str(path)

        with pytest.raises(HTTPException) as missing_file:
            asyncio_run(
                download_document(
                    "doc-1",
                    current_user=_user(),
                    session=Session(
                        _document(storage_path=str(tmp_path / "missing.pdf"))
                    ),
                    ctx=_ctx(),
                    sig=None,
                    exp=None,
                )
            )
        assert missing_file.value.status_code == 404

    def test_create_download_url(self, tmp_path):
        from backend.api.documents import create_document_download_url

        path = tmp_path / "doc.pdf"
        path.write_bytes(b"%PDF-1.4")
        with patch(
            "backend.api.documents.sign_document_download", return_value="signature"
        ), patch("backend.api.documents.time.time", return_value=1000):
            response = asyncio_run(
                create_document_download_url(
                    "doc-1",
                    current_user=_user(),
                    session=Session(_document(storage_path=str(path))),
                    ctx=_ctx(),
                )
            )
        assert response.url == "/documents/doc-1/download?sig=signature&exp=1300"
        assert response.expires_in == 300

        with pytest.raises(HTTPException):
            asyncio_run(
                create_document_download_url(
                    "missing",
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )
        with pytest.raises(HTTPException):
            asyncio_run(
                create_document_download_url(
                    "doc-1",
                    current_user=_user(),
                    session=Session(_document(storage_path=None)),
                    ctx=_ctx(),
                )
            )
        with pytest.raises(HTTPException):
            asyncio_run(
                create_document_download_url(
                    "doc-1",
                    current_user=_user(),
                    session=Session(
                        _document(storage_path=str(tmp_path / "missing.pdf"))
                    ),
                    ctx=_ctx(),
                )
            )
