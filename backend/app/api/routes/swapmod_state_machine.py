from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.permissions import Permission
from backend.app.models.user import User
from backend.app.schemas.swapmod_state_machine import (
    SwapmodStateMachineCycleCreate,
    SwapmodStateMachineEventRequest,
)
from backend.app.services.swapmod_state_machine import (
    apply_swapmod_event,
    create_swapmod_cycle,
    get_swapmod_cycle,
    public_swapmod_cycle,
    swapmod_state_machine_status,
)

router = APIRouter(prefix="/swapmod-state-machine", tags=["swapmod-state-machine"])


def _require_enabled() -> None:
    if not settings.farm_swapmod_state_machine_enabled:
        raise HTTPException(status_code=404, detail="SwapMod state machine is disabled")


@router.get("/status")
async def get_swapmod_state_machine_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return swapmod_state_machine_status(
        enabled=settings.farm_swapmod_state_machine_enabled,
        dry_run=settings.farm_swapmod_state_machine_dry_run,
    )


@router.post("/cycles", status_code=202)
async def create_swapmod_state_machine_cycle(
    body: SwapmodStateMachineCycleCreate,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    cycle = await create_swapmod_cycle(
        db,
        cycle_key=body.cycle_key,
        printer_id=body.printer_id,
        source_print_run_id=body.source_print_run_id,
    )
    return public_swapmod_cycle(cycle)


@router.post("/cycles/{cycle_key}/events")
async def apply_swapmod_state_machine_event(
    cycle_key: str,
    body: SwapmodStateMachineEventRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    cycle = await get_swapmod_cycle(db, cycle_key=cycle_key)
    if cycle is None:
        raise HTTPException(status_code=404, detail="SwapMod state machine cycle not found")
    cycle = await apply_swapmod_event(
        db,
        cycle,
        body.event,
        event_id=body.event_id,
        step=body.step,
        verification_source=body.verification_source,
        verification_result=body.verification_result,
        note=body.note,
    )
    return public_swapmod_cycle(cycle)
