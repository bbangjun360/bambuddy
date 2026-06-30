from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.swapmod_state_machine import SwapmodStateMachineCycle
from backend.app.services.bed_automation import MANUAL_REVIEW_REQUIRED, READY_FOR_NEXT_PRINT
from backend.app.services.swapmod_bed_readiness import swapmod_bed_cycle_key
from backend.app.services.swapmod_state_machine import READY_FOR_NEXT_PRINT as SWAPMOD_READY_FOR_NEXT_PRINT

NEXT_PRINT_GATE_READY = "ready"
NEXT_PRINT_GATE_BLOCKED = "blocked"


class SwapmodNextPrintGateError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def swapmod_next_print_gate_status(*, enabled: bool, bed_automation_enabled: bool) -> dict[str, object]:
    return {
        "mode": "SWAPMOD_NEXT_PRINT_GATE_EVALUATE_ONLY",
        "enabled": enabled,
        "bed_automation_enabled": bed_automation_enabled,
        "evaluate_only": True,
        "requires_swapmod_ready": True,
        "requires_bed_ready": True,
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }


async def evaluate_swapmod_next_print_gate(
    db: AsyncSession,
    cycle: SwapmodStateMachineCycle,
    *,
    gate_key: str,
    printer_id: int,
    enabled: bool,
    bed_automation_enabled: bool,
) -> dict[str, object]:
    if not enabled:
        raise SwapmodNextPrintGateError("next_print_gate_disabled", "SwapMod next-print gate is disabled")
    if not bed_automation_enabled:
        raise SwapmodNextPrintGateError("bed_automation_disabled", "Bed automation must be enabled for next-print gate")

    bed_cycle_key = swapmod_bed_cycle_key(source_cycle_key=cycle.cycle_key)
    bed_cycle = await _get_bed_cycle(db, bed_cycle_key=bed_cycle_key)
    blocked_reasons = _blocked_reasons(cycle, bed_cycle, printer_id=printer_id)
    gate_status = NEXT_PRINT_GATE_READY if not blocked_reasons else NEXT_PRINT_GATE_BLOCKED

    return {
        "gate_key": gate_key,
        "gate_status": gate_status,
        "next_print_allowed": gate_status == NEXT_PRINT_GATE_READY,
        "blocked_reasons": blocked_reasons,
        "evaluate_only": True,
        "source_cycle_key": cycle.cycle_key,
        "source_state": cycle.state,
        "source_ready_for_next_print": cycle.ready_for_next_print,
        "source_manual_review_required": cycle.manual_review_required,
        "printer_id": printer_id,
        "source_printer_id": cycle.printer_id,
        "source_print_run_id": cycle.source_print_run_id,
        "bed_cycle_key": bed_cycle_key,
        "bed_cycle_id": bed_cycle.id if bed_cycle is not None else None,
        "bed_state": bed_cycle.state if bed_cycle is not None else None,
        "bed_ready_for_next_print": bool(bed_cycle.ready_for_next_print) if bed_cycle is not None else False,
        "bed_manual_review_required": bool(bed_cycle.manual_review_required) if bed_cycle is not None else False,
        "bed_blocked_reason": bed_cycle.blocked_reason if bed_cycle is not None else None,
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }


async def _get_bed_cycle(db: AsyncSession, *, bed_cycle_key: str) -> BedAutomationCycle | None:
    result = await db.execute(select(BedAutomationCycle).where(BedAutomationCycle.cycle_key == bed_cycle_key))
    return result.scalar_one_or_none()


def _blocked_reasons(
    cycle: SwapmodStateMachineCycle,
    bed_cycle: BedAutomationCycle | None,
    *,
    printer_id: int,
) -> list[str]:
    reasons: list[str] = []

    if cycle.printer_id is None:
        reasons.append("printer_missing")
    elif cycle.printer_id != printer_id:
        reasons.append("printer_mismatch")

    if cycle.manual_review_required:
        reasons.append("swapmod_manual_review_required")
    if cycle.state != SWAPMOD_READY_FOR_NEXT_PRINT or not cycle.ready_for_next_print:
        reasons.append("swapmod_cycle_not_ready")

    if bed_cycle is None:
        reasons.append("bed_readiness_record_missing")
        return reasons

    if bed_cycle.printer_id is None:
        reasons.append("bed_printer_missing")
    elif bed_cycle.printer_id != printer_id:
        reasons.append("bed_printer_mismatch")
    if bed_cycle.manual_review_required or bed_cycle.state == MANUAL_REVIEW_REQUIRED:
        reasons.append("bed_manual_review_required")
    if bed_cycle.state != READY_FOR_NEXT_PRINT or not bed_cycle.ready_for_next_print:
        reasons.append("bed_not_ready_for_next_print")

    return reasons
