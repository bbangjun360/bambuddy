from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.swapmod_state_machine import SwapmodStateMachineCycle
from backend.app.services.bed_automation import MANUAL_REVIEW_REQUIRED, READY_FOR_NEXT_PRINT
from backend.app.services.swapmod_state_machine import (
    BLOCKED_TIMEOUT as SWAPMOD_BLOCKED_TIMEOUT,
    BLOCKED_UNKNOWN_STATE as SWAPMOD_BLOCKED_UNKNOWN_STATE,
    MANUAL_REVIEW_REQUIRED as SWAPMOD_MANUAL_REVIEW_REQUIRED,
    READY_FOR_NEXT_PRINT as SWAPMOD_READY_FOR_NEXT_PRINT,
)

HANDOFF_READY_RECORDED = "READY_RECORDED"
HANDOFF_MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"

_READY_HANDOFF_EVENT = "SWAPMOD_READY_FOR_NEXT_PRINT_HANDOFF"
_MANUAL_REVIEW_HANDOFF_EVENT = "SWAPMOD_MANUAL_REVIEW_HANDOFF"


class SwapmodBedReadinessError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def swapmod_bed_cycle_key(*, source_cycle_key: str) -> str:
    return f"swapmod-bed-readiness:{source_cycle_key}"


def swapmod_bed_readiness_status(
    *,
    enabled: bool,
    bed_automation_enabled: bool,
    bed_automation_dry_run: bool,
) -> dict[str, object]:
    return {
        "mode": "SWAPMOD_BED_READINESS_HANDOFF_ONLY",
        "enabled": enabled,
        "bed_automation_enabled": bed_automation_enabled,
        "bed_automation_dry_run": bed_automation_dry_run,
        "records_ready_only_after_swapmod_ready": True,
        "manual_review_preserved": True,
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }


async def record_swapmod_bed_readiness(
    db: AsyncSession,
    cycle: SwapmodStateMachineCycle,
    *,
    handoff_key: str,
    printer_id: int,
    enabled: bool,
    bed_automation_enabled: bool,
    bed_automation_dry_run: bool,
) -> dict[str, object]:
    _validate_flags(
        enabled=enabled,
        bed_automation_enabled=bed_automation_enabled,
        bed_automation_dry_run=bed_automation_dry_run,
    )
    _validate_printer(cycle, printer_id=printer_id)

    bed_cycle_key = swapmod_bed_cycle_key(source_cycle_key=cycle.cycle_key)
    existing = await _get_bed_cycle(db, bed_cycle_key=bed_cycle_key)
    if existing is not None:
        return _public_handoff(cycle, existing, handoff_status=_status_for_bed_cycle(existing))

    source_requires_manual_review = cycle.manual_review_required or cycle.state in {
        SWAPMOD_MANUAL_REVIEW_REQUIRED,
        SWAPMOD_BLOCKED_TIMEOUT,
        SWAPMOD_BLOCKED_UNKNOWN_STATE,
    }
    source_ready = cycle.state == SWAPMOD_READY_FOR_NEXT_PRINT and bool(cycle.ready_for_next_print)

    if not source_ready and not source_requires_manual_review:
        raise SwapmodBedReadinessError(
            "swapmod_cycle_not_ready",
            "SwapMod cycle must be READY_FOR_NEXT_PRINT before bed readiness handoff",
        )

    if source_requires_manual_review:
        bed_cycle = _new_bed_cycle(
            source=cycle,
            bed_cycle_key=bed_cycle_key,
            handoff_key=handoff_key,
            printer_id=printer_id,
            dry_run=bed_automation_dry_run,
            state=MANUAL_REVIEW_REQUIRED,
            ready_for_next_print=False,
            manual_review_required=True,
            blocked_reason="SwapMod source cycle requires manual review before bed readiness handoff",
            event=_MANUAL_REVIEW_HANDOFF_EVENT,
        )
        handoff_status = HANDOFF_MANUAL_REVIEW_REQUIRED
    else:
        bed_cycle = _new_bed_cycle(
            source=cycle,
            bed_cycle_key=bed_cycle_key,
            handoff_key=handoff_key,
            printer_id=printer_id,
            dry_run=bed_automation_dry_run,
            state=READY_FOR_NEXT_PRINT,
            ready_for_next_print=True,
            manual_review_required=False,
            blocked_reason=None,
            event=_READY_HANDOFF_EVENT,
        )
        handoff_status = HANDOFF_READY_RECORDED

    try:
        async with db.begin_nested():
            db.add(bed_cycle)
            await db.flush()
    except IntegrityError:
        existing_after_race = await _get_bed_cycle(db, bed_cycle_key=bed_cycle_key)
        if existing_after_race is None:
            raise
        return _public_handoff(cycle, existing_after_race, handoff_status=_status_for_bed_cycle(existing_after_race))

    await db.refresh(bed_cycle)
    return _public_handoff(cycle, bed_cycle, handoff_status=handoff_status)


async def _get_bed_cycle(db: AsyncSession, *, bed_cycle_key: str) -> BedAutomationCycle | None:
    result = await db.execute(select(BedAutomationCycle).where(BedAutomationCycle.cycle_key == bed_cycle_key))
    return result.scalar_one_or_none()


def _validate_flags(*, enabled: bool, bed_automation_enabled: bool, bed_automation_dry_run: bool) -> None:
    if not enabled:
        raise SwapmodBedReadinessError("handoff_disabled", "SwapMod bed readiness handoff is disabled")
    if not bed_automation_enabled:
        raise SwapmodBedReadinessError("bed_automation_disabled", "Bed automation must be enabled for handoff")
    if not bed_automation_dry_run:
        raise SwapmodBedReadinessError("bed_automation_dry_run_required", "Bed automation handoff is dry-run only")


def _validate_printer(cycle: SwapmodStateMachineCycle, *, printer_id: int) -> None:
    if cycle.printer_id is None:
        raise SwapmodBedReadinessError("printer_missing", "SwapMod cycle printer is required for bed readiness handoff")
    if cycle.printer_id != printer_id:
        raise SwapmodBedReadinessError("printer_mismatch", "requested printer does not match SwapMod cycle printer")


def _new_bed_cycle(
    *,
    source: SwapmodStateMachineCycle,
    bed_cycle_key: str,
    handoff_key: str,
    printer_id: int,
    dry_run: bool,
    state: str,
    ready_for_next_print: bool,
    manual_review_required: bool,
    blocked_reason: str | None,
    event: str,
) -> BedAutomationCycle:
    return BedAutomationCycle(
        cycle_key=bed_cycle_key,
        printer_id=printer_id,
        source_print_run_id=source.source_print_run_id,
        state=state,
        dry_run=dry_run,
        ready_for_next_print=ready_for_next_print,
        manual_review_required=manual_review_required,
        blocked_reason=blocked_reason,
        seen_event_ids=[f"swapmod-bed-readiness:{handoff_key}"],
        transition_log=[
            {
                "event": event,
                "event_id": f"swapmod-bed-readiness:{handoff_key}",
                "from_state": None,
                "to_state": state,
                "source_cycle_key": source.cycle_key,
                "source_state": source.state,
                "reason": blocked_reason,
            }
        ],
        transition_count=1,
    )


def _status_for_bed_cycle(cycle: BedAutomationCycle) -> str:
    if cycle.manual_review_required or cycle.state == MANUAL_REVIEW_REQUIRED:
        return HANDOFF_MANUAL_REVIEW_REQUIRED
    return HANDOFF_READY_RECORDED


def _public_handoff(
    source: SwapmodStateMachineCycle,
    bed_cycle: BedAutomationCycle,
    *,
    handoff_status: str,
) -> dict[str, object]:
    return {
        "handoff_status": handoff_status,
        "source_cycle_key": source.cycle_key,
        "source_state": source.state,
        "source_ready_for_next_print": source.ready_for_next_print,
        "source_manual_review_required": source.manual_review_required,
        "bed_cycle_id": bed_cycle.id,
        "bed_cycle_key": bed_cycle.cycle_key,
        "bed_state": bed_cycle.state,
        "printer_id": bed_cycle.printer_id,
        "source_print_run_id": bed_cycle.source_print_run_id,
        "dry_run": bed_cycle.dry_run,
        "ready_for_next_print": bed_cycle.ready_for_next_print,
        "manual_review_required": bed_cycle.manual_review_required,
        "blocked_reason": bed_cycle.blocked_reason,
        "transition_count": int(bed_cycle.transition_count or 0),
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }
