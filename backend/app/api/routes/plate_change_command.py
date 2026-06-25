from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.permissions import Permission
from backend.app.models.user import User
from backend.app.schemas.plate_change_command import PlateChangeDryRunCommandRequest
from backend.app.services.plate_change_command import (
    PlateChangeCommandError,
    plate_change_command_service,
)

router = APIRouter(prefix="/plate-change", tags=["plate-change"])


def _require_enabled() -> None:
    if not settings.farm_plate_change_command_enabled:
        raise HTTPException(status_code=404, detail="Plate-change command dry-run boundary is disabled")


def _require_safe_dry_run_runtime() -> None:
    if not settings.farm_plate_change_command_dry_run:
        raise HTTPException(
            status_code=400,
            detail={"code": "dry_run_required", "message": "Plate-change command boundary is dry-run only"},
        )
    if settings.farm_plate_change_allow_real_commands:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "real_commands_not_implemented",
                "message": "Real plate-change commands are not implemented in this Work Package",
            },
        )


def _error_detail(exc: PlateChangeCommandError) -> dict[str, str]:
    return {"code": exc.code, "message": exc.message}


@router.post("/dry-run-commands", status_code=202)
async def create_dry_run_commands(
    body: PlateChangeDryRunCommandRequest,
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    _require_safe_dry_run_runtime()
    try:
        return plate_change_command_service.create_dry_run(
            body.model_dump(mode="json"),
            global_dry_run=settings.farm_plate_change_command_dry_run,
            human_approval_required=settings.farm_plate_change_human_approval_required,
            single_printer_only=settings.farm_plate_change_single_printer_only,
            allow_real_commands=settings.farm_plate_change_allow_real_commands,
        )
    except PlateChangeCommandError as exc:
        raise HTTPException(status_code=400, detail=_error_detail(exc)) from exc


@router.get("/status")
async def get_plate_change_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return plate_change_command_service.status_snapshot(
        enabled=settings.farm_plate_change_command_enabled,
        dry_run=settings.farm_plate_change_command_dry_run,
        human_approval_required=settings.farm_plate_change_human_approval_required,
        single_printer_only=settings.farm_plate_change_single_printer_only,
        allow_real_commands=settings.farm_plate_change_allow_real_commands,
    )
