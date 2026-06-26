from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from backend.app.models.user import User
from backend.app.schemas.plate_change_3mf_postprocess import PlateChange3mfPostprocessPlanRequest
from backend.app.services.plate_change_3mf_postprocess import (
    PlateChange3mfPostprocessError,
    default_controlled_roots,
    plate_change_3mf_postprocess_service,
)

router = APIRouter(prefix="/plate-change-3mf", tags=["plate-change-3mf"])


def _require_enabled() -> None:
    if not settings.farm_plate_change_3mf_postprocess_enabled:
        raise HTTPException(status_code=404, detail="Plate-change 3MF post-processing prototype is disabled")


def _require_safe_dry_run_runtime() -> None:
    if not settings.farm_plate_change_3mf_postprocess_dry_run:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "dry_run_required",
                "message": "Plate-change 3MF post-processing prototype is dry-run only",
            },
        )


def _error_detail(exc: PlateChange3mfPostprocessError) -> dict[str, str]:
    return {"code": exc.code, "message": exc.message}


@router.post("/postprocess-plans", status_code=202)
async def create_postprocess_plan(
    body: PlateChange3mfPostprocessPlanRequest,
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    _require_safe_dry_run_runtime()
    try:
        return plate_change_3mf_postprocess_service.create_plan(
            source_path=body.source_path,
            enabled=settings.farm_plate_change_3mf_postprocess_enabled,
            dry_run=settings.farm_plate_change_3mf_postprocess_dry_run,
            request_dry_run=body.dry_run,
            allow_output_artifact=settings.farm_plate_change_3mf_allow_output_artifact,
            create_output_artifact=body.create_output_artifact,
            allowed_roots=default_controlled_roots(settings.base_dir),
        )
    except PlateChange3mfPostprocessError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(exc)) from exc


@router.get("/status")
async def get_postprocess_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return plate_change_3mf_postprocess_service.status_snapshot(
        enabled=settings.farm_plate_change_3mf_postprocess_enabled,
        dry_run=settings.farm_plate_change_3mf_postprocess_dry_run,
        allow_output_artifact=settings.farm_plate_change_3mf_allow_output_artifact,
    )
