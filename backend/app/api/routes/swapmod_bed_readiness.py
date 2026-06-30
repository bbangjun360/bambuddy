from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.permissions import Permission
from backend.app.models.user import User
from backend.app.schemas.swapmod_bed_readiness import SwapmodBedReadinessRecordRequest
from backend.app.services.swapmod_bed_readiness import (
    SwapmodBedReadinessError,
    record_swapmod_bed_readiness,
    swapmod_bed_readiness_status,
)
from backend.app.services.swapmod_state_machine import get_swapmod_cycle

router = APIRouter(prefix="/swapmod-bed-readiness", tags=["swapmod-bed-readiness"])


def _require_enabled() -> None:
    if not settings.farm_swapmod_bed_readiness_handoff_enabled:
        raise HTTPException(status_code=404, detail="SwapMod bed readiness handoff is disabled")
    if not settings.farm_swapmod_state_machine_enabled:
        raise HTTPException(
            status_code=400,
            detail={"code": "swapmod_state_machine_disabled", "message": "SwapMod state machine must be enabled"},
        )
    if not settings.farm_bed_automation_enabled:
        raise HTTPException(
            status_code=400,
            detail={"code": "bed_automation_disabled", "message": "Bed automation must be enabled"},
        )
    if not settings.farm_bed_automation_dry_run:
        raise HTTPException(
            status_code=400,
            detail={"code": "bed_automation_dry_run_required", "message": "Bed automation handoff is dry-run only"},
        )


@router.get("/status")
async def get_swapmod_bed_readiness_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return swapmod_bed_readiness_status(
        enabled=settings.farm_swapmod_bed_readiness_handoff_enabled,
        bed_automation_enabled=settings.farm_bed_automation_enabled,
        bed_automation_dry_run=settings.farm_bed_automation_dry_run,
    )


@router.post("/cycles/{cycle_key}/records", status_code=202)
async def create_swapmod_bed_readiness_record(
    cycle_key: str,
    body: SwapmodBedReadinessRecordRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    cycle = await get_swapmod_cycle(db, cycle_key=cycle_key)
    if cycle is None:
        raise HTTPException(status_code=404, detail="SwapMod state machine cycle not found")
    try:
        return await record_swapmod_bed_readiness(
            db,
            cycle,
            handoff_key=body.handoff_key,
            printer_id=body.printer_id,
            enabled=settings.farm_swapmod_bed_readiness_handoff_enabled,
            bed_automation_enabled=settings.farm_bed_automation_enabled,
            bed_automation_dry_run=settings.farm_bed_automation_dry_run,
        )
    except SwapmodBedReadinessError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
