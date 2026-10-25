"""Organization and organization-member endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.auth.tenant import TenantContext, require_org, require_org_permission
from backend.db.models import (
    Organization,
    OrganizationMember,
    User,
)
from backend.db.schemas import (
    AddMemberRequest,
    MemberResponse,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
    UpdateMemberRoleRequest,
)
from backend.db.session import get_session

router = APIRouter(tags=["organizations"])


# ── Organizations ───────────────────────────────────────────────


@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    body: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Organization).where(Organization.slug == body.slug)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="An organization with this slug already exists"
        )

    org = Organization(
        name=body.name,
        slug=body.slug,
        description=body.description,
        owner_id=current_user.id,
    )
    session.add(org)
    await session.flush()

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role="owner",
    )
    session.add(membership)
    await session.flush()

    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        description=org.description,
        owner_id=org.owner_id,
        member_count=1,
        is_active=org.is_active,
        created_at=org.created_at,
    )


@router.get("/organizations", response_model=list[OrganizationResponse])
async def list_organizations(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    member_count_subq = (
        select(
            OrganizationMember.organization_id,
            func.count(OrganizationMember.id).label("cnt"),
        )
        .group_by(OrganizationMember.organization_id)
        .subquery()
    )
    result = await session.execute(
        select(
            Organization,
            func.coalesce(member_count_subq.c.cnt, 0).label("member_count"),
        )
        .outerjoin(
            member_count_subq,
            member_count_subq.c.organization_id == Organization.id,
        )
        .join(
            OrganizationMember,
            OrganizationMember.organization_id == Organization.id,
        )
        .where(
            OrganizationMember.user_id == current_user.id,
            Organization.is_active.is_(True),
        )
    )
    rows = result.all()
    return [
        OrganizationResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            description=org.description,
            avatar_url=org.avatar_url,
            owner_id=org.owner_id,
            member_count=member_count,
            is_active=org.is_active,
            created_at=org.created_at,
        )
        for org, member_count in rows
    ]


@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    result = await session.execute(
        select(Organization)
        .join(
            OrganizationMember,
            OrganizationMember.organization_id == Organization.id,
        )
        .where(
            Organization.id == org_id,
            OrganizationMember.user_id == current_user.id,
            Organization.is_active.is_(True),
        )
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    member_count = await session.scalar(
        select(func.count(OrganizationMember.id)).where(
            OrganizationMember.organization_id == org.id,
        )
    )
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        description=org.description,
        avatar_url=org.avatar_url,
        owner_id=org.owner_id,
        member_count=member_count or 0,
        is_active=org.is_active,
        created_at=org.created_at,
    )


@router.patch("/organizations/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: str,
    body: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org_permission("manage_workspaces")),
):
    result = await session.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.is_active.is_(True),
        )
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if body.name is not None:
        org.name = body.name
    if body.description is not None:
        org.description = body.description
    if body.avatar_url is not None:
        org.avatar_url = body.avatar_url
    await session.flush()
    return OrganizationResponse.model_validate(org)


@router.delete("/organizations/{org_id}")
async def delete_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org_permission("delete_organization")),
):
    result = await session.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.owner_id == current_user.id,
        )
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    org.is_active = False
    await session.flush()
    return {"status": "deleted"}


# ── Organization Members ────────────────────────────────────────


@router.get("/organizations/{org_id}/members", response_model=list[MemberResponse])
async def list_members(
    org_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    result = await session.execute(
        select(Organization)
        .where(Organization.id == org_id, Organization.is_active.is_(True))
        .join(
            OrganizationMember,
            OrganizationMember.organization_id == Organization.id,
        )
        .where(OrganizationMember.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    rows = await session.execute(
        select(OrganizationMember, User)
        .join(
            User,
            User.id == OrganizationMember.user_id,
        )
        .where(OrganizationMember.organization_id == org_id)
    )
    members = []
    for membership, user in rows.all():
        members.append(
            MemberResponse(
                id=membership.id,
                user_id=membership.user_id,
                name=user.name,
                email=user.email,
                role=membership.role,
                joined_at=membership.joined_at,
            )
        )
    return members


@router.post(
    "/organizations/{org_id}/members", response_model=MemberResponse, status_code=201
)
async def add_member(
    org_id: str,
    body: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org_permission("manage_members")),
):
    user_result = await session.execute(select(User).where(User.email == body.email))
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == target_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User is already a member")

    membership = OrganizationMember(
        organization_id=org_id,
        user_id=target_user.id,
        role=body.role.value,
    )
    session.add(membership)
    await session.flush()

    return MemberResponse(
        id=membership.id,
        user_id=membership.user_id,
        name=target_user.name,
        email=target_user.email,
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.patch("/organizations/{org_id}/members/{member_id}")
async def update_member_role(
    org_id: str,
    member_id: str,
    body: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org_permission("manage_members")),
):
    result = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == org_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot change the owner's role")
    membership.role = body.role.value
    await session.flush()
    return {"status": "updated", "role": membership.role}


@router.delete("/organizations/{org_id}/members/{member_id}")
async def remove_member(
    org_id: str,
    member_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org_permission("manage_members")),
):
    result = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == org_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found")
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the owner")
    if membership.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    await session.delete(membership)
    await session.flush()
    return {"status": "removed"}
