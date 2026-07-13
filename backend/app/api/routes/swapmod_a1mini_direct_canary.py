from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.permissions import Permission
from backend.app.models.printer import Printer
from backend.app.models.user import User
from backend.app.schemas.swapmod_a1mini_direct_canary import SwapmodA1MiniDirectCanaryTransportRequest
from backend.app.services.printer_manager import printer_manager
from backend.app.services.swapmod_a1mini_direct_canary import (
    SwapmodA1MiniDirectCanaryError,
    swapmod_a1mini_direct_canary_service,
)
from backend.app.services.swapmod_state_machine import get_swapmod_cycle

router = APIRouter(prefix="/swapmod-a1-mini-direct-canary", tags=["swapmod-a1-mini-direct-canary"])


class PrinterManagerA1MiniDirectTransport:
    def get_status(self, printer_id: int) -> dict[str, object] | None:
        state = printer_manager.get_status(printer_id)
        if state is None:
            return None
        return {
            "state": state.state,
            "gcode_file": state.gcode_file,
        }

    def send_gcode(self, printer_id: int, gcode: str) -> bool:
        client = printer_manager.get_client(printer_id)
        if client is None:
            return False
        return bool(client.send_gcode(gcode))


def get_a1mini_direct_transport() -> PrinterManagerA1MiniDirectTransport:
    return PrinterManagerA1MiniDirectTransport()


def _require_direct_canary_target(printer_id: int) -> None:
    target_printer_id = settings.farm_swapmod_a1mini_direct_canary_target_printer_id
    if target_printer_id is None:
        raise HTTPException(status_code=404, detail="Named SwapMod A1 Mini direct canary printer is not configured")
    if int(printer_id) != int(target_printer_id):
        raise HTTPException(status_code=404, detail="Printer is not the named SwapMod A1 Mini direct canary")


def _require_direct_canary_enabled(printer_id: int) -> None:
    if not settings.farm_swapmod_a1mini_direct_canary_enabled:
        raise HTTPException(status_code=404, detail="SwapMod A1 Mini direct canary is disabled")
    if not settings.farm_swapmod_a1mini_direct_canary_allow_real_commands:
        raise HTTPException(status_code=404, detail="SwapMod A1 Mini direct canary real commands are disabled")
    _require_direct_canary_target(printer_id)


@router.get("/status")
async def get_swapmod_a1mini_direct_canary_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return swapmod_a1mini_direct_canary_service.status_snapshot(
        enabled=settings.farm_swapmod_a1mini_direct_canary_enabled,
        allow_real_commands=settings.farm_swapmod_a1mini_direct_canary_allow_real_commands,
        target_printer_id=settings.farm_swapmod_a1mini_direct_canary_target_printer_id,
        release_sequence_configured=bool(
            settings.farm_swapmod_a1mini_direct_canary_sequence_root
            and settings.farm_swapmod_a1mini_direct_canary_release_sequence_file
            and settings.farm_swapmod_a1mini_direct_canary_release_sequence_sha256
        ),
        load_sequence_configured=bool(
            settings.farm_swapmod_a1mini_direct_canary_sequence_root
            and settings.farm_swapmod_a1mini_direct_canary_load_sequence_file
            and settings.farm_swapmod_a1mini_direct_canary_load_sequence_sha256
        ),
    )


@router.get("/confirmation-preview")
async def get_swapmod_a1mini_direct_canary_confirmation_preview(
    printer_id: int,
    cycle_key: str,
    step: str,
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    """Read-only preview of the confirmation phrase + checklist for a step.

    Lets the UI display the server-provided phrase read-only before the operator
    ticks the checklist and confirms. Sends no printer command.
    """
    _require_direct_canary_target(printer_id)
    return swapmod_a1mini_direct_canary_service.confirmation_preview(
        printer_id=printer_id,
        cycle_key=cycle_key,
        step=step,
        release_sequence_sha256=settings.farm_swapmod_a1mini_direct_canary_release_sequence_sha256,
        load_sequence_sha256=settings.farm_swapmod_a1mini_direct_canary_load_sequence_sha256,
    )


@router.post("/cycles/{cycle_key}/transport-steps", status_code=202)
async def execute_swapmod_a1mini_direct_canary_transport_step(
    cycle_key: str,
    body: SwapmodA1MiniDirectCanaryTransportRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_direct_canary_enabled(body.printer_id)
    cycle = await get_swapmod_cycle(db, cycle_key=cycle_key)
    if cycle is None:
        raise HTTPException(status_code=404, detail="SwapMod state machine cycle not found")
    result = await db.execute(select(Printer).where(Printer.id == body.printer_id))
    printer = result.scalar_one_or_none()
    if printer is None:
        raise HTTPException(status_code=404, detail="Printer not found")
    try:
        return await swapmod_a1mini_direct_canary_service.execute_transport_step(
            db,
            cycle,
            canary_key=body.canary_key,
            printer_id=body.printer_id,
            printer_model=printer.model,
            step=body.step,
            operator_approved=body.operator_approved,
            operator_approval_phrase=body.operator_approval_phrase,
            checklist=body.checklist.model_dump(),
            enabled=settings.farm_swapmod_a1mini_direct_canary_enabled,
            allow_real_commands=settings.farm_swapmod_a1mini_direct_canary_allow_real_commands,
            target_printer_id=settings.farm_swapmod_a1mini_direct_canary_target_printer_id,
            sequence_root=settings.farm_swapmod_a1mini_direct_canary_sequence_root,
            release_sequence_file=settings.farm_swapmod_a1mini_direct_canary_release_sequence_file,
            release_sequence_sha256=settings.farm_swapmod_a1mini_direct_canary_release_sequence_sha256,
            load_sequence_file=settings.farm_swapmod_a1mini_direct_canary_load_sequence_file,
            load_sequence_sha256=settings.farm_swapmod_a1mini_direct_canary_load_sequence_sha256,
            transport=get_a1mini_direct_transport(),
        )
    except SwapmodA1MiniDirectCanaryError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
