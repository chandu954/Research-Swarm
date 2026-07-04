"""Health metrics endpoint for monitoring."""
from __future__ import annotations
import os
import time
from typing import Any
from fastapi import APIRouter

from backend.core.registry import get_plugin_registry

router = APIRouter(tags=["monitoring"])

_start_time = time.time()


@router.get("/metrics")
async def metrics() -> dict[str, Any]:
    """System metrics: uptime, registered plugins, configured state."""
    registry = get_plugin_registry()
    uptime = round(time.time() - _start_time)

    plugin_info: dict[str, list[dict[str, Any]]] = {}
    for ptype in registry.list_types():
        plugins = registry.list_plugins(ptype)
        plugin_info[ptype] = [
            {
                "name": p.name if hasattr(p, "name") and callable(p.name) else getattr(p, "name", str(p)),
                "version": p.version if hasattr(p, "version") and callable(p.version) else "?",
                "configured": registry.is_configured(ptype),
            }
            for p in (plugins or [])
        ]

    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "plugins": plugin_info,
        "python_version": os.sys.version.split()[0],
    }
