"""Tenant resolution and dependency unit tests.

Split from backend/tests/test_api_routes_units.py.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.tests._api_test_helpers import (
    Session,
    _ctx,
    _membership,
    _org,
    _project,
    _user,
    _workspace,
    asyncio_run,
    reset_tenant_context,
    resolve_org_from_subdomain,
    resolve_optional_tenant,
    resolve_tenant_dependencies,
    set_tenant_context,
    tenant_filter,
)
from backend.db.models import Conversation
from backend.auth.tenant import (
    _resolve_permissions,
    _slugify,
    get_tenant_context,
    require_org,
    require_org_permission,
    require_permission,
)


class TestTenantHelpers:
    def test_context_round_trip(self):
        reset_tenant_context()
        assert get_tenant_context() is None
        ctx = _ctx()
        set_tenant_context(ctx)
        assert get_tenant_context() is ctx
        reset_tenant_context()
        assert get_tenant_context() is None

    def test_slugify(self):
        assert _slugify("My Cool Org") == "my-cool-org"
        assert _slugify("R&D / Team") == "rd--team"

    def test_permissions_for_every_role(self):
        assert _resolve_permissions("viewer")["view_org"] is True
        assert "create_research" not in _resolve_permissions("viewer")
        assert _resolve_permissions("researcher")["create_research"] is True
        assert _resolve_permissions("manager")["manage_members"] is True
        assert _resolve_permissions("admin")["manage_workspaces"] is True
        assert _resolve_permissions("owner")["delete_organization"] is True
        assert _resolve_permissions("unknown") == {
            "view_own": True,
            "edit_own": True,
            "delete_own": True,
        }

    def test_require_permission(self):
        allowed = asyncio_run(require_permission("manage_members")(ctx=_ctx()))
        assert allowed.organization_id == "org-1"
        with pytest.raises(HTTPException) as excinfo:
            asyncio_run(require_permission("nonexistent_permission")(ctx=_ctx()))
        assert excinfo.value.status_code == 403

    def test_require_org(self):
        assert require_org("org-1", ctx=_ctx()).organization_id == "org-1"
        with pytest.raises(HTTPException) as excinfo:
            require_org("other", ctx=_ctx())
        assert excinfo.value.status_code == 403

    def test_require_org_permission(self):
        dependency = require_org_permission("manage_members")
        assert asyncio_run(dependency("org-1", ctx=_ctx())).organization_id == "org-1"

        with pytest.raises(HTTPException) as mismatch:
            asyncio_run(dependency("other", ctx=_ctx()))
        assert mismatch.value.status_code == 403
        assert "Not a member" in mismatch.value.detail

        with pytest.raises(HTTPException) as denied:
            asyncio_run(
                dependency("org-1", ctx=_ctx(permissions={"manage_members": False}))
            )
        assert "Missing required permission" in denied.value.detail

    def test_tenant_filter(self):
        reset_tenant_context()
        assert tenant_filter(Conversation) == []
        set_tenant_context(_ctx())
        assert len(tenant_filter(Conversation)) == 1
        set_tenant_context(_ctx(workspace_id="ws-1", project_id="proj-1"))
        assert len(tenant_filter(Conversation)) == 3
        reset_tenant_context()

    def test_resolve_org_from_subdomain(self):
        async def resolve(host):
            request = SimpleNamespace(headers={"host": host})
            return await resolve_org_from_subdomain(request)

        assert asyncio_run(resolve("acme.example.com")) == "acme"
        assert asyncio_run(resolve("www.example.com")) is None
        assert asyncio_run(resolve("app.example.com")) is None
        assert asyncio_run(resolve("localhost")) is None
        assert asyncio_run(resolve("")) is None

    def test_resolve_optional_tenant_without_user(self):
        assert (
            asyncio_run(
                resolve_optional_tenant(MagicMock(), user=None, session=Session())
            )
            is None
        )

    def test_resolve_optional_tenant_swallows_http_errors(self):
        request = MagicMock()
        request.headers = {}
        user = _user()
        session = Session(None)
        assert asyncio_run(resolve_optional_tenant(request, user, session)) is None


class TestResolveTenantDependencies:
    def _request(self, **headers):
        request = MagicMock()
        request.headers = headers
        return request

    def test_org_id_path_success(self):
        session = Session(
            _org(),
            _membership(),
            _membership(),
        )
        ctx = asyncio_run(
            resolve_tenant_dependencies(
                self._request(**{"X-Organization-Id": "org-1"}),
                user=_user(),
                session=session,
            )
        )
        assert ctx.organization_id == "org-1"
        assert ctx.user_role == "owner"
        assert ctx.permissions["delete_organization"] is True

    def test_org_id_missing_raises_404(self):
        with pytest.raises(HTTPException) as excinfo:
            asyncio_run(
                resolve_tenant_dependencies(
                    self._request(**{"X-Organization-Id": "missing"}),
                    user=_user(),
                    session=Session(None),
                )
            )
        assert excinfo.value.status_code == 404

    def test_org_id_non_member_raises_403(self):
        with pytest.raises(HTTPException) as excinfo:
            asyncio_run(
                resolve_tenant_dependencies(
                    self._request(**{"X-Organization-Id": "org-1"}),
                    user=_user(),
                    session=Session(_org(), None),
                )
            )
        assert excinfo.value.status_code == 403

    def test_org_slug_path(self):
        session = Session(
            _org(),
            _membership(),
            _workspace(),
            _project(),
            _membership(role="researcher"),
        )
        ctx = asyncio_run(
            resolve_tenant_dependencies(
                self._request(
                    **{
                        "X-Organization-Slug": "org",
                        "X-Workspace-Id": "ws-1",
                        "X-Project-Id": "proj-1",
                    }
                ),
                user=_user(),
                session=session,
            )
        )
        assert ctx.organization_slug == "org"
        assert ctx.workspace_id == "ws-1"
        assert ctx.project_id == "proj-1"
        assert ctx.user_role == "researcher"

    def test_org_slug_missing_and_non_member(self):
        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                resolve_tenant_dependencies(
                    self._request(**{"X-Organization-Slug": "missing"}),
                    user=_user(),
                    session=Session(None),
                )
            )
        assert missing.value.status_code == 404

        with pytest.raises(HTTPException) as denied:
            asyncio_run(
                resolve_tenant_dependencies(
                    self._request(**{"X-Organization-Slug": "org"}),
                    user=_user(),
                    session=Session(_org(), None),
                )
            )
        assert denied.value.status_code == 403

    def test_subdomain_resolution(self):
        session = Session(_org(), _membership(), _membership(role="admin"))
        ctx = asyncio_run(
            resolve_tenant_dependencies(
                self._request(host="acme.example.com"),
                user=_user(),
                session=session,
            )
        )
        assert ctx.organization_id == "org-1"
        assert ctx.user_role == "admin"

    def test_subdomain_org_missing_falls_back_to_membership(self):
        session = Session(
            None,
            _membership(organization_id="fallback-org"),
            _org(id="fallback-org", slug="fallback"),
            _membership(organization_id="fallback-org", role="manager"),
        )
        ctx = asyncio_run(
            resolve_tenant_dependencies(
                self._request(host="unknown.example.com"),
                user=_user(),
                session=session,
            )
        )
        assert ctx.organization_id == "fallback-org"
        assert ctx.organization_slug == "fallback"
        assert ctx.user_role == "manager"

    def test_no_membership_raises_organization_required(self):
        with pytest.raises(HTTPException) as excinfo:
            asyncio_run(
                resolve_tenant_dependencies(
                    self._request(), user=_user(), session=Session(None)
                )
            )
        assert excinfo.value.status_code == 403
        assert excinfo.value.detail["code"] == "organization_required"

    def test_workspace_and_project_not_found_are_ignored(self):
        session = Session(
            _org(),
            _membership(),
            None,
            None,
            None,
        )
        ctx = asyncio_run(
            resolve_tenant_dependencies(
                self._request(
                    **{
                        "X-Organization-Id": "org-1",
                        "X-Workspace-Id": "missing",
                        "X-Project-Id": "missing",
                    }
                ),
                user=_user(),
                session=session,
            )
        )
        assert ctx.workspace_id is None
        assert ctx.project_id is None
        assert ctx.user_role == "viewer"

    def test_fallback_membership_without_org_slug(self):
        session = Session(
            _membership(organization_id="org-2"),
            None,
            None,
        )
        ctx = asyncio_run(
            resolve_tenant_dependencies(self._request(), user=_user(), session=session)
        )
        assert ctx.organization_id == "org-2"
        assert ctx.organization_slug == ""
        assert ctx.user_role == "viewer"
