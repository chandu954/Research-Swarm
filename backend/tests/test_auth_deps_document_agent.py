"""Tests for auth dependency, document agent, answer agent, and plugin paths.

Split from backend/tests/test_coverage_critical_paths.py.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pyotp
import pytest
from backend.auth import providers


class TestMagicLinkAndMFAPaths:
    def test_magic_link_is_single_use_and_email_bound(self, monkeypatch):
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
        from backend.auth import dependencies
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

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
        from backend.auth import dependencies
        from starlette.requests import Request

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
        from backend.auth import dependencies
        from fastapi import HTTPException
        from starlette.requests import Request

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
