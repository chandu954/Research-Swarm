"""Workspace and project route unit tests.

Split from backend/tests/test_api_routes_units.py.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from backend.tests._api_test_helpers import (
    Session,
    _ctx,
    _project,
    _user,
    _workspace,
    asyncio_run,
)


class TestWorkspaceRoutes:
    def test_create_workspace_conflict_and_success(self):
        from backend.api.workspaces import create_workspace

        from backend.db.schemas import WorkspaceCreate

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

        from backend.db.schemas import WorkspaceCreate

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

        from backend.db.schemas import WorkspaceUpdate

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

        from backend.db.schemas import ProjectCreate, ProjectUpdate

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

        from backend.db.models import WorkspaceMember

        from backend.tests._api_test_helpers import NOW

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
