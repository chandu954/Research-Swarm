"""Direct route/helper coverage for tenant, health, org, workspace, chat APIs."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.auth.tenant import (
    TenantContext,
    _resolve_permissions,
    _slugify,
    get_tenant_context,
    require_org,
    require_org_permission,
    require_permission,
    reset_tenant_context,
    resolve_optional_tenant,
    resolve_org_from_subdomain,
    resolve_tenant_dependencies,
    set_tenant_context,
    tenant_filter,
)
from backend.db.models import (
    Conversation,
    Message,
    Organization,
    OrganizationMember,
    Project,
    User,
    Workspace,
    WorkspaceMember,
)
from backend.db.schemas import (
    AddMemberRequest,
    ConversationCreate,
    ConversationUpdate,
    MemberRole,
    OrganizationCreate,
    OrganizationUpdate,
    ProjectCreate,
    ProjectUpdate,
    UpdateMemberRoleRequest,
    WorkspaceCreate,
    WorkspaceUpdate,
)


def asyncio_run(coroutine):
    return asyncio.run(coroutine)


NOW = datetime.now(timezone.utc)


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        if isinstance(self.value, list):
            return self.value
        return [] if self.value is None else [self.value]

    def fetchall(self):
        return self.value or []


class Session:
    def __init__(self, *results, scalar_values=()):
        self.results = list(results)
        self.scalar_values = list(scalar_values)
        self.added = []
        self.deleted = []
        self.flushes = 0
        self.commits = 0

    async def execute(self, *_args, **_kwargs):
        return Result(self.results.pop(0) if self.results else None)

    async def scalar(self, *_args, **_kwargs):
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def flush(self):
        self.flushes += 1
        for item in self.added:
            _ensure_defaults(item)

    async def commit(self):
        self.commits += 1

    def add(self, item):
        self.added.append(item)
        _ensure_defaults(item)

    async def delete(self, item):
        self.deleted.append(item)

    def scalars(self):
        return self

    def all(self):
        return self.scalar_values.pop(0) if self.scalar_values else []


def _ensure_defaults(item):
    if getattr(item, "id", None) is None:
        item.id = str(uuid.uuid4())
    for attr in ("created_at", "updated_at", "joined_at"):
        if hasattr(item, attr) and getattr(item, attr) is None:
            setattr(item, attr, NOW)
    for attr in ("is_active", "trusted"):
        if hasattr(item, attr) and getattr(item, attr) is None:
            setattr(item, attr, True)


def _user(user_id="user-1", **overrides):
    values = {
        "id": user_id,
        "email": f"{user_id}@example.com",
        "name": "User",
        "is_active": True,
        "mfa_enabled": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return User(**values)


def _org(**overrides):
    values = {
        "id": "org-1",
        "name": "Org",
        "slug": "org",
        "description": None,
        "avatar_url": None,
        "owner_id": "user-1",
        "is_active": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Organization(**values)


def _workspace(**overrides):
    values = {
        "id": "ws-1",
        "organization_id": "org-1",
        "name": "Workspace",
        "slug": "workspace",
        "description": None,
        "owner_id": "user-1",
        "is_active": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Workspace(**values)


def _project(**overrides):
    values = {
        "id": "proj-1",
        "organization_id": "org-1",
        "workspace_id": "ws-1",
        "name": "Project",
        "slug": "project",
        "description": None,
        "owner_id": "user-1",
        "is_active": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Project(**values)


def _membership(**overrides):
    values = {
        "id": "member-1",
        "organization_id": "org-1",
        "user_id": "user-1",
        "role": "owner",
        "joined_at": NOW,
    }
    values.update(overrides)
    return OrganizationMember(**values)


def _ctx(**overrides):
    values = {
        "organization_id": "org-1",
        "organization_slug": "org",
        "workspace_id": None,
        "project_id": None,
        "user_id": "user-1",
        "user_role": "owner",
        "permissions": _resolve_permissions("owner"),
    }
    values.update(overrides)
    return TenantContext(**values)


# ── Tenant resolution ───────────────────────────────────────────


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


# ── Health endpoints ────────────────────────────────────────────


class TestHealthEndpoints:
    def _request(self):
        registry = MagicMock()
        registry.list_tools.return_value = [1, 2]
        app = SimpleNamespace(
            state=SimpleNamespace(
                start_time=100.0,
                registry=registry,
            )
        )
        return SimpleNamespace(app=app)

    def test_health_ok_with_openrouter_configured(self, monkeypatch):
        from backend.api.health import health_check

        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "key")
        with patch(
            "backend.db.session.get_session", _session_generator(Session())
        ), patch("backend.api.health.get_plugin_registry") as registry, patch(
            "backend.api.health.time.time", return_value=105.0
        ):
            registry.return_value.list_types.return_value = ["llm"]
            result = asyncio_run(health_check(self._request()))

        assert result["status"] == "healthy"
        assert result["uptime"] == 5.0
        assert result["tools_available"] == 2
        assert result["checks"] == {"database": "ok", "openrouter": "ok"}

    def test_health_degraded_when_database_fails(self, monkeypatch):
        from backend.api.health import health_check

        monkeypatch.setenv("LLM_PROVIDER", "openrouter")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        def failing():
            raise RuntimeError("db down")

        with patch("backend.db.session.get_session", failing), patch(
            "backend.api.health.get_plugin_registry"
        ) as registry:
            registry.return_value.list_types.return_value = []
            result = asyncio_run(health_check(self._request()))

        assert result["status"] == "degraded"
        assert result["checks"]["database"] == "error: db down"
        assert result["checks"]["openrouter"] == "unconfigured"

    def test_health_checks_ollama(self, monkeypatch):
        from backend.api.health import health_check

        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        response = SimpleNamespace(status_code=200)
        client = AsyncMock()
        client.get.return_value = response
        client.__aenter__.return_value = client
        client.__aexit__.return_value = False

        with patch(
            "backend.db.session.get_session", _session_generator(Session())
        ), patch("backend.api.health.get_plugin_registry"), patch(
            "httpx.AsyncClient", return_value=client
        ):
            result = asyncio_run(health_check(self._request()))
        assert result["checks"]["ollama"] == "ok"

        response.status_code = 500
        with patch(
            "backend.db.session.get_session", _session_generator(Session())
        ), patch("backend.api.health.get_plugin_registry"), patch(
            "httpx.AsyncClient", return_value=client
        ):
            assert (
                asyncio_run(health_check(self._request()))["checks"]["ollama"]
                == "error"
            )

    def test_health_ollama_connection_error(self, monkeypatch):
        from backend.api.health import health_check

        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        with patch(
            "backend.db.session.get_session", _session_generator(Session())
        ), patch("backend.api.health.get_plugin_registry"), patch(
            "httpx.AsyncClient", side_effect=RuntimeError("down")
        ):
            result = asyncio_run(health_check(self._request()))
        assert result["checks"]["ollama"] == "error"

    def test_ready_ok_and_not_ready(self):
        from fastapi.responses import JSONResponse
        from backend.api.health import ready_check

        with patch("backend.db.session.get_session", _session_generator(Session())):
            assert asyncio_run(ready_check(self._request())) == {"status": "ready"}

        with patch("backend.db.session.get_session", side_effect=RuntimeError("down")):
            response = asyncio_run(ready_check(self._request()))
        assert isinstance(response, JSONResponse)
        assert response.status_code == 503


def _session_generator(session):
    async def generator():
        yield session

    return generator


# ── Organization routes ─────────────────────────────────────────


class TestOrganizationRoutes:
    def test_create_conflict_and_success(self):
        from backend.api.organizations import create_organization

        body = OrganizationCreate(name="Org", slug="org", description="d")
        with pytest.raises(HTTPException) as conflict:
            asyncio_run(
                create_organization(body, current_user=_user(), session=Session(_org()))
            )
        assert conflict.value.status_code == 409

        session = Session(None)
        response = asyncio_run(
            create_organization(body, current_user=_user(), session=session)
        )
        assert response.slug == "org"
        assert response.member_count == 1
        assert len(session.added) == 2

    def test_list_organizations(self):
        from backend.api.organizations import list_organizations

        session = Session([(_org(), 3), (_org(id="org-2", slug="two"), 0)])
        response = asyncio_run(
            list_organizations(current_user=_user(), session=session)
        )
        assert [item.member_count for item in response] == [3, 0]

    def test_get_organization(self):
        from backend.api.organizations import get_organization

        session = Session(_org(), scalar_values=[4])
        response = asyncio_run(
            get_organization("org-1", current_user=_user(), session=session, ctx=_ctx())
        )
        assert response.member_count == 4

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                get_organization(
                    "missing", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )
        assert missing.value.status_code == 404

    def test_update_organization(self):
        from backend.api.organizations import update_organization

        org = _org()
        session = Session(org)
        response = asyncio_run(
            update_organization(
                "org-1",
                OrganizationUpdate(
                    name="New", description="Desc", avatar_url="https://a.test"
                ),
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert response.name == "New"
        assert response.avatar_url == "https://a.test"

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                update_organization(
                    "missing",
                    OrganizationUpdate(),
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )
        assert missing.value.status_code == 404

    def test_delete_organization(self):
        from backend.api.organizations import delete_organization

        org = _org()
        assert asyncio_run(
            delete_organization(
                "org-1", current_user=_user(), session=Session(org), ctx=_ctx()
            )
        ) == {"status": "deleted"}
        assert org.is_active is False

        with pytest.raises(HTTPException):
            asyncio_run(
                delete_organization(
                    "missing",
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )

    def test_list_members(self):
        from backend.api.organizations import list_members

        member = _membership(role="researcher")
        session = Session(_org(), [(member, _user())])
        response = asyncio_run(
            list_members("org-1", current_user=_user(), session=session, ctx=_ctx())
        )
        assert response[0].role == "researcher"

        with pytest.raises(HTTPException) as denied:
            asyncio_run(
                list_members(
                    "org-1", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )
        assert denied.value.status_code == 403

    def test_add_member(self):
        from backend.api.organizations import add_member

        body = AddMemberRequest(email="new@example.com", role=MemberRole.RESEARCHER)
        target = _user("target", email="new@example.com", name="Target")
        session = Session(target, None)
        response = asyncio_run(
            add_member("org-1", body, current_user=_user(), session=session, ctx=_ctx())
        )
        assert response.email == "new@example.com"
        assert response.role == "researcher"

        with pytest.raises(HTTPException) as missing_user:
            asyncio_run(
                add_member(
                    "org-1",
                    body,
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )
        assert missing_user.value.status_code == 404

        with pytest.raises(HTTPException) as conflict:
            asyncio_run(
                add_member(
                    "org-1",
                    body,
                    current_user=_user(),
                    session=Session(target, _membership()),
                    ctx=_ctx(),
                )
            )
        assert conflict.value.status_code == 409

    def test_update_member_role(self):
        from backend.api.organizations import update_member_role

        member = _membership(role="researcher")
        response = asyncio_run(
            update_member_role(
                "org-1",
                "member-1",
                UpdateMemberRoleRequest(role=MemberRole.MANAGER),
                current_user=_user(),
                session=Session(member),
                ctx=_ctx(),
            )
        )
        assert response["role"] == "manager"

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                update_member_role(
                    "org-1",
                    "missing",
                    UpdateMemberRoleRequest(role=MemberRole.MANAGER),
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )
        assert missing.value.status_code == 404

        with pytest.raises(HTTPException) as owner:
            asyncio_run(
                update_member_role(
                    "org-1",
                    "member-1",
                    UpdateMemberRoleRequest(role=MemberRole.ADMIN),
                    current_user=_user(),
                    session=Session(_membership(role="owner")),
                    ctx=_ctx(),
                )
            )
        assert owner.value.status_code == 400

    def test_remove_member(self):
        from backend.api.organizations import remove_member

        member = _membership(user_id="other", role="researcher")
        session = Session(member)
        assert asyncio_run(
            remove_member(
                "org-1", "member-1", current_user=_user(), session=session, ctx=_ctx()
            )
        ) == {"status": "removed"}
        assert session.deleted == [member]

        cases = [
            (Session(None), "member-1", 404),
            (Session(_membership(role="owner")), "member-1", 400),
            (
                Session(_membership(user_id="user-1", role="researcher")),
                "member-1",
                400,
            ),
        ]
        for case_session, member_id, status_code in cases:
            with pytest.raises(HTTPException) as excinfo:
                asyncio_run(
                    remove_member(
                        "org-1",
                        member_id,
                        current_user=_user(),
                        session=case_session,
                        ctx=_ctx(),
                    )
                )
            assert excinfo.value.status_code == status_code


# ── Workspace and project routes ────────────────────────────────


class TestWorkspaceRoutes:
    def test_create_workspace_conflict_and_success(self):
        from backend.api.workspaces import create_workspace

        body = WorkspaceCreate(name="My Workspace")
        with pytest.raises(HTTPException) as conflict:
            asyncio_run(
                create_workspace(
                    "org-1",
                    body,
                    current_user=_user(),
                    session=Session(_workspace()),
                    ctx=_ctx(),
                )
            )
        assert conflict.value.status_code == 409

        session = Session(None)
        response = asyncio_run(
            create_workspace(
                "org-1", body, current_user=_user(), session=session, ctx=_ctx()
            )
        )
        assert response.slug == "my-workspace"
        assert len(session.added) == 2

    def test_create_workspace_with_explicit_slug(self):
        from backend.api.workspaces import create_workspace

        response = asyncio_run(
            create_workspace(
                "org-1",
                WorkspaceCreate(name="Name", slug="explicit"),
                current_user=_user(),
                session=Session(None),
                ctx=_ctx(),
            )
        )
        assert response.slug == "explicit"

    def test_list_workspaces(self):
        from backend.api.workspaces import list_workspaces

        session = Session([(_workspace(), 2)])
        response = asyncio_run(
            list_workspaces("org-1", current_user=_user(), session=session, ctx=_ctx())
        )
        assert response[0].member_count == 2

    def test_get_update_delete_workspace(self):
        from backend.api.workspaces import (
            delete_workspace,
            get_workspace,
            update_workspace,
        )

        ws = _workspace()
        response = asyncio_run(
            get_workspace(
                "org-1",
                "ws-1",
                current_user=_user(),
                session=Session(ws, scalar_values=[2]),
                ctx=_ctx(),
            )
        )
        assert response.member_count == 2

        with pytest.raises(HTTPException):
            asyncio_run(
                get_workspace(
                    "org-1",
                    "missing",
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )

        updated = asyncio_run(
            update_workspace(
                "org-1",
                "ws-1",
                WorkspaceUpdate(name="New", description="D"),
                current_user=_user(),
                session=Session(ws),
                ctx=_ctx(),
            )
        )
        assert updated.name == "New"

        with pytest.raises(HTTPException):
            asyncio_run(
                update_workspace(
                    "org-1",
                    "missing",
                    WorkspaceUpdate(),
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )

        ws = _workspace()
        assert asyncio_run(
            delete_workspace(
                "org-1", "ws-1", current_user=_user(), session=Session(ws), ctx=_ctx()
            )
        ) == {"status": "deleted"}
        assert ws.is_active is False

        with pytest.raises(HTTPException):
            asyncio_run(
                delete_workspace(
                    "org-1",
                    "missing",
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )

    def test_project_lifecycle(self):
        from backend.api.workspaces import (
            create_project,
            delete_project,
            get_project,
            list_projects,
            update_project,
        )

        body = ProjectCreate(name="My Project")
        with pytest.raises(HTTPException) as conflict:
            asyncio_run(
                create_project(
                    "org-1",
                    "ws-1",
                    body,
                    current_user=_user(),
                    session=Session(_project()),
                    ctx=_ctx(),
                )
            )
        assert conflict.value.status_code == 409

        session = Session(None)
        created = asyncio_run(
            create_project(
                "org-1",
                "ws-1",
                body,
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert created.slug == "my-project"

        listed = asyncio_run(
            list_projects(
                "org-1",
                "ws-1",
                current_user=_user(),
                session=Session([_project()]),
                ctx=_ctx(),
            )
        )
        assert listed[0].id == "proj-1"

        proj = _project()
        assert (
            asyncio_run(
                get_project(
                    "org-1",
                    "ws-1",
                    "proj-1",
                    current_user=_user(),
                    session=Session(proj),
                    ctx=_ctx(),
                )
            ).id
            == "proj-1"
        )

        with pytest.raises(HTTPException):
            asyncio_run(
                get_project(
                    "org-1",
                    "ws-1",
                    "missing",
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )

        updated = asyncio_run(
            update_project(
                "org-1",
                "ws-1",
                "proj-1",
                ProjectUpdate(name="Renamed", description="D"),
                current_user=_user(),
                session=Session(proj),
                ctx=_ctx(),
            )
        )
        assert updated.name == "Renamed"

        with pytest.raises(HTTPException):
            asyncio_run(
                update_project(
                    "org-1",
                    "ws-1",
                    "missing",
                    ProjectUpdate(),
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )

        proj = _project()
        assert asyncio_run(
            delete_project(
                "org-1",
                "ws-1",
                "proj-1",
                current_user=_user(),
                session=Session(proj),
                ctx=_ctx(),
            )
        ) == {"status": "deleted"}
        assert proj.is_active is False

        with pytest.raises(HTTPException):
            asyncio_run(
                delete_project(
                    "org-1",
                    "ws-1",
                    "missing",
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )

    def test_list_workspace_members(self):
        from backend.api.workspaces import list_workspace_members

        member = WorkspaceMember(
            id="wm-1",
            workspace_id="ws-1",
            user_id="user-1",
            role="owner",
            joined_at=NOW,
        )
        session = Session([(member, _user())])
        response = asyncio_run(
            list_workspace_members(
                "org-1",
                "ws-1",
                current_user=_user(),
                session=session,
                ctx=_ctx(),
            )
        )
        assert response[0].email == "user-1@example.com"


# ── Conversation routes ─────────────────────────────────────────


def _conversation(**overrides):
    values = {
        "id": "conv-1",
        "user_id": "user-1",
        "organization_id": "org-1",
        "workspace_id": "ws-1",
        "project_id": "proj-1",
        "title": "Conversation",
        "description": None,
        "is_archived": False,
        "is_pinned": False,
        "is_favorited": False,
        "visibility": "workspace",
        "is_deleted": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return Conversation(**values)


class TestConversationRoutes:
    def test_list_with_filters_and_message_counts(self):
        from backend.api.conversations import list_conversations

        session = Session([_conversation()], scalar_values=[3])
        response = asyncio_run(
            list_conversations(
                ws_id="ignored",
                proj_id="proj-1",
                archived=False,
                search="Conv",
                limit=10,
                offset=0,
                current_user=_user(),
                session=session,
                ctx=_ctx(workspace_id="ws-1"),
            )
        )
        assert response[0].message_count == 3

        session = Session([], scalar_values=[None])
        assert (
            asyncio_run(
                list_conversations(
                    ws_id="ws-2",
                    proj_id=None,
                    archived=True,
                    search=None,
                    limit=10,
                    offset=0,
                    current_user=_user(),
                    session=session,
                    ctx=_ctx(workspace_id=None),
                )
            )
            == []
        )

    def test_create_conversation(self):
        from backend.api.conversations import create_conversation

        session = Session()
        with patch("backend.api.conversations.log_audit", new=AsyncMock()) as audit:
            response = asyncio_run(
                create_conversation(
                    ConversationCreate(title="Mine"),
                    current_user=_user(),
                    session=session,
                    ctx=_ctx(),
                )
            )
        assert response.title == "Mine"
        assert audit.await_count == 1

        with patch("backend.api.conversations.log_audit", new=AsyncMock()):
            response = asyncio_run(
                create_conversation(
                    ConversationCreate(project_id="body-project"),
                    current_user=_user(),
                    session=Session(),
                    ctx=_ctx(project_id="ctx-project"),
                )
            )
        assert response.title == "New Conversation"

    def test_get_conversation(self):
        from backend.api.conversations import get_conversation

        message = Message(
            id="msg-1",
            conversation_id="conv-1",
            role="user",
            content="hi",
            sources=[],
            metadata_={},
            created_at=NOW,
        )
        session = Session(_conversation(), [message])
        response = asyncio_run(
            get_conversation(
                "conv-1", current_user=_user(), session=session, ctx=_ctx()
            )
        )
        assert response.messages[0].content == "hi"

        with pytest.raises(HTTPException) as missing:
            asyncio_run(
                get_conversation(
                    "missing", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )
        assert missing.value.status_code == 404

    def test_update_conversation(self):
        from backend.api.conversations import update_conversation

        conv = _conversation()
        response = asyncio_run(
            update_conversation(
                "conv-1",
                ConversationUpdate(
                    title="New",
                    description="Desc",
                    is_archived=True,
                    is_pinned=True,
                    is_favorited=True,
                    visibility="private",
                ),
                current_user=_user(),
                session=Session(conv),
                ctx=_ctx(),
            )
        )
        assert response.title == "New"
        assert response.visibility == "private"

        with pytest.raises(HTTPException):
            asyncio_run(
                update_conversation(
                    "missing",
                    ConversationUpdate(),
                    current_user=_user(),
                    session=Session(None),
                    ctx=_ctx(),
                )
            )

    def test_delete_conversation(self):
        from backend.api.conversations import delete_conversation

        conv = _conversation()
        with patch("backend.api.conversations.log_audit", new=AsyncMock()):
            assert asyncio_run(
                delete_conversation(
                    "conv-1", current_user=_user(), session=Session(conv), ctx=_ctx()
                )
            ) == {"status": "deleted"}
        assert conv.is_deleted is True
        assert conv.deleted_at is not None

        with pytest.raises(HTTPException):
            asyncio_run(
                delete_conversation(
                    "missing", current_user=_user(), session=Session(None), ctx=_ctx()
                )
            )
