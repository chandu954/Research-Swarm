"""Tests for PDF loader paths.

Split from backend/tests/test_coverage_critical_paths.py.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest


class _FakePage:
    def __init__(self, text: str):
        self.text = text

    def get_text(self):
        return self.text


class _FakeDocument:
    metadata = {"title": "Title", "author": "Author", "subject": "Subject"}

    def __init__(self, pages):
        self.pages = pages
        self.closed = False

    def __len__(self):
        return len(self.pages)

    def load_page(self, index):
        return self.pages[index]

    def close(self):
        self.closed = True


class TestPDFLoaderPaths:
    def test_load_pdf_extracts_text_and_page_metadata(self, tmp_path, monkeypatch):
        from backend.tools import pdf_loader

        path = tmp_path / "sample.pdf"
        path.write_bytes(b"pdf")
        document = _FakeDocument([_FakePage("first"), _FakePage("second")])
        monkeypatch.setattr(
            pdf_loader, "fitz", SimpleNamespace(open=Mock(return_value=document))
        )

        text, pages = pdf_loader.load_pdf(str(path))

        assert text == "first\n\nsecond\n\n"
        assert pages == [
            {"page_number": 1, "text": "first", "char_count": 5},
            {"page_number": 2, "text": "second", "char_count": 6},
        ]
        assert document.closed

    def test_load_pdf_reports_missing_file_and_unavailable_dependency(
        self, tmp_path, monkeypatch
    ):
        from backend.tools import pdf_loader

        with pytest.raises(FileNotFoundError):
            pdf_loader.load_pdf(str(tmp_path / "missing.pdf"))

        path = tmp_path / "sample.pdf"
        path.touch()
        monkeypatch.setattr(pdf_loader, "fitz", None)
        with pytest.raises(pdf_loader.PDFLoadError, match="not installed"):
            pdf_loader.load_pdf(str(path))
        with pytest.raises(pdf_loader.PDFLoadError, match="not installed"):
            pdf_loader.get_pdf_metadata(str(path))
        with pytest.raises(pdf_loader.PDFLoadError, match="not installed"):
            pdf_loader.extract_page_text(str(path), [1])

    def test_metadata_and_selected_pages_filter_out_of_range(
        self, tmp_path, monkeypatch
    ):
        from backend.tools import pdf_loader

        path = tmp_path / "sample.pdf"
        path.write_bytes(b"pdf bytes")
        document = _FakeDocument([_FakePage("one"), _FakePage("two")])
        monkeypatch.setattr(
            pdf_loader, "fitz", SimpleNamespace(open=Mock(return_value=document))
        )

        metadata = pdf_loader.get_pdf_metadata(str(path))
        pages = pdf_loader.extract_page_text(str(path), [2, 0, 1, 3])

        assert metadata == {
            "title": "Title",
            "author": "Author",
            "subject": "Subject",
            "page_count": 2,
            "file_size": 9,
            "filename": "sample.pdf",
        }
        assert pages == [
            {"page_number": 2, "text": "two"},
            {"page_number": 1, "text": "one"},
        ]
        assert document.closed

    def test_pdf_open_errors_are_wrapped(self, tmp_path, monkeypatch):
        from backend.tools import pdf_loader

        path = tmp_path / "broken.pdf"
        path.touch()
        monkeypatch.setattr(
            pdf_loader,
            "fitz",
            SimpleNamespace(open=Mock(side_effect=ValueError("bad pdf"))),
        )
        with pytest.raises(pdf_loader.PDFLoadError, match="bad pdf"):
            pdf_loader.load_pdf(str(path))
        with pytest.raises(pdf_loader.PDFLoadError, match="metadata"):
            pdf_loader.get_pdf_metadata(str(path))
        with pytest.raises(pdf_loader.PDFLoadError, match="extract pages"):
            pdf_loader.extract_page_text(str(path), [1])
