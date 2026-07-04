"""Tests for authentication: JWT, password hashing, OAuth, dependencies."""
from __future__ import annotations
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

from backend.auth.password import hash_password, verify_password
from backend.auth.jwt import create_access_token, create_refresh_token, decode_token, get_token_subject


class TestPassword:
    """Tests for password hashing and verification."""

    def test_hash_and_verify(self):
        """Hashed password should verify correctly."""
        password = "my-secure-password-123!"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_verify_wrong_password(self):
        """Wrong password should not verify."""
        hashed = hash_password("correct-password")
        assert not verify_password("wrong-password", hashed)

    def test_hash_is_different_each_time(self):
        """Each hash of the same password should be different (due to salt)."""
        password = "test-password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2


class TestJWT:
    """Tests for JWT token creation and validation."""

    def test_create_access_token(self):
        """Access token should be a string with dots."""
        token = create_access_token("user-123")
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_create_refresh_token(self):
        """Refresh token should be a string with dots."""
        token = create_refresh_token("user-123")
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_decode_valid_token(self):
        """Valid token should decode to the correct subject."""
        user_id = "user-123"
        token = create_access_token(user_id)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "access"

    def test_decode_invalid_token(self):
        """Invalid token should return None."""
        payload = decode_token("invalid-token")
        assert payload is None

    def test_get_token_subject(self):
        """get_token_subject should return the correct subject."""
        user_id = "user-456"
        token = create_access_token(user_id)
        subject = get_token_subject(token, expected_type="access")
        assert subject == user_id

    def test_get_token_subject_wrong_type(self):
        """get_token_subject should reject wrong token types."""
        access_token = create_access_token("user-789")
        subject = get_token_subject(access_token, expected_type="refresh")
        assert subject is None

    def test_access_and_refresh_are_different(self):
        """Access and refresh tokens should be different strings."""
        user_id = "user-999"
        access = create_access_token(user_id)
        refresh = create_refresh_token(user_id)
        assert access != refresh


class TestDependencies:
    """Tests for FastAPI auth dependencies."""

    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self):
        """Missing token should raise 401."""
        from backend.auth.dependencies import get_current_user
        with pytest.raises(HTTPException):
            await get_current_user(None, MagicMock())
        # This is tested via API integration tests

    @pytest.mark.asyncio
    async def test_get_optional_user_no_token(self):
        """Missing token should return None for optional user."""
        from backend.auth.dependencies import get_optional_user
        result = await get_optional_user(None, MagicMock())
        assert result is None
