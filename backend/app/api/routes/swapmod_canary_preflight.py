from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from backend.app.models.user import User
from backend.app.schemas.swapmod_canary_preflight import SwapmodCanaryPreflightPackageRequest
from backend.app.services.swapmod_canary_preflight import (
    SwapmodCanaryPreflightError,
    swapmod_canary_preflight_service,
)

router = APIRouter(prefix="/plate-change-3mf/swapmod-canary-preflight", tags=["plate-change-3mf"])


def _preflight_flags() -> dict[str, object]:
    return {
        "enabled": settings.farm_swapmod_canary_preflight_enabled,
        "require_human_confirmation": settings.farm_swapmod_canary_preflight_require_human_confirmation,
        "single_printer_only": settings.farm_swapmod_canary_preflight_single_printer_only,
    }


def _require_enabled() -> None:
    if not settings.farm_swapmod_canary_preflight_enabled:
        raise HTTPException(status_code=404, detail="SwapMod canary preflight is disabled")


def _error_detail(exc: SwapmodCanaryPreflightError) -> dict[str, str]:
    return {"code": exc.code, "message": exc.message}


@router.get("/status")
async def get_swapmod_canary_preflight_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return swapmod_canary_preflight_service.status_snapshot(**_preflight_flags())


@router.post("/packages", status_code=202)
async def create_swapmod_canary_preflight_package(
    body: SwapmodCanaryPreflightPackageRequest,
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    try:
        return swapmod_canary_preflight_service.create_package(
            body.model_dump(),
            **_preflight_flags(),
        )
    except SwapmodCanaryPreflightError as exc:
        status_code = 404 if exc.code == "feature_disabled" else 400
        raise HTTPException(status_code=status_code, detail=_error_detail(exc)) from exc
