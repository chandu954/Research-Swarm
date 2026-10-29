"""Tests for browser and code execution paths.

Split from backend/tests/test_coverage_critical_paths.py.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock


class _Response:
    def __init__(self, text="", payload=None, error=None):
        self.text = text
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error


class _HTTPClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.headers = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, _url, headers=None):
        self.headers = headers
        if self.error:
            raise self.error
        return self.response


class TestBrowserPaths:
    def test_read_page_strips_noise_and_prefers_article(self, monkeypatch):
        from backend.tools import browser

        client = _HTTPClient(
            _Response(
                "<html><head><title> Report </title></head><body>"
                "<nav>skip nav</nav><article><h1>Findings</h1><p>Useful text</p>"
                "<script>skip script</script></article></body></html>"
            )
        )
        monkeypatch.setattr(
            browser, "httpx", SimpleNamespace(Client=lambda **_: client)
        )

        result = browser.read_page("https://example.test/report", max_length=30)

        assert result == {
            "url": "https://example.test/report",
            "title": "Report",
            "text": "Findings\nUseful text",
            "snippet": "Findings\nUseful text",
            "success": True,
        }
        assert "User-Agent" in client.headers

    def test_read_page_returns_fetch_error(self, monkeypatch):
        from backend.tools import browser

        monkeypatch.setattr(
            browser,
            "httpx",
            SimpleNamespace(
                Client=lambda **_: _HTTPClient(error=TimeoutError("timed out"))
            ),
        )
        result = browser.read_page("https://example.test")
        assert result["success"] is False
        assert result["error"] == "timed out"

    def test_read_page_falls_back_when_html_parser_is_missing(self, monkeypatch):
        from backend.tools import browser

        monkeypatch.setattr(browser, "BeautifulSoup", None)
        monkeypatch.setattr(
            browser,
            "httpx",
            SimpleNamespace(Client=lambda **_: _HTTPClient(_Response("<p>hello</p>"))),
        )
        result = browser.read_page("https://example.test", max_length=5)
        assert result["text"] == "<p>he"
        assert result["snippet"] == "<p>hello</p>"

    def test_extract_links_resolves_relative_urls_and_limits_results(self, monkeypatch):
        from backend.tools import browser

        html = '<a href="/about"> About </a><a href="https://other.test">Other</a>'
        monkeypatch.setattr(
            browser,
            "httpx",
            SimpleNamespace(Client=lambda **_: _HTTPClient(_Response(html))),
        )
        assert browser.extract_links("https://example.test/path", max_links=1) == [
            {"url": "https://example.test/about", "text": "About"}
        ]
        assert browser.extract_links("https://example.test", max_links=2)[1] == {
            "url": "https://other.test",
            "text": "Other",
        }

    def test_extract_links_handles_missing_dependencies_and_request_errors(
        self, monkeypatch
    ):
        from backend.tools import browser

        monkeypatch.setattr(browser, "BeautifulSoup", None)
        assert browser.extract_links("https://example.test") == []
        monkeypatch.setattr(browser, "BeautifulSoup", object())
        monkeypatch.setattr(
            browser,
            "httpx",
            SimpleNamespace(Client=lambda **_: _HTTPClient(error=OSError("offline"))),
        )
        assert browser.extract_links("https://example.test") == []


class TestCodeExecutionPaths:
    def test_python_success_failure_and_output_truncation(self):
        from backend.tools.code_executor import execute_python

        success = execute_python("print('hello')")
        failure = execute_python("raise SystemExit(3)")
        large = execute_python("print('x' * 60000)")

        assert success["success"] and success["stdout"] == "hello\n"
        assert failure["success"] is False and failure["return_code"] == 3
        assert len(large["stdout"]) == 50_000

    def test_python_blocks_dangerous_code_and_handles_timeout(self, monkeypatch):
        from backend.tools import code_executor

        blocked = code_executor.execute_python("import os")
        assert blocked["success"] is False
        assert "blocked patterns" in blocked["stderr"]

        monkeypatch.setattr(
            code_executor.subprocess,
            "run",
            Mock(side_effect=code_executor.subprocess.TimeoutExpired("python", 1)),
        )
        timed_out = code_executor.execute_python("print('hello')", timeout=1)
        assert timed_out["success"] is False
        assert "timed out" in timed_out["stderr"]

    def test_shell_success_failure_and_timeout(self, monkeypatch):
        from backend.tools import code_executor

        assert code_executor.execute_shell("printf hello")["stdout"] == "hello"
        failed = code_executor.execute_shell("exit 4")
        assert failed["success"] is False and failed["return_code"] == 4

        monkeypatch.setattr(
            code_executor.subprocess,
            "run",
            Mock(side_effect=code_executor.subprocess.TimeoutExpired("sh", 1)),
        )
        assert (
            "timed out" in code_executor.execute_shell("sleep 1", timeout=1)["stderr"]
        )
