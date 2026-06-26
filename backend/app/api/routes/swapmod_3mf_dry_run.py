from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from backend.app.models.user import User
from backend.app.schemas.swapmod_3mf_dry_run import Swapmod3mfDryRunPlanRequest
from backend.app.services.swapmod_3mf_dry_run import (
    Swapmod3mfDryRunError,
    default_swapmod_sample_root,
    swapmod_3mf_dry_run_service,
)

router = APIRouter(prefix="/plate-change-3mf/swapmod-dry-run", tags=["plate-change-3mf"])


def _require_enabled() -> None:
    if not settings.farm_swapmod_3mf_dry_run_enabled:
        raise HTTPException(status_code=404, detail="SwapMod 3MF dry-run workflow is disabled")


def _allowed_roots():
    return [settings.farm_swapmod_3mf_sample_root or default_swapmod_sample_root()]


def _error_detail(exc: Swapmod3mfDryRunError) -> dict[str, str]:
    return {"code": exc.code, "message": exc.message}


@router.get("/status")
async def get_swapmod_dry_run_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return swapmod_3mf_dry_run_service.status_snapshot(
        enabled=settings.farm_swapmod_3mf_dry_run_enabled,
        dry_run=settings.farm_swapmod_3mf_dry_run_required,
        allowed_roots=_allowed_roots(),
    )


@router.post("/plans", status_code=202)
async def create_swapmod_dry_run_plan(
    body: Swapmod3mfDryRunPlanRequest,
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    try:
        return swapmod_3mf_dry_run_service.create_plan(
            original_path=body.original_path,
            swapmod_path=body.swapmod_path,
            enabled=settings.farm_swapmod_3mf_dry_run_enabled,
            dry_run=settings.farm_swapmod_3mf_dry_run_required,
            request_dry_run=body.dry_run,
            allowed_roots=_allowed_roots(),
            repository_root=settings.base_dir,
            expected_printer_model_family=body.expected_printer_model_family,
        )
    except Swapmod3mfDryRunError as exc:
        status_code = 404 if exc.code == "feature_disabled" else 400
        raise HTTPException(status_code=status_code, detail=_error_detail(exc)) from exc
