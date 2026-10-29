"""Production-hardening regression suite.

Locks in the P0/P1 production-readiness fixes:
- P0-4: signed PDF download URLs (tenant-bound, short-lived, never a JWT)
- P1-5: billing usage derives the org from authenticated membership
- P1-6: plugin configure/execute honor the declared contract

These tests are permanent: they must keep passing so the vulnerability
classes cannot silently reappear.
"""
from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock

import pytest

# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_app():
    import re

    from backend.db.session import _engine

    url = os.environ.get("DATABASE_URL", "")
    m = re.match(r"sqlite\+aiosqlite:///(.*)", url)
    if m:
        db_path = os.path.abspath(m.group(1))
        if os.path.exists(db_path):
            os.remove(db_path)
    _engine.sync_engine.dispose()

    from backend.api.main import app
    app.state.limiter.enabled = False
    app.state.graph = AsyncMock()
    app.state.graph.ainvoke.return_value = {
        "status": "completed", "answer": "test answer", "sources": [],
        "logs": [], "plan": [], "errors": [], "pdf_paths": [],
    }
    return app


@pytest.fixture(scope="module")
def client(api_app):
    from fastapi.testclient import TestClient
    with TestClient(api_app) as c:
        yield c


def register(client, email: str, name: str = "Test User", password: str = "test-password-123"):
    resp = client.post("/auth/register", json={
        "email": email, "password": password, "name": name,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def auth_headers(tokens: dict, org_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    if org_id:
        headers["X-Organization-Id"] = org_id
    return headers


def my_orgs(client, tokens) -> list[dict]:
    resp = client.get("/organizations", headers=auth_headers(tokens))
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture(scope="module")
def users(client):
    alice = register(client, "hardening-alice@example.com", "Alice")
    bob = register(client, "hardening-bob@example.com", "Bob")
    alice_org = my_orgs(client, alice)[0]
    bob_org = my_orgs(client, bob)[0]
    return {"alice": alice, "bob": bob, "alice_org": alice_org, "bob_org": bob_org}


# ═════════════════════════════════════════════════════════════════
# P0-4 — Signed document download URLs
# ═════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def signed_doc(client, users):
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    resp = client.post(
        "/upload",
        headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        files={"file": ("signed.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["document_id"]


class TestSignedDownload:
    def test_issue_signed_url(self, client, users, signed_doc):
        resp = client.post(
            f"/documents/{signed_doc}/download-url",
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "sig=" in body["url"]
        assert "exp=" in body["url"]
        assert body["expires_in"] == 300

    def test_signed_url_downloads_without_bearer(self, client, users, signed_doc):
        issued = client.post(
            f"/documents/{signed_doc}/download-url",
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        ).json()
        resp = client.get(issued["url"])
        assert resp.status_code == 200, resp.text
        assert resp.content.startswith(b"%PDF")

    def test_plain_download_without_auth_rejected(self, client, signed_doc):
        resp = client.get(f"/documents/{signed_doc}/download")
        assert resp.status_code == 401

    def test_tampered_signature_rejected(self, client, users, signed_doc):
        issued = client.post(
            f"/documents/{signed_doc}/download-url",
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        ).json()
        url = issued["url"]
        sig = url.split("sig=")[1].split("&")[0]
        forged_sig = ("deadbeef0" * 8)[: len(sig)]
        forged_url = url.replace(f"sig={sig}", f"sig={forged_sig}")
        resp = client.get(forged_url)
        assert resp.status_code == 403

    def test_expired_signature_rejected(self, client, users, signed_doc):
        from backend.api.main import _sign_document_download
        old_exp = int(time.time()) - 60
        sig = _sign_document_download(signed_doc, users["alice_org"]["id"], old_exp)
        resp = client.get(
            f"/documents/{signed_doc}/download?sig={sig}&exp={old_exp}"
        )
        assert resp.status_code == 403

    def test_signature_not_reusable_across_documents(self, client, users):
        """A signature minted for one document must not open another."""
        from backend.api.main import _sign_document_download
        expires = int(time.time()) + 300
        # Second document owned by the same org — sig from doc A must fail on B.
        pdf = b"%PDF-1.4\n%%EOF"
        upload = client.post(
            "/upload",
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
            files={"file": ("other.pdf", pdf, "application/pdf")},
        ).json()["document_id"]
        sig_a = _sign_document_download("doc-a", users["alice_org"]["id"], expires)
        resp = client.get(
            f"/documents/{upload}/download?sig={sig_a}&exp={expires}"
        )
        assert resp.status_code == 403

    def test_download_url_for_foreign_doc_rejected(self, client, users, signed_doc):
        resp = client.post(
            f"/documents/{signed_doc}/download-url",
            headers=auth_headers(users["bob"], users["bob_org"]["id"]),
        )
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════
# P1-5 — Billing usage is tenant-scoped
# ═════════════════════════════════════════════════════════════════

class TestBillingUsageTenantScoping:
    def test_own_org_accepted(self, client, users):
        resp = client.get(
            "/billing/usage",
            params={"organization_id": users["alice_org"]["id"]},
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        )
        assert resp.status_code == 200, resp.text
        assert "tokens_in" in resp.json()

    def test_missing_org_uses_authenticated_tenant(self, client, users):
        """Without an org param the endpoint must not fail — it scopes to
        the caller's own membership."""
        resp = client.get("/billing/usage", headers=auth_headers(users["alice"]))
        assert resp.status_code == 200, resp.text

    def test_foreign_org_rejected(self, client, users):
        resp = client.get(
            "/billing/usage",
            params={"organization_id": users["bob_org"]["id"]},
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        )
        assert resp.status_code == 403

    def test_malformed_org_rejected(self, client, users):
        resp = client.get(
            "/billing/usage",
            params={"organization_id": "not-a-real-org-id"},
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        )
        # Tenant resolution fails before any data is read.
        assert resp.status_code in (403, 404)

    def test_requires_auth(self, client):
        resp = client.get("/billing/usage")
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════
# P1-6 — Plugin configure/execute honor the declared contract
# ═════════════════════════════════════════════════════════════════

class _ContractPlugin:
    """Minimal plugin with a declared config schema + declared actions."""

    class _Spec:
        name = "audit_contract_plugin"
        description = "Audit fixture plugin"
        version = "1.0.0"
        tags = ["ping"]
        config_schema = {"api_key": {"type": "string", "required": True}}

    spec = _Spec()

    def __init__(self):
        self._config = {}

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs):
        if action == "ping":
            return "pong"
        raise ValueError(f"Unknown action: {action}")

    def is_configured(self) -> bool:
        return "api_key" in self._config

    @property
    def config(self) -> dict:
        return self._config


@pytest.fixture(scope="module")
def contract_plugin():
    from backend.core.registry import get_plugin_registry
    registry = get_plugin_registry()
    plugin = _ContractPlugin()
    registry.register(plugin, "external")
    yield plugin
    if plugin.spec.name in registry._plugins:
        del registry._plugins[plugin.spec.name]
    bucket = registry._by_type.get("external", {})
    if "audit_contract_plugin" in bucket:
        del bucket["audit_contract_plugin"]


class TestPluginContract:
    def test_configure_requires_auth(self, client):
        resp = client.post("/plugins/audit_contract_plugin/configure", json={
            "name": "audit_contract_plugin", "config": {"api_key": "x"},
        })
        assert resp.status_code == 401

    def test_execute_requires_auth(self, client):
        resp = client.post("/plugins/audit_contract_plugin/execute?action=ping", json={})
        assert resp.status_code == 401

    def test_configure_unknown_plugin(self, client, users):
        resp = client.post("/plugins/does-not-exist/configure", json={
            "name": "does-not-exist", "config": {},
        }, headers=auth_headers(users["alice"], users["alice_org"]["id"]))
        assert resp.status_code == 404

    def test_execute_unknown_plugin(self, client, users):
        resp = client.post(
            "/plugins/does-not-exist/execute?action=ping",
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        )
        assert resp.status_code == 404

    def test_configure_rejects_undeclared_keys(self, client, users, contract_plugin):
        resp = client.post("/plugins/audit_contract_plugin/configure", json={
            "name": "audit_contract_plugin",
            "config": {"token": "sneaky", "api_key": "x"},
        }, headers=auth_headers(users["alice"], users["alice_org"]["id"]))
        assert resp.status_code == 422
        assert "token" in resp.text

    def test_configure_valid_keys(self, client, users, contract_plugin):
        resp = client.post("/plugins/audit_contract_plugin/configure", json={
            "name": "audit_contract_plugin",
            "config": {"api_key": "secret-value"},
        }, headers=auth_headers(users["alice"], users["alice_org"]["id"]))
        assert resp.status_code == 200, resp.text

    def test_execute_unconfigured_plugin_rejected(self, client, users):
        """Before configuration, execution fails closed."""
        unconfigured = _ContractPlugin()
        unconfigured.spec.name = "audit_contract_unconfigured"
        from backend.core.registry import get_plugin_registry
        registry = get_plugin_registry()
        registry.register(unconfigured, "external")
        try:
            resp = client.post(
                "/plugins/audit_contract_unconfigured/execute?action=ping",
                headers=auth_headers(users["bob"], users["bob_org"]["id"]),
            )
            assert resp.status_code == 400
        finally:
            if unconfigured.spec.name in registry._plugins:
                del registry._plugins[unconfigured.spec.name]
            bucket = registry._by_type.get("external", {})
            if unconfigured.spec.name in bucket:
                del bucket[unconfigured.spec.name]

    def test_execute_undeclared_action_rejected(self, client, users, contract_plugin):
        resp = client.post(
            "/plugins/audit_contract_plugin/execute?action=delete_everything",
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        )
        assert resp.status_code == 400

    def test_execute_declared_action_works(self, client, users, contract_plugin):
        resp = client.post(
            "/plugins/audit_contract_plugin/execute?action=ping",
            json={"extra": "arg"},
            headers=auth_headers(users["alice"], users["alice_org"]["id"]),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["result"] == "pong"