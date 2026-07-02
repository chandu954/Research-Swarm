"""Organization, workspace, and project management endpoints."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from backend.db.session import get_session
from backend.db.models import (
    User, Organization, OrganizationMember,
    Workspace, WorkspaceMember,
    Project,
)
from backend.db.schemas import (
    OrganizationCreate, OrganizationResponse, OrganizationUpdate,
    MemberResponse, AddMemberRequest, UpdateMemberRoleRequest,
    WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate,
    ProjectCreate, ProjectResponse, ProjectUpdate,
)
from backend.auth.dependencies import get_current_user
from backend.auth.tenant import (
    resolve_tenant_dependencies, TenantContext,
    require_permission,
)

router = APIRouter(tags=["organizations"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))
    if not slug:
        slug = "org"
    return slug


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
        raise HTTPException(status_code=409, detail="An organization with this slug already exists")

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
    result = await session.execute(
        select(Organization).join(
            OrganizationMember,
            OrganizationMember.organization_id == Organization.id,
        ).where(
            OrganizationMember.user_id == current_user.id,
            Organization.is_active == True,
        )
    )
    orgs = result.scalars().all()
    responses = []
    for org in orgs:
        member_count = await session.scalar(
            select(func.count(OrganizationMember.id)).where(
                OrganizationMember.organization_id == org.id,
            )
        )
        responses.append(OrganizationResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            description=org.description,
            avatar_url=org.avatar_url,
            owner_id=org.owner_id,
            member_count=member_count or 0,
            is_active=org.is_active,
            created_at=org.created_at,
        ))
    return responses


@router.get("/organizations/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Organization).join(
            OrganizationMember,
            OrganizationMember.organization_id == Organization.id,
        ).where(
            Organization.id == org_id,
            OrganizationMember.user_id == current_user.id,
            Organization.is_active == True,
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
    ctx: TenantContext = Depends(require_permission("manage_workspaces")),
):
    result = await session.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.is_active == True,
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
    ctx: TenantContext = Depends(require_permission("delete_organization")),
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
):
    result = await session.execute(
        select(Organization).where(Organization.id == org_id, Organization.is_active == True).join(
            OrganizationMember,
            OrganizationMember.organization_id == Organization.id,
        ).where(OrganizationMember.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    rows = await session.execute(
        select(OrganizationMember, User).join(
            User, User.id == OrganizationMember.user_id,
        ).where(OrganizationMember.organization_id == org_id)
    )
    members = []
    for membership, user in rows.all():
        members.append(MemberResponse(
            id=membership.id,
            user_id=membership.user_id,
            name=user.name,
            email=user.email,
            role=membership.role,
            joined_at=membership.joined_at,
        ))
    return members


@router.post("/organizations/{org_id}/members", response_model=MemberResponse, status_code=201)
async def add_member(
    org_id: str,
    body: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_permission("manage_members")),
):
    user_result = await session.execute(
        select(User).where(User.email == body.email)
    )
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
    ctx: TenantContext = Depends(require_permission("manage_members")),
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
    ctx: TenantContext = Depends(require_permission("manage_members")),
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


# ── Workspaces ──────────────────────────────────────────────────

@router.post("/organizations/{org_id}/workspaces", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    org_id: str,
    body: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    slug = body.slug or _slugify(body.name)
    result = await session.execute(
        select(Workspace).where(
            Workspace.organization_id == org_id,
            Workspace.slug == slug,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A workspace with this slug already exists")

    ws = Workspace(
        organization_id=org_id,
        name=body.name,
        slug=slug,
        description=body.description,
        owner_id=current_user.id,
        vector_db_namespace=f"org_{org_id}_ws_{slug}",
    )
    session.add(ws)
    await session.flush()

    membership = WorkspaceMember(
        workspace_id=ws.id,
        user_id=current_user.id,
        role="owner",
    )
    session.add(membership)
    await session.flush()

    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        description=ws.description,
        organization_id=ws.organization_id,
        owner_id=ws.owner_id,
        member_count=1,
        is_active=ws.is_active,
        created_at=ws.created_at,
    )


@router.get("/organizations/{org_id}/workspaces", response_model=list[WorkspaceResponse])
async def list_workspaces(
    org_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Workspace).join(
            WorkspaceMember,
            WorkspaceMember.workspace_id == Workspace.id,
        ).where(
            Workspace.organization_id == org_id,
            WorkspaceMember.user_id == current_user.id,
            Workspace.is_active == True,
        )
    )
    workspaces = result.scalars().all()
    responses = []
    for ws in workspaces:
        member_count = await session.scalar(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == ws.id,
            )
        )
        responses.append(WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            description=ws.description,
            organization_id=ws.organization_id,
            owner_id=ws.owner_id,
            member_count=member_count or 0,
            is_active=ws.is_active,
            created_at=ws.created_at,
        ))
    return responses


@router.get("/organizations/{org_id}/workspaces/{ws_id}", response_model=WorkspaceResponse)
async def get_workspace(
    org_id: str,
    ws_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Workspace).where(
            Workspace.id == ws_id,
            Workspace.organization_id == org_id,
            Workspace.is_active == True,
        )
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    member_count = await session.scalar(
        select(func.count(WorkspaceMember.id)).where(
            WorkspaceMember.workspace_id == ws.id,
        )
    )
    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        description=ws.description,
        organization_id=ws.organization_id,
        owner_id=ws.owner_id,
        member_count=member_count or 0,
        is_active=ws.is_active,
        created_at=ws.created_at,
    )


@router.patch("/organizations/{org_id}/workspaces/{ws_id}", response_model=WorkspaceResponse)
async def update_workspace(
    org_id: str,
    ws_id: str,
    body: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Workspace).where(
            Workspace.id == ws_id,
            Workspace.organization_id == org_id,
            Workspace.is_active == True,
        )
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if body.name is not None:
        ws.name = body.name
    if body.description is not None:
        ws.description = body.description
    await session.flush()
    return WorkspaceResponse.model_validate(ws)


@router.delete("/organizations/{org_id}/workspaces/{ws_id}")
async def delete_workspace(
    org_id: str,
    ws_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Workspace).where(
            Workspace.id == ws_id,
            Workspace.organization_id == org_id,
            Workspace.owner_id == current_user.id,
        )
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.is_active = False
    await session.flush()
    return {"status": "deleted"}


# ── Projects ────────────────────────────────────────────────────

@router.post("/organizations/{org_id}/workspaces/{ws_id}/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    org_id: str,
    ws_id: str,
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    slug = body.slug or _slugify(body.name)
    result = await session.execute(
        select(Project).where(
            Project.workspace_id == ws_id,
            Project.slug == slug,
            Project.is_active == True,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A project with this slug already exists")

    proj = Project(
        organization_id=org_id,
        workspace_id=ws_id,
        name=body.name,
        slug=slug,
        description=body.description,
        owner_id=current_user.id,
    )
    session.add(proj)
    await session.flush()

    return ProjectResponse(
        id=proj.id,
        name=proj.name,
        slug=proj.slug,
        description=proj.description,
        organization_id=proj.organization_id,
        workspace_id=proj.workspace_id,
        owner_id=proj.owner_id,
        is_active=proj.is_active,
        created_at=proj.created_at,
    )


@router.get("/organizations/{org_id}/workspaces/{ws_id}/projects", response_model=list[ProjectResponse])
async def list_projects(
    org_id: str,
    ws_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(
            Project.workspace_id == ws_id,
            Project.organization_id == org_id,
            Project.is_active == True,
        )
    )
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


@router.get("/organizations/{org_id}/workspaces/{ws_id}/projects/{proj_id}", response_model=ProjectResponse)
async def get_project(
    org_id: str,
    ws_id: str,
    proj_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(
            Project.id == proj_id,
            Project.workspace_id == ws_id,
            Project.organization_id == org_id,
            Project.is_active == True,
        )
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(proj)


@router.patch("/organizations/{org_id}/workspaces/{ws_id}/projects/{proj_id}", response_model=ProjectResponse)
async def update_project(
    org_id: str,
    ws_id: str,
    proj_id: str,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(
            Project.id == proj_id,
            Project.workspace_id == ws_id,
            Project.organization_id == org_id,
            Project.is_active == True,
        )
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if body.name is not None:
        proj.name = body.name
    if body.description is not None:
        proj.description = body.description
    await session.flush()
    return ProjectResponse.model_validate(proj)


@router.delete("/organizations/{org_id}/workspaces/{ws_id}/projects/{proj_id}")
async def delete_project(
    org_id: str,
    ws_id: str,
    proj_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Project).where(
            Project.id == proj_id,
            Project.workspace_id == ws_id,
            Project.organization_id == org_id,
            Project.owner_id == current_user.id,
        )
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    proj.is_active = False
    await session.flush()
    return {"status": "deleted"}


# ── Workspace Members ──────────────────────────────────────────

@router.get("/organizations/{org_id}/workspaces/{ws_id}/members", response_model=list[MemberResponse])
async def list_workspace_members(
    org_id: str,
    ws_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = await session.execute(
        select(WorkspaceMember, User).join(
            User, User.id == WorkspaceMember.user_id,
        ).where(WorkspaceMember.workspace_id == ws_id)
    )
    return [
        MemberResponse(
            id=m.id,
            user_id=m.user_id,
            name=u.name,
            email=u.email,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m, u in rows.all()
    ]
