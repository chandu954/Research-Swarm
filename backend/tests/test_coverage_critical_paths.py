"""Focused regression coverage for file, web, execution, and auth helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
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


class TestMagicLinkAndMFAPaths:
    def test_magic_link_is_single_use_and_email_bound(self, monkeypatch):
        from backend.auth import providers

        monkeypatch.setattr(providers.config, "app_url", "https://app.example")
        url, token, expires = providers.create_magic_link("user@example.test")

        assert url.startswith("https://app.example/auth/magic?")
        assert expires > datetime.now(timezone.utc)
        assert providers.verify_magic_token(token, "other@example.test") is False
        assert providers.verify_magic_token(token, "user@example.test") is True
        assert providers.verify_magic_token(token, "user@example.test") is False
        assert providers.verify_magic_token("missing", "user@example.test") is False

    def test_expired_magic_link_is_removed(self):
        from backend.auth import providers

        _, token, _ = providers.create_magic_link("expired@example.test")
        providers._magic_link_store[token]["expires_at"] = datetime.now(
            timezone.utc
        ) - timedelta(seconds=1)
        assert providers.verify_magic_token(token, "expired@example.test") is False
        assert token not in providers._magic_link_store

    def test_mfa_secret_code_and_recovery_codes(self):
        import pyotp
        from backend.auth import providers

        secret = providers.generate_mfa_secret()
        code = pyotp.TOTP(secret).now()
        assert providers.verify_mfa_code(secret, code) is True
        assert providers.verify_mfa_code(secret, "000000") is False
        assert "ResearchSwarm" in providers.generate_mfa_qr_code(
            secret, "user@example.test"
        )
        codes = providers.generate_recovery_codes(3)
        assert len(codes) == 3
        assert all(len(code) == 8 for code in codes)

    def test_google_oauth_exchange_and_userinfo_failures_are_returned_as_none(
        self, monkeypatch
    ):
        from backend.auth import providers

        class AsyncResponse:
            def __init__(self, payload=None, error=None):
                self.payload = payload or {}
                self.error = error

            def raise_for_status(self):
                if self.error:
                    raise self.error

            def json(self):
                return self.payload

        class AsyncClient:
            def __init__(self, response):
                self.response = response

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            async def post(self, *_args, **_kwargs):
                return self.response

            async def get(self, *_args, **_kwargs):
                return self.response

        response = AsyncResponse({"access_token": "test-access-token"})
        monkeypatch.setattr(
            providers,
            "httpx",
            SimpleNamespace(AsyncClient=lambda **_: AsyncClient(response)),
        )
        assert asyncio.run(providers.exchange_google_code("test-code")) == {
            "access_token": "test-access-token"
        }
        assert asyncio.run(providers.get_google_userinfo("test-access-token")) == {
            "access_token": "test-access-token"
        }

        failure = AsyncResponse(error=OSError("offline"))
        monkeypatch.setattr(
            providers,
            "httpx",
            SimpleNamespace(AsyncClient=lambda **_: AsyncClient(failure)),
        )
        assert asyncio.run(providers.exchange_google_code("test-code")) is None
        assert asyncio.run(providers.get_google_userinfo("test-access-token")) is None


class TestAuthenticationDependencyPaths:
    def test_bearer_auth_resolves_user_and_rejects_invalid_or_missing_users(
        self, monkeypatch
    ):
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials
        from backend.auth import dependencies

        user = SimpleNamespace(id="user-id")

        class Result:
            def scalar_one_or_none(self):
                return user

        class Session:
            async def execute(self, _query):
                return Result()

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
        monkeypatch.setattr(
            dependencies, "get_token_subject", lambda *_args, **_kwargs: "user-id"
        )
        assert (
            asyncio.run(dependencies.get_current_user(credentials, Session())) is user
        )

        monkeypatch.setattr(
            dependencies, "get_token_subject", lambda *_args, **_kwargs: None
        )
        with pytest.raises(HTTPException) as invalid:
            asyncio.run(dependencies.get_current_user(credentials, Session()))
        assert invalid.value.status_code == 401
        assert (
            asyncio.run(dependencies.get_optional_user(credentials, Session())) is None
        )

    def test_api_key_auth_hashes_key_updates_usage_and_resolves_user(self, monkeypatch):
        from starlette.requests import Request
        from backend.auth import dependencies

        api_key = SimpleNamespace(user_id="user-id", last_used_at=None)
        user = SimpleNamespace(id="user-id")

        class Result:
            def __init__(self, value):
                self.value = value

            def scalar_one_or_none(self):
                return self.value

        class Session:
            def __init__(self):
                self.results = iter([Result(api_key), Result(user)])

            async def execute(self, _query):
                return next(self.results)

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [(b"x-api-key", b"test-api-key")],
                "query_string": b"",
                "server": ("test", 80),
                "scheme": "http",
            }
        )
        session = Session()
        result = asyncio.run(dependencies.get_current_user(None, session, request))

        assert result is user
        assert api_key.last_used_at is not None

    def test_unrecognized_api_key_falls_back_to_unauthorized(self):
        from fastapi import HTTPException
        from starlette.requests import Request
        from backend.auth import dependencies

        class Result:
            def scalar_one_or_none(self):
                return None

        class Session:
            async def execute(self, _query):
                return Result()

        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [(b"x-api-key", b"unknown")],
                "query_string": b"",
                "server": ("test", 80),
                "scheme": "http",
            }
        )
        with pytest.raises(HTTPException) as missing:
            asyncio.run(dependencies.get_current_user(None, Session(), request))
        assert missing.value.status_code == 401


class TestDocumentAgentPaths:
    @staticmethod
    def _agent(embedding_provider=None, llm=None):
        from backend.agents.document_agent import DocumentAgent

        agent = DocumentAgent.__new__(DocumentAgent)
        agent._embedding_provider = embedding_provider
        agent.llm = llm or SimpleNamespace(generate=Mock(return_value="0.8"))
        return agent

    def test_chunking_handles_empty_short_and_overlapping_text(self):
        agent = self._agent()
        assert agent._chunk_text("", "doc") == []

        short = agent._chunk_text("one two three", "doc")
        assert short[0]["chunk_id"] == "doc_0"
        assert short[0]["metadata"]["word_count"] == 3
        assert short[0]["metadata"]["source"] == "pdf"

        words = [f"w{i}" for i in range(1900)]
        chunks = agent._chunk_text(" ".join(words), "long")
        assert len(chunks) == 3
        assert chunks[0]["content"].split()[-200:] == chunks[1]["content"].split()[:200]
        assert chunks[-1]["metadata"]["chunk_index"] == 2

    def test_ingest_pdf_chunks_embeds_and_stores(self, tmp_path):
        path = tmp_path / "report.pdf"
        path.write_bytes(b"test")
        stored = {}

        class Registry:
            def execute(self, name, **kwargs):
                if name == "load_pdf":
                    return "evidence from report", [
                        {"page_number": 1, "text": "evidence"}
                    ]
                stored.update(kwargs)

        provider = SimpleNamespace(embed=Mock(return_value=[[0.1, 0.2]]))
        agent = self._agent(provider)
        agent.registry = Registry()

        result = agent.ingest_pdf(str(path))

        assert result == {"doc_id": "report", "filename": "report.pdf", "chunks": 1}
        assert stored["ids"] == ["report_0"]
        assert stored["embeddings"] == [[0.1, 0.2]]
        assert stored["metadatas"][0]["doc_id"] == "report"

    def test_embedding_helpers_use_provider_or_zero_vectors(self):
        provider = SimpleNamespace(
            embed=Mock(return_value=None), embed_query=Mock(return_value=[1.0, 0.0])
        )
        agent = self._agent(provider)
        fallback = agent._create_embeddings(["a", "b"])
        assert len(fallback) == 2 and len(fallback[0]) == 768
        assert agent._create_embedding("query") == [1.0, 0.0]

        no_provider = self._agent()
        assert no_provider._create_embeddings(["a"])[0] == [0.0] * 768
        assert no_provider._create_embedding("query") is None

    def test_retrieve_handles_empty_input_missing_embedding_and_missing_store(
        self, monkeypatch
    ):
        from backend.agents import document_agent

        agent = self._agent()
        assert agent.retrieve("") == []
        assert agent.retrieve("query") == []

        agent._embedding_provider = SimpleNamespace(
            embed_query=Mock(return_value=[1.0])
        )
        monkeypatch.setattr(
            document_agent,
            "get_plugin_registry",
            lambda: SimpleNamespace(get_vector_db=lambda: None),
        )
        assert agent.retrieve("query") == []

    def test_retrieve_fuses_results_and_reranks(self, monkeypatch):
        from backend.agents import document_agent

        class VectorStore:
            async def query(self, **kwargs):
                assert kwargs["top_k"] == 4
                return [{"content": "evidence", "score": 0.5}]

        agent = self._agent(SimpleNamespace(embed_query=Mock(return_value=[1.0])))
        monkeypatch.setattr(
            document_agent,
            "get_plugin_registry",
            lambda: SimpleNamespace(get_vector_db=lambda: VectorStore()),
        )
        monkeypatch.setattr(
            "backend.search.hybrid.hybrid_rerank",
            lambda _query, results, **_kwargs: results,
        )
        ranked = agent.retrieve("question", top_k=2)
        assert ranked[0]["rank"] == 1
        assert ranked[0]["relevance_score"] == 0.8

    def test_relevance_clamps_scores_and_falls_back_to_cosine(self, monkeypatch):
        monkeypatch.setenv("RELEVANCE_MODEL", "test-model")
        agent = self._agent(llm=SimpleNamespace(generate=Mock(return_value="1.5")))
        assert agent._compute_relevance("q", "chunk") == 1.0

        agent.llm.generate.return_value = "not a number"
        agent._embedding_provider = SimpleNamespace(
            embed_query=Mock(side_effect=[[1.0, 0.0], [0.0, 1.0]])
        )
        assert agent._compute_relevance("q", "chunk") == 0.0

        agent.llm.generate.side_effect = RuntimeError("model unavailable")
        agent._embedding_provider.embed_query.side_effect = [[1.0, 0.0], [1.0, 0.0]]
        assert agent._compute_relevance("q", "chunk") == pytest.approx(1.0)

        agent._embedding_provider.embed_query.side_effect = RuntimeError(
            "embedding unavailable"
        )
        assert agent._compute_relevance("q", "chunk") == 0.0

    def test_cosine_similarity_handles_invalid_vectors(self):
        from backend.agents.document_agent import DocumentAgent

        assert DocumentAgent._cosine_similarity([], [1.0]) == 0.0
        assert DocumentAgent._cosine_similarity([1.0], [1.0, 2.0]) == 0.0
        assert DocumentAgent._cosine_similarity([0.0], [1.0]) == 0.0
        assert DocumentAgent._cosine_similarity(
            [1.0, 0.0], [1.0, 0.0]
        ) == pytest.approx(1.0)


class TestAnswerAgentPaths:
    @staticmethod
    def _agent(generate):
        from backend.agents.answer_agent import AnswerAgent

        agent = AnswerAgent.__new__(AnswerAgent)
        agent.llm = SimpleNamespace(generate=generate)
        return agent

    def test_no_evidence_returns_explanation_without_calling_llm(self):
        agent = self._agent(Mock())
        from backend.agents.answer_agent import AnswerRequest

        response = agent.generate(AnswerRequest(question="What happened?"))
        assert response.mode == "no_evidence"
        assert response.sources == []
        assert response.evidence_summary["source_count"] == 0
        assert "No relevant web sources" in response.answer
        agent.llm.generate.assert_not_called()

    def test_evidence_generation_builds_citations_and_prompt_context(self, monkeypatch):
        from backend.agents import answer_agent

        monkeypatch.setattr(answer_agent, "resolve_model", lambda _agent: "model-test")
        llm = Mock(return_value="  Cited answer  ")
        agent = self._agent(llm)
        request = answer_agent.AnswerRequest(
            question="Compare these findings",
            web_results=[
                {
                    "title": "Web source",
                    "url": "https://example.test",
                    "snippet": "Web evidence",
                    "_provider": "search-a",
                    "hybrid_score": 0.9,
                    "source_diversity_score": 0.7,
                }
            ],
            document_chunks=[
                {
                    "content": "Document evidence",
                    "metadata": {"doc_id": "doc-1", "page_number": 4},
                    "score": 0.8,
                }
            ],
            conversation_history=[{"role": "assistant", "content": "Prior context"}],
        )

        response = agent.generate(request)

        assert response.mode == "normal"
        assert response.answer == "Cited answer"
        assert [source.source_type for source in response.sources] == [
            "web",
            "document",
        ]
        assert response.sources[0].provider == "search-a"
        assert response.sources[1].title == "doc-1"
        assert response.evidence_summary["source_count"] == 2
        prompt = llm.call_args.kwargs["prompt"]
        assert "Prior context" in prompt
        assert "Web evidence" in prompt
        assert "Page 4" in prompt

    def test_empty_or_failed_llm_response_uses_fallback(self, monkeypatch):
        from backend.agents import answer_agent

        monkeypatch.setattr(answer_agent, "resolve_model", lambda _agent: "model-test")
        request = answer_agent.AnswerRequest(
            question="Summarize",
            web_results=[{"title": "Source", "snippet": "Finding"}],
        )

        empty = self._agent(Mock(return_value="  ")).generate(request)
        assert empty.mode == "fallback"
        assert "Finding" in empty.answer

        failed = self._agent(
            Mock(side_effect=RuntimeError("provider offline"))
        ).generate(request)
        assert failed.mode == "fallback"
        assert "Fallback mode" in failed.answer


class _PluginResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _PluginClient:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.headers = None

    def get(self, path, **kwargs):
        self.calls.append(("GET", path, kwargs))
        return _PluginResponse(self.routes[path])

    def post(self, path, **kwargs):
        self.calls.append(("POST", path, kwargs))
        return _PluginResponse(self.routes[path])


def _install_plugin_client(monkeypatch, module, client):
    monkeypatch.setattr(
        module,
        "httpx",
        SimpleNamespace(
            Client=lambda **kwargs: _capture_plugin_headers(client, kwargs)
        ),
    )


def _capture_plugin_headers(client, kwargs):
    client.headers = kwargs.get("headers", {})
    return client


class TestExternalPluginBehaviors:
    def test_github_actions_transform_results_and_require_initialization(
        self, monkeypatch
    ):
        from backend.plugins import github

        plugin = github.GitHubPlugin({"token": "test-token"})
        with pytest.raises(RuntimeError, match="not initialized"):
            plugin._search_issues("bug")

        client = _PluginClient(
            {
                "/search/issues": {
                    "items": [
                        {
                            "title": "Issue",
                            "html_url": "https://github.test/i/1",
                            "state": "open",
                            "repository_url": "https://api.github.test/repos/acme/project",
                            "created_at": "2024-01-01",
                            "body": "details",
                        }
                    ]
                },
                "/search/repositories": {
                    "items": [
                        {
                            "full_name": "acme/project",
                            "html_url": "https://github.test/acme/project",
                            "description": "repo",
                            "stargazers_count": 5,
                            "language": "Python",
                            "topics": ["ai"],
                        }
                    ]
                },
                "/repos/acme/project": {
                    "full_name": "acme/project",
                    "description": "repo",
                    "stargazers_count": 5,
                    "forks_count": 2,
                    "language": "Python",
                    "topics": [],
                    "html_url": "https://github.test/acme/project",
                },
                "/repos/acme/project/issues": [
                    {
                        "title": "Issue",
                        "html_url": "https://github.test/i/1",
                        "state": "open",
                        "created_at": "2024-01-01",
                        "labels": [{"name": "bug"}],
                    }
                ],
                "/repos/acme/project/contents/README.md": {
                    "content": "aGVsbG8=",
                    "encoding": "base64",
                },
            }
        )
        _install_plugin_client(monkeypatch, github, client)
        asyncio.run(plugin.initialize())

        assert client.headers["Authorization"] == "Bearer test-token"
        assert plugin._search_issues("bug")[0]["repo"] == "project"
        assert plugin._search_repos("ai")[0]["topics"] == ["ai"]
        assert plugin._get_repo("acme/project")["forks"] == 2
        assert plugin._list_issues("acme/project")[0]["labels"] == ["bug"]
        assert plugin._get_file("acme/project", "README.md") == "hello"
        assert (
            asyncio.run(plugin.execute("search_issues", query="bug"))[0]["title"]
            == "Issue"
        )
        with pytest.raises(ValueError, match="Unknown GitHub action"):
            asyncio.run(plugin.execute("unknown"))

    def test_notion_actions_and_property_value_shapes(self, monkeypatch):
        from backend.plugins import notion

        plugin = notion.NotionPlugin({"token": "notion-token"})
        with pytest.raises(RuntimeError, match="not initialized"):
            plugin._search("query")
        client = _PluginClient(
            {
                "/databases/db/query": {
                    "results": [
                        {
                            "id": "page-1",
                            "url": "https://notion.test/p/1",
                            "created_time": "today",
                            "properties": {
                                "title": {
                                    "type": "title",
                                    "title": [{"plain_text": "Title"}],
                                },
                                "status": {
                                    "type": "status",
                                    "status": {"name": "Done"},
                                },
                                "tags": {
                                    "type": "multi",
                                    "multi": [{"plain_text": "a"}, {"plain_text": "b"}],
                                },
                                "count": {"type": "number", "number": 3},
                                "empty": {},
                            },
                        }
                    ]
                },
                "/pages/page-1": {
                    "id": "page-1",
                    "url": "https://notion.test/p/1",
                    "properties": {},
                },
                "/search": {
                    "results": [
                        {
                            "id": "page-1",
                            "object": "page",
                            "url": "https://notion.test/p/1",
                        }
                    ]
                },
            }
        )
        _install_plugin_client(monkeypatch, notion, client)
        asyncio.run(plugin.initialize())

        result = plugin._query_database("db", {"property": "Status"})[0]
        assert result["properties"] == {
            "title": "Title",
            "status": "Done",
            "tags": "a b",
            "count": 3,
            "empty": None,
        }
        assert client.calls[0][2]["json"] == {"filter": {"property": "Status"}}
        assert plugin._get_page("page-1")["id"] == "page-1"
        assert plugin._search("query")[0]["type"] == "page"
        assert (
            notion._notion_prop_value({"type": "unknown", "unknown": {"id": "x"}})
            == "{'id': 'x'}"
        )
        with pytest.raises(ValueError, match="Unknown Notion action"):
            asyncio.run(plugin.execute("unknown"))

    def test_slack_results_and_api_error_classification(self, monkeypatch):
        from backend.plugins import slack

        plugin = slack.SlackPlugin({"token": "slack-token"})
        with pytest.raises(RuntimeError, match="not initialized"):
            plugin._list_channels()
        client = _PluginClient(
            {
                "/search.messages": {
                    "ok": True,
                    "messages": {
                        "matches": [
                            {
                                "text": "hello",
                                "channel": {"name": "general"},
                                "username": "user",
                                "ts": "1",
                                "permalink": "https://slack.test/1",
                            }
                        ]
                    },
                },
                "/conversations.list": {
                    "ok": True,
                    "channels": [
                        {
                            "id": "c1",
                            "name": "general",
                            "topic": {"value": "work"},
                            "member_count": 4,
                        }
                    ],
                },
                "/conversations.history": {
                    "ok": True,
                    "messages": [{"text": "hello", "user": "u1", "ts": "1"}],
                },
            }
        )
        _install_plugin_client(monkeypatch, slack, client)
        asyncio.run(plugin.initialize())

        assert client.headers["Authorization"] == "Bearer slack-token"
        assert plugin._search_messages("hello")[0]["channel"] == "general"
        assert plugin._list_channels()[0]["member_count"] == 4
        assert plugin._get_channel_history("c1")[0]["text"] == "hello"
        assert (
            asyncio.run(plugin.execute("search_messages", query="hello"))[0]["user"]
            == "user"
        )
        with pytest.raises(ValueError, match="Unknown Slack action"):
            asyncio.run(plugin.execute("unknown"))

        client.routes["/search.messages"] = {"ok": False, "error": "invalid_auth"}
        with pytest.raises(RuntimeError, match="invalid_auth"):
            plugin._search_messages("hello")
