"""Organization route unit tests.

Split from backend/tests/test_api_routes_units.py.
"""

from __future__ import annotations

import pytest
from backend.tests._api_test_helpers import (
    Session,
    _ctx,
    _membership,
    _org,
    _user,
    asyncio_run,
)
from fastapi import HTTPException


class TestOrganizationRoutes:
    def test_create_conflict_and_success(self):
        from backend.api.organizations import create_organization
        from backend.db.schemas import OrganizationCreate

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
        from backend.db.schemas import OrganizationUpdate

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
        from backend.db.schemas import AddMemberRequest, MemberRole

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
        from backend.db.schemas import MemberRole, UpdateMemberRoleRequest

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
