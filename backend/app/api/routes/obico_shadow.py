from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from backend.app.models.user import User
from backend.app.services.obico_shadow import obico_shadow_service

router = APIRouter(prefix="/obico-shadow", tags=["obico-shadow"])


def _require_enabled() -> None:
    if not settings.farm_obico_shadow_enabled:
        raise HTTPException(status_code=404, detail="Obico shadow mode is disabled")


@router.post("/events", status_code=202)
async def ingest_shadow_event(
    payload: dict[str, Any],
    _: User | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_UPDATE),
):
    _require_enabled()
    return obico_shadow_service.ingest_event(payload)


@router.get("/status")
async def get_shadow_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_READ),
):
    _require_enabled()
    return obico_shadow_service.status_snapshot()


@router.get("/metrics", response_class=Response)
async def get_shadow_metrics(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_READ),
):
    _require_enabled()
    return Response(content=obico_shadow_service.render_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")
