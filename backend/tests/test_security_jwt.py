"""Security regression suite — JWT claims, key rotation, secret validation (C3)."""

from __future__ import annotations

import os

import pytest


class TestJWTAndSecrets:
    def test_token_has_iss_aud_kid(self):
        from backend.auth.jwt import create_access_token, decode_token
        token = create_access_token("user-1")
        payload = decode_token(token)
        assert payload["iss"] == "researchswarm"
        assert payload["aud"] == "researchswarm-api"
        assert payload["kid"]

    def test_token_from_rotation_key_still_verifies(self, monkeypatch):
        import os

        from backend.auth.jwt import create_access_token, decode_token
        old = os.environ.get("JWT_SECRET_KEYS_ROTATION")
        os.environ["JWT_SECRET_KEYS_ROTATION"] = "rotated-key-0123456789abcdef0123456789abcdef"
        try:
            token = create_access_token("user-2")
            payload = decode_token(token)
            assert payload["sub"] == "user-2"
        finally:
            if old is None:
                os.environ.pop("JWT_SECRET_KEYS_ROTATION", None)
            else:
                os.environ["JWT_SECRET_KEYS_ROTATION"] = old

    def test_token_from_unknown_key_rejected(self, monkeypatch):
        from backend.auth.jwt import create_access_token, decode_token
        monkeypatch.setenv("JWT_SECRET_KEY", "signing-key-0123456789abcdef0123456789abcd")
        token = create_access_token("user-3")
        monkeypatch.setenv("JWT_SECRET_KEY", "different-secret-0123456789abcdef0123456789ab")
        assert decode_token(token) is None

    def test_bridge_secret_fails_closed(self, monkeypatch):
        import backend.core.supabase as sb
        monkeypatch.setattr(sb, "_BRIDGE_SECRET", "")
        with pytest.raises(RuntimeError):
            sb.get_bridge_secret()
        with pytest.raises(RuntimeError):
            sb._bridge_password("user-4")

    def test_production_validation_rejects_weak_secret(self, monkeypatch):
        from backend.core.config import validate_secrets
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "dev")
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "x" * 40)
        with pytest.raises(RuntimeError):
            validate_secrets()

    def test_production_validation_rejects_missing_service_role(self, monkeypatch):
        from backend.core.config import validate_secrets
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
        monkeypatch.setenv("SUPABASE_BRIDGE_SECRET", "y" * 40)
        monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
        with pytest.raises(RuntimeError):
            validate_secrets()

    def test_production_validation_passes_with_strong_secrets(self, monkeypatch):
        from backend.core.config import validate_secrets
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "k" * 40)
        monkeypatch.setenv("SUPABASE_BRIDGE_SECRET", "b" * 40)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "s" * 40)
        monkeypatch.setenv("SUPABASE_URL", "https://proj.supabase.co")
        validate_secrets()  # must not raise

    def test_production_validation_rejects_local_supabase_url(self, monkeypatch):
        from backend.core.config import validate_secrets
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "k" * 40)
        monkeypatch.setenv("SUPABASE_BRIDGE_SECRET", "b" * 40)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "s" * 40)
        monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
        with pytest.raises(RuntimeError, match="deployed Supabase project URL"):
            validate_secrets()

    def test_production_validation_rejects_missing_supabase_url(self, monkeypatch):
        from backend.core.config import validate_secrets
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", "k" * 40)
        monkeypatch.setenv("SUPABASE_BRIDGE_SECRET", "b" * 40)
        monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "s" * 40)
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="SUPABASE_URL is not set"):
            validate_secrets()
