"""Tenant resolution middleware — resolves org/workspace/project from authenticated context.

Never trusts values sent by the frontend. Resolves permissions from server-side context.
"""
from __future__ import annotations
from typing import Optional
from contextvars import ContextVar
from dataclasses import dataclass, field

from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.session import get_session
from backend.db.models import (
    User, Organization, OrganizationMember,
    Workspace, Project,
)
from backend.auth.dependencies import get_current_user


@dataclass
class TenantContext:
    organization_id: str
    organization_slug: str = ""
    workspace_id: Optional[str] = None
    workspace_slug: Optional[str] = None
    project_id: Optional[str] = None
    project_slug: Optional[str] = None
    user_id: str = ""
    user_role: str = "viewer"
    permissions: dict[str, bool] = field(default_factory=dict)


_tenant_context: ContextVar[Optional[TenantContext]] = ContextVar("tenant_context", default=None)


def get_tenant_context() -> Optional[TenantContext]:
    return _tenant_context.get()


def set_tenant_context(ctx: TenantContext) -> None:
    _tenant_context.set(ctx)


def reset_tenant_context() -> None:
    _tenant_context.set(None)


def _slugify(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))


async def resolve_org_from_subdomain(request: Request) -> Optional[str]:
    host = request.headers.get("host", "")
    parts = host.split(".")
    if len(parts) >= 2:
        subdomain = parts[0].lower()
        if subdomain not in ("www", "app", "api", "localhost", ""):
            return subdomain
    return None


async def resolve_tenant_dependencies(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    org_id = request.headers.get("X-Organization-Id", "")
    org_slug = request.headers.get("X-Organization-Slug", "")
    ws_id = request.headers.get("X-Workspace-Id", "")
    proj_id = request.headers.get("X-Project-Id", "")

    subdomain_org = await resolve_org_from_subdomain(request)

    resolved_org_id: Optional[str] = None
    resolved_org_slug: Optional[str] = None

    if org_id:
        stmt = select(Organization).where(
            Organization.id == org_id,
            Organization.is_active == True,
        )
        result = await session.execute(stmt)
        org = result.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        membership = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == user.id,
            )
        )
        if not membership.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a member of this organization")
        resolved_org_id = org.id
        resolved_org_slug = org.slug
    elif org_slug:
        stmt = select(Organization).where(
            Organization.slug == org_slug,
            Organization.is_active == True,
        )
        result = await session.execute(stmt)
        org = result.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        membership = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org.id,
                OrganizationMember.user_id == user.id,
            )
        )
        if not membership.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Not a member of this organization")
        resolved_org_id = org.id
        resolved_org_slug = org.slug
    elif subdomain_org:
        stmt = select(Organization).where(
            Organization.slug == subdomain_org,
            Organization.is_active == True,
        )
        result = await session.execute(stmt)
        org = result.scalar_one_or_none()
        if org:
            membership = await session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == org.id,
                    OrganizationMember.user_id == user.id,
                )
            )
            if membership.scalar_one_or_none():
                resolved_org_id = org.id
                resolved_org_slug = org.slug

    if not resolved_org_id:
        memberships = await session.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user.id,
            ).limit(1)
        )
        first = memberships.scalar_one_or_none()
        if first:
            resolved_org_id = first.organization_id
            org_result = await session.execute(
                select(Organization).where(Organization.id == first.organization_id)
            )
            org = org_result.scalar_one_or_none()
            if org:
                resolved_org_slug = org.slug

    if not resolved_org_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "organization_required", "message": "We need to set up your workspace before you can start researching."},
        )

    resolved_ws_id: Optional[str] = None
    resolved_ws_slug: Optional[str] = None
    if ws_id:
        stmt = select(Workspace).where(
            Workspace.id == ws_id,
            Workspace.organization_id == resolved_org_id,
            Workspace.is_active == True,
        )
        result = await session.execute(stmt)
        ws = result.scalar_one_or_none()
        if ws:
            resolved_ws_id = ws.id
            resolved_ws_slug = ws.slug

    resolved_proj_id: Optional[str] = None
    resolved_proj_slug: Optional[str] = None
    if proj_id:
        stmt = select(Project).where(
            Project.id == proj_id,
            Project.organization_id == resolved_org_id,
            Project.is_active == True,
        )
        if resolved_ws_id:
            stmt = stmt.where(Project.workspace_id == resolved_ws_id)
        result = await session.execute(stmt)
        proj = result.scalar_one_or_none()
        if proj:
            resolved_proj_id = proj.id
            resolved_proj_slug = proj.slug

    membership = await session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == resolved_org_id,
            OrganizationMember.user_id == user.id,
        )
    )
    org_member = membership.scalar_one_or_none()
    user_role = org_member.role if org_member else "viewer"

    permissions = _resolve_permissions(user_role)

    ctx = TenantContext(
        organization_id=resolved_org_id,
        organization_slug=resolved_org_slug or "",
        workspace_id=resolved_ws_id,
        workspace_slug=resolved_ws_slug,
        project_id=resolved_proj_id,
        project_slug=resolved_proj_slug,
        user_id=user.id,
        user_role=user_role,
        permissions=permissions,
    )
    set_tenant_context(ctx)
    return ctx


async def resolve_optional_tenant(
    request: Request,
    user: Optional[User] = None,
    session: AsyncSession = Depends(get_session),
) -> Optional[TenantContext]:
    if not user:
        return None
    try:
        return await resolve_tenant_dependencies(request, user, session)
    except HTTPException:
        return None


def _resolve_permissions(role: str) -> dict[str, bool]:
    base = {
        "view_own": True,
        "edit_own": True,
        "delete_own": True,
    }
    if role == "viewer":
        return {**base, "view_org": True, "view_workspace": True}
    if role == "researcher":
        return {**base, "view_org": True, "view_workspace": True,
                "create_research": True, "upload_documents": True}
    if role == "manager":
        return {**base, "view_org": True, "view_workspace": True,
                "create_research": True, "upload_documents": True,
                "manage_members": True, "manage_projects": True,
                "view_billing": True}
    if role == "admin":
        return {**base, "view_org": True, "view_workspace": True,
                "create_research": True, "upload_documents": True,
                "manage_members": True, "manage_projects": True,
                "manage_workspaces": True, "view_billing": True,
                "manage_api_keys": True, "view_audit_logs": True}
    if role == "owner":
        return {**base, "view_org": True, "view_workspace": True,
                "create_research": True, "upload_documents": True,
                "manage_members": True, "manage_projects": True,
                "manage_workspaces": True, "view_billing": True,
                "manage_api_keys": True, "view_audit_logs": True,
                "delete_organization": True, "manage_billing": True}
    return base


def require_permission(permission: str):
    async def dependency(ctx: TenantContext = Depends(resolve_tenant_dependencies)) -> TenantContext:
        if not ctx.permissions.get(permission, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission}",
            )
        return ctx
    return dependency


def tenant_filter(model) -> list:
    ctx = get_tenant_context()
    if not ctx:
        return []
    filters = [model.organization_id == ctx.organization_id]
    if ctx.workspace_id:
        filters.append(model.workspace_id == ctx.workspace_id)
    if ctx.project_id:
        filters.append(model.project_id == ctx.project_id)
    return filters
