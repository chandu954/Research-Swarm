"""Tests for document read and download routes.

Split from backend/tests/test_workspace_documents_units.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from backend.tests.test_workspace_doc_helpers import (
    NOW,
    DocumentVersion,
    Session,
    _ctx,
    _document,
    _user,
    asyncio_run,
)
from fastapi import HTTPException


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

        path = tmp_path / "doc.pdf"
        path.write_bytes(b"%PDF-1.4")
