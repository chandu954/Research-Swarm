"""Tests for document upload route.

Split from backend/tests/test_workspace_documents_units.py.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from backend.core.ratelimit import limiter
from backend.tests.test_workspace_doc_helpers import (
    Session,
    _ctx,
    _user,
    asyncio_run,
)
from fastapi import HTTPException


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
