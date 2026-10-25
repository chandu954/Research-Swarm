"""Workspace, project, and workspace-member endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.common import slugify
from backend.auth.dependencies import get_current_user
from backend.auth.tenant import TenantContext, require_org
from backend.db.models import (
    Project,
    User,
    Workspace,
    WorkspaceMember,
)
from backend.db.schemas import (
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from backend.db.session import get_session

router = APIRouter(tags=["workspaces"])


# ── Workspaces ──────────────────────────────────────────────────


@router.post(
    "/organizations/{org_id}/workspaces",
    response_model=WorkspaceResponse,
    status_code=201,
)
async def create_workspace(
    org_id: str,
    body: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    slug = body.slug or slugify(body.name)
    result = await session.execute(
        select(Workspace).where(
            Workspace.organization_id == org_id,
            Workspace.slug == slug,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="A workspace with this slug already exists"
        )

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


@router.get(
    "/organizations/{org_id}/workspaces", response_model=list[WorkspaceResponse]
)
async def list_workspaces(
    org_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    member_count_subq = (
        select(
            WorkspaceMember.workspace_id, func.count(WorkspaceMember.id).label("cnt")
        )
        .group_by(WorkspaceMember.workspace_id)
        .subquery()
    )
    result = await session.execute(
        select(
            Workspace,
            func.coalesce(member_count_subq.c.cnt, 0).label("member_count"),
        )
        .outerjoin(
            member_count_subq,
            member_count_subq.c.workspace_id == Workspace.id,
        )
        .join(
            WorkspaceMember,
            WorkspaceMember.workspace_id == Workspace.id,
        )
        .where(
            Workspace.organization_id == org_id,
            WorkspaceMember.user_id == current_user.id,
            Workspace.is_active.is_(True),
        )
    )
    rows = result.all()
    return [
        WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            description=ws.description,
            organization_id=ws.organization_id,
            owner_id=ws.owner_id,
            member_count=member_count,
            is_active=ws.is_active,
            created_at=ws.created_at,
        )
        for ws, member_count in rows
    ]


@router.get(
    "/organizations/{org_id}/workspaces/{ws_id}", response_model=WorkspaceResponse
)
async def get_workspace(
    org_id: str,
    ws_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    result = await session.execute(
        select(Workspace).where(
            Workspace.id == ws_id,
            Workspace.organization_id == org_id,
            Workspace.is_active.is_(True),
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


@router.patch(
    "/organizations/{org_id}/workspaces/{ws_id}", response_model=WorkspaceResponse
)
async def update_workspace(
    org_id: str,
    ws_id: str,
    body: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    result = await session.execute(
        select(Workspace).where(
            Workspace.id == ws_id,
            Workspace.organization_id == org_id,
            Workspace.is_active.is_(True),
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
    ctx: TenantContext = Depends(require_org),
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


@router.post(
    "/organizations/{org_id}/workspaces/{ws_id}/projects",
    response_model=ProjectResponse,
    status_code=201,
)
async def create_project(
    org_id: str,
    ws_id: str,
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    slug = body.slug or slugify(body.name)
    result = await session.execute(
        select(Project).where(
            Project.workspace_id == ws_id,
            Project.slug == slug,
            Project.is_active.is_(True),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="A project with this slug already exists"
        )

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


@router.get(
    "/organizations/{org_id}/workspaces/{ws_id}/projects",
    response_model=list[ProjectResponse],
)
async def list_projects(
    org_id: str,
    ws_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    result = await session.execute(
        select(Project).where(
            Project.workspace_id == ws_id,
            Project.organization_id == org_id,
            Project.is_active.is_(True),
        )
    )
    return [ProjectResponse.model_validate(p) for p in result.scalars().all()]


@router.get(
    "/organizations/{org_id}/workspaces/{ws_id}/projects/{proj_id}",
    response_model=ProjectResponse,
)
async def get_project(
    org_id: str,
    ws_id: str,
    proj_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    result = await session.execute(
        select(Project).where(
            Project.id == proj_id,
            Project.workspace_id == ws_id,
            Project.organization_id == org_id,
            Project.is_active.is_(True),
        )
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(proj)


@router.patch(
    "/organizations/{org_id}/workspaces/{ws_id}/projects/{proj_id}",
    response_model=ProjectResponse,
)
async def update_project(
    org_id: str,
    ws_id: str,
    proj_id: str,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    result = await session.execute(
        select(Project).where(
            Project.id == proj_id,
            Project.workspace_id == ws_id,
            Project.organization_id == org_id,
            Project.is_active.is_(True),
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
    ctx: TenantContext = Depends(require_org),
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


@router.get(
    "/organizations/{org_id}/workspaces/{ws_id}/members",
    response_model=list[MemberResponse],
)
async def list_workspace_members(
    org_id: str,
    ws_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(require_org),
):
    rows = await session.execute(
        select(WorkspaceMember, User)
        .join(
            User,
            User.id == WorkspaceMember.user_id,
        )
        .where(WorkspaceMember.workspace_id == ws_id)
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
