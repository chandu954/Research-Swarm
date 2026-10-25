"""Plugin configuration/execution and provider management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.auth.tenant import TenantContext, resolve_tenant_dependencies
from backend.db.models import Provider, User
from backend.db.schemas import (
    PluginConfigRequest,
    PluginStatus,
    ProviderCreate,
    ProviderListResponse,
    ProviderResponse,
    ProviderUpdate,
)
from backend.db.session import get_session

router = APIRouter(tags=["plugins"])


def _registry():
    """Resolve the registry through main for backwards-compatible patching."""
    from backend.api import main as main_module

    return main_module.get_plugin_registry()


# ═══════════════════════════════════════════════════════════════
# PLUGINS
# ═══════════════════════════════════════════════════════════════


@router.get("/plugins", response_model=list[PluginStatus])
async def list_plugins():
    registry = _registry()
    return [
        PluginStatus(
            name=spec.name,
            configured=registry.is_configured(spec.name),
            actions=spec.tags,
        )
        for spec in registry.list_plugins()
    ]


@router.post("/plugins/{name}/configure")
async def configure_plugin(
    name: str,
    req: PluginConfigRequest,
    current_user: User = Depends(get_current_user),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    """Configure a plugin, restricted to the plugin's declared contract.

    Only configuration keys declared in the plugin's config_schema are
    accepted; unknown keys are rejected instead of silently mutating
    shared plugin state.
    """
    registry = _registry()
    plugin = registry.get(name)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")

    config_schema = plugin.spec.config_schema or {}
    if config_schema:
        undeclared = set(req.config) - set(config_schema)
        if undeclared:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown configuration keys for plugin '{name}': {sorted(undeclared)}",
            )
    if hasattr(plugin, "_config"):
        plugin._config.update(req.config)
    logger.info(
        f"Plugin '{name}' configured by user {current_user.id} (org {ctx.organization_id})"
    )
    return {"status": "configured", "name": name}


@router.post("/plugins/{name}/execute")
async def execute_plugin(
    name: str,
    action: str = Query(...),
    current_user: User = Depends(get_current_user),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
    request: Request = None,
):
    """Execute a plugin action, bound to the plugin's declared contract.

    Invocation is restricted to actions declared in the plugin's spec.tags
    (the declared contract); undeclared actions are rejected. Kwargs still
    pass through so each plugin's own signature validation applies.
    """
    registry = _registry()
    plugin = registry.get(name)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")

    spec = plugin.spec
    if spec.tags and action not in spec.tags:
        raise HTTPException(
            status_code=400,
            detail=f"Action '{action}' is not a declared action of plugin '{name}'",
        )
    if not plugin.is_configured():
        raise HTTPException(
            status_code=400, detail=f"Plugin '{name}' is not configured"
        )

    try:
        body = {}
        if (
            request is not None
            and request.headers.get("content-type") == "application/json"
        ):
            body = await request.json()
        result = await registry.execute(name, action, **body)
        return {"status": "ok", "name": name, "action": action, "result": result}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# PROVIDERS
# ═══════════════════════════════════════════════════════════════


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers():
    registry = _registry()
    return ProviderListResponse(
        builtin=registry.list_all(),
        custom=[],
    )


@router.get("/providers/types")
async def list_provider_types():
    """Return available built-in providers grouped by type."""
    registry = _registry()
    return registry.list_all()


@router.post("/providers", response_model=ProviderResponse)
async def create_provider(
    req: ProviderCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    existing = await session.execute(
        select(Provider).where(
            Provider.organization_id == ctx.organization_id,
            Provider.name == req.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail=f"Provider '{req.name}' already exists"
        )

    provider = Provider(
        name=req.name,
        provider_type=req.provider_type,
        provider_key=req.provider_key,
        config=req.config,
        organization_id=ctx.organization_id,
        created_by=current_user.id,
    )
    session.add(provider)
    await session.commit()
    await session.refresh(provider)
    return provider


@router.get("/providers/{provider_id}", response_model=ProviderResponse)
async def get_provider(
    provider_id: str,
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Provider).where(
            Provider.id == provider_id,
            Provider.organization_id == ctx.organization_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.patch("/providers/{provider_id}", response_model=ProviderResponse)
async def update_provider(
    provider_id: str,
    req: ProviderUpdate,
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Provider).where(
            Provider.id == provider_id,
            Provider.organization_id == ctx.organization_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if req.name is not None:
        provider.name = req.name
    if req.config is not None:
        provider.config = req.config
    if req.is_active is not None:
        provider.is_active = req.is_active

    await session.commit()
    await session.refresh(provider)
    return provider


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: str,
    session: AsyncSession = Depends(get_session),
    ctx: TenantContext = Depends(resolve_tenant_dependencies),
):
    result = await session.execute(
        select(Provider).where(
            Provider.id == provider_id,
            Provider.organization_id == ctx.organization_id,
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    await session.delete(provider)
    await session.commit()
    return {"status": "deleted"}
