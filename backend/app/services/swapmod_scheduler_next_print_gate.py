from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.print_log import PrintLogEntry
from backend.app.models.swapmod_state_machine import SwapmodStateMachineCycle
from backend.app.services.swapmod_next_print_gate import evaluate_swapmod_next_print_gate

SCHEDULER_NEXT_PRINT_GATE_ALLOWED = "allowed"
SCHEDULER_NEXT_PRINT_GATE_BLOCKED = "blocked"


def scheduler_print_run_key(print_log_entry_id: int) -> str:
    return f"print_log:{print_log_entry_id}"


async def evaluate_scheduler_next_print_gate(
    db: AsyncSession,
    *,
    printer_id: int | None,
    enabled: bool,
    bed_automation_enabled: bool,
) -> dict[str, object]:
    if not enabled:
        return _allowed_payload(
            enforced=False,
            printer_id=printer_id,
            latest_print_log_id=None,
            latest_print_run_id=None,
            source_cycle_key=None,
            details={},
        )

    if printer_id is None:
        return _blocked_payload(
            blocked_reasons=["printer_missing"],
            printer_id=None,
            latest_print_log_id=None,
            latest_print_run_id=None,
            source_cycle_key=None,
            details={},
        )

    if not bed_automation_enabled:
        return _blocked_payload(
            blocked_reasons=["bed_automation_disabled"],
            printer_id=printer_id,
            latest_print_log_id=None,
            latest_print_run_id=None,
            source_cycle_key=None,
            details={},
        )

    latest_run = await _latest_print_log(db, printer_id=printer_id)
    if latest_run is None:
        return _blocked_payload(
            blocked_reasons=["last_print_run_missing"],
            printer_id=printer_id,
            latest_print_log_id=None,
            latest_print_run_id=None,
            source_cycle_key=None,
            details={},
        )

    latest_print_run_id = scheduler_print_run_key(latest_run.id)
    cycle = await _matching_swapmod_cycle(db, printer_id=printer_id, source_print_run_id=latest_print_run_id)
    if cycle is None:
        return _blocked_payload(
            blocked_reasons=["swapmod_cycle_missing_for_last_print"],
            printer_id=printer_id,
            latest_print_log_id=latest_run.id,
            latest_print_run_id=latest_print_run_id,
            source_cycle_key=None,
            details={
                "latest_print_status": latest_run.status,
                "latest_print_completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
            },
        )

    details = await evaluate_swapmod_next_print_gate(
        db,
        cycle,
        gate_key=f"scheduler-next-print:{printer_id}:{latest_print_run_id}",
        printer_id=printer_id,
        enabled=True,
        bed_automation_enabled=bed_automation_enabled,
    )
    allowed = bool(details.get("next_print_allowed"))
    payload = _allowed_payload if allowed else _blocked_payload
    return payload(
        enforced=True,
        blocked_reasons=list(details.get("blocked_reasons") or []),
        printer_id=printer_id,
        latest_print_log_id=latest_run.id,
        latest_print_run_id=latest_print_run_id,
        source_cycle_key=cycle.cycle_key,
        details={
            **details,
            "swapmod_gate_status": details.get("gate_status"),
            "latest_print_status": latest_run.status,
            "latest_print_completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
        },
    )


async def _latest_print_log(db: AsyncSession, *, printer_id: int) -> PrintLogEntry | None:
    result = await db.execute(
        select(PrintLogEntry)
        .where(PrintLogEntry.printer_id == printer_id)
        .order_by(PrintLogEntry.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _matching_swapmod_cycle(
    db: AsyncSession,
    *,
    printer_id: int,
    source_print_run_id: str,
) -> SwapmodStateMachineCycle | None:
    result = await db.execute(
        select(SwapmodStateMachineCycle)
        .where(SwapmodStateMachineCycle.printer_id == printer_id)
        .where(SwapmodStateMachineCycle.source_print_run_id == source_print_run_id)
        .order_by(SwapmodStateMachineCycle.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _allowed_payload(
    *,
    enforced: bool,
    printer_id: int | None,
    latest_print_log_id: int | None,
    latest_print_run_id: str | None,
    source_cycle_key: str | None,
    details: dict[str, object],
    blocked_reasons: list[str] | None = None,
) -> dict[str, object]:
    return _base_payload(
        gate_status=SCHEDULER_NEXT_PRINT_GATE_ALLOWED,
        next_print_allowed=True,
        enforced=enforced,
        blocked_reasons=blocked_reasons or [],
        printer_id=printer_id,
        latest_print_log_id=latest_print_log_id,
        latest_print_run_id=latest_print_run_id,
        source_cycle_key=source_cycle_key,
        details=details,
    )


def _blocked_payload(
    *,
    blocked_reasons: list[str],
    printer_id: int | None,
    latest_print_log_id: int | None,
    latest_print_run_id: str | None,
    source_cycle_key: str | None,
    details: dict[str, object],
    enforced: bool = True,
) -> dict[str, object]:
    return _base_payload(
        gate_status=SCHEDULER_NEXT_PRINT_GATE_BLOCKED,
        next_print_allowed=False,
        enforced=enforced,
        blocked_reasons=blocked_reasons,
        printer_id=printer_id,
        latest_print_log_id=latest_print_log_id,
        latest_print_run_id=latest_print_run_id,
        source_cycle_key=source_cycle_key,
        details=details,
    )


def _base_payload(
    *,
    gate_status: str,
    next_print_allowed: bool,
    enforced: bool,
    blocked_reasons: list[str],
    printer_id: int | None,
    latest_print_log_id: int | None,
    latest_print_run_id: str | None,
    source_cycle_key: str | None,
    details: dict[str, object],
) -> dict[str, object]:
    return {
        **details,
        "mode": "SWAPMOD_SCHEDULER_NEXT_PRINT_GATE",
        "gate_status": gate_status,
        "next_print_allowed": next_print_allowed,
        "enforced": enforced,
        "blocked_reasons": blocked_reasons,
        "printer_id": printer_id,
        "latest_print_log_id": latest_print_log_id,
        "latest_print_run_id": latest_print_run_id,
        "source_cycle_key": source_cycle_key,
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }
