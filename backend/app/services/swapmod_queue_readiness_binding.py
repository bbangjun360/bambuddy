from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.print_queue import PrintQueueItem
from backend.app.models.swapmod_queue_readiness_binding import SwapmodQueueReadinessBinding
from backend.app.models.swapmod_state_machine import SwapmodStateMachineCycle
from backend.app.services.bed_automation import MANUAL_REVIEW_REQUIRED, READY_FOR_NEXT_PRINT
from backend.app.services.swapmod_bed_readiness import swapmod_bed_cycle_key
from backend.app.services.swapmod_state_machine import READY_FOR_NEXT_PRINT as SWAPMOD_READY_FOR_NEXT_PRINT

QUEUE_READINESS_BINDING_READY = "ready"
QUEUE_READINESS_BINDING_BLOCKED = "blocked"


class SwapmodQueueReadinessBindingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def swapmod_queue_readiness_binding_status(*, enabled: bool, bed_automation_enabled: bool) -> dict[str, object]:
    return {
        "mode": "SWAPMOD_QUEUE_READINESS_BINDING_RECORD_ONLY",
        "enabled": enabled,
        "bed_automation_enabled": bed_automation_enabled,
        "record_only": True,
        "requires_swapmod_ready": True,
        "requires_bed_ready": True,
        "requires_pending_queue_item": True,
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }


async def bind_swapmod_queue_readiness(
    db: AsyncSession,
    cycle: SwapmodStateMachineCycle,
    *,
    binding_key: str,
    queue_item_id: int,
    printer_id: int,
    enabled: bool,
    bed_automation_enabled: bool,
) -> dict[str, object]:
    if not enabled:
        raise SwapmodQueueReadinessBindingError(
            "queue_readiness_binding_disabled",
            "SwapMod queue-readiness binding is disabled",
        )
    if not bed_automation_enabled:
        raise SwapmodQueueReadinessBindingError(
            "bed_automation_disabled",
            "Bed automation must be enabled for queue-readiness binding",
        )

    existing = await _get_binding_by_key(db, binding_key=binding_key)
    if existing is not None:
        _validate_existing_binding(existing, cycle, queue_item_id=queue_item_id, printer_id=printer_id)
        return await _evaluate_existing_binding(db, cycle, existing, idempotent=True)

    existing_for_queue_item = await _get_binding_by_queue_item(db, queue_item_id=queue_item_id)
    if existing_for_queue_item is not None:
        if existing_for_queue_item.binding_key != binding_key:
            raise SwapmodQueueReadinessBindingError(
                "binding_conflict",
                "queue_item_id is already tied to a different readiness binding",
            )
        _validate_existing_binding(existing_for_queue_item, cycle, queue_item_id=queue_item_id, printer_id=printer_id)
        return await _evaluate_existing_binding(db, cycle, existing_for_queue_item, idempotent=True)

    queue_item = await db.get(PrintQueueItem, queue_item_id)
    bed_cycle_key = swapmod_bed_cycle_key(source_cycle_key=cycle.cycle_key)
    existing_for_bed_cycle = await _get_binding_by_bed_cycle(db, bed_cycle_key=bed_cycle_key)
    if existing_for_bed_cycle is not None:
        raise SwapmodQueueReadinessBindingError(
            "binding_conflict",
            "bed-readiness proof is already tied to a different queue item",
        )
    bed_cycle = await _get_bed_cycle(db, bed_cycle_key=bed_cycle_key)
    blocked_reasons = _blocked_reasons(cycle, bed_cycle, queue_item, printer_id=printer_id)
    if blocked_reasons:
        return _public_blocked(
            cycle,
            queue_item=queue_item,
            bed_cycle=bed_cycle,
            bed_cycle_key=bed_cycle_key,
            binding_key=binding_key,
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            blocked_reasons=blocked_reasons,
        )

    if queue_item is None or bed_cycle is None:
        raise AssertionError("blocked readiness binding cannot create without queue item and bed cycle")

    binding = SwapmodQueueReadinessBinding(
        binding_key=binding_key,
        queue_item_id=queue_item.id,
        printer_id=printer_id,
        source_cycle_key=cycle.cycle_key,
        source_print_run_id=cycle.source_print_run_id,
        bed_cycle_key=bed_cycle.cycle_key,
        queue_archive_id=queue_item.archive_id,
        queue_library_file_id=queue_item.library_file_id,
        queue_plate_id=queue_item.plate_id,
        queue_fingerprint=_queue_fingerprint(queue_item, printer_id=printer_id),
    )

    try:
        async with db.begin_nested():
            db.add(binding)
            await db.flush()
    except IntegrityError:
        existing_after_race = await _get_binding_by_key(db, binding_key=binding_key)
        if existing_after_race is None:
            existing_after_race = await _get_binding_by_queue_item(db, queue_item_id=queue_item_id)
        if existing_after_race is None:
            existing_after_race = await _get_binding_by_bed_cycle(db, bed_cycle_key=bed_cycle_key)
        if existing_after_race is None:
            raise
        if (
            existing_after_race.binding_key != binding_key
            or existing_after_race.queue_item_id != queue_item_id
            or existing_after_race.bed_cycle_key != bed_cycle_key
        ):
            raise SwapmodQueueReadinessBindingError(
                "binding_conflict",
                "readiness binding unique key was claimed by a different queue item",
            )
        return await _evaluate_existing_binding(db, cycle, existing_after_race, idempotent=True)

    await db.refresh(binding)
    return _public_binding(
        cycle,
        binding,
        queue_item=queue_item,
        bed_cycle=bed_cycle,
        blocked_reasons=[],
        idempotent=False,
    )


async def _get_binding_by_key(
    db: AsyncSession,
    *,
    binding_key: str,
) -> SwapmodQueueReadinessBinding | None:
    result = await db.execute(
        select(SwapmodQueueReadinessBinding).where(SwapmodQueueReadinessBinding.binding_key == binding_key)
    )
    return result.scalar_one_or_none()


async def _get_binding_by_queue_item(
    db: AsyncSession,
    *,
    queue_item_id: int,
) -> SwapmodQueueReadinessBinding | None:
    result = await db.execute(
        select(SwapmodQueueReadinessBinding).where(SwapmodQueueReadinessBinding.queue_item_id == queue_item_id)
    )
    return result.scalar_one_or_none()


async def _get_binding_by_bed_cycle(
    db: AsyncSession,
    *,
    bed_cycle_key: str,
) -> SwapmodQueueReadinessBinding | None:
    result = await db.execute(
        select(SwapmodQueueReadinessBinding).where(SwapmodQueueReadinessBinding.bed_cycle_key == bed_cycle_key)
    )
    return result.scalar_one_or_none()


async def _get_bed_cycle(db: AsyncSession, *, bed_cycle_key: str) -> BedAutomationCycle | None:
    result = await db.execute(select(BedAutomationCycle).where(BedAutomationCycle.cycle_key == bed_cycle_key))
    return result.scalar_one_or_none()


async def _evaluate_existing_binding(
    db: AsyncSession,
    cycle: SwapmodStateMachineCycle,
    binding: SwapmodQueueReadinessBinding,
    *,
    idempotent: bool,
) -> dict[str, object]:
    queue_item = await db.get(PrintQueueItem, binding.queue_item_id)
    bed_cycle = await _get_bed_cycle(db, bed_cycle_key=binding.bed_cycle_key)
    blocked_reasons = _blocked_reasons(cycle, bed_cycle, queue_item, printer_id=binding.printer_id)
    if queue_item is not None and _queue_fingerprint(queue_item, printer_id=binding.printer_id) != binding.queue_fingerprint:
        blocked_reasons.append("queue_fingerprint_mismatch")
    if blocked_reasons:
        return _public_existing_blocked(
            cycle,
            binding,
            queue_item=queue_item,
            bed_cycle=bed_cycle,
            blocked_reasons=blocked_reasons,
            idempotent=idempotent,
        )
    return _public_binding(
        cycle,
        binding,
        queue_item=queue_item,
        bed_cycle=bed_cycle,
        blocked_reasons=[],
        idempotent=idempotent,
    )


def _validate_existing_binding(
    binding: SwapmodQueueReadinessBinding,
    cycle: SwapmodStateMachineCycle,
    *,
    queue_item_id: int,
    printer_id: int,
) -> None:
    if binding.queue_item_id != queue_item_id:
        raise SwapmodQueueReadinessBindingError(
            "binding_conflict",
            "binding_key is already tied to a different queue item",
        )
    if binding.printer_id != printer_id:
        raise SwapmodQueueReadinessBindingError(
            "binding_conflict",
            "binding_key is already tied to a different printer",
        )
    if binding.source_cycle_key != cycle.cycle_key:
        raise SwapmodQueueReadinessBindingError(
            "binding_conflict",
            "binding_key is already tied to a different SwapMod cycle",
        )
    if binding.bed_cycle_key != swapmod_bed_cycle_key(source_cycle_key=cycle.cycle_key):
        raise SwapmodQueueReadinessBindingError(
            "binding_conflict",
            "binding_key is already tied to a different bed-readiness proof",
        )
    if binding.source_print_run_id != cycle.source_print_run_id:
        raise SwapmodQueueReadinessBindingError(
            "binding_conflict",
            "binding_key source print run does not match the requested SwapMod cycle",
        )


def _blocked_reasons(
    cycle: SwapmodStateMachineCycle,
    bed_cycle: BedAutomationCycle | None,
    queue_item: PrintQueueItem | None,
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
    else:
        if bed_cycle.printer_id is None:
            reasons.append("bed_printer_missing")
        elif bed_cycle.printer_id != printer_id:
            reasons.append("bed_printer_mismatch")
        if bed_cycle.manual_review_required or bed_cycle.state == MANUAL_REVIEW_REQUIRED:
            reasons.append("bed_manual_review_required")
        if bed_cycle.state != READY_FOR_NEXT_PRINT or not bed_cycle.ready_for_next_print:
            reasons.append("bed_not_ready_for_next_print")

    if queue_item is None:
        reasons.append("queue_item_missing")
        return reasons

    if queue_item.status != "pending":
        reasons.append("queue_status_not_pending")
    if queue_item.printer_id is None:
        reasons.append("queue_printer_missing")
    elif queue_item.printer_id != printer_id:
        reasons.append("queue_printer_mismatch")
    if queue_item.archive_id is None and queue_item.library_file_id is None:
        reasons.append("queue_source_missing")

    return reasons


def _queue_fingerprint(queue_item: PrintQueueItem, *, printer_id: int) -> str:
    return ":".join(
        (
            f"queue_item={queue_item.id}",
            f"printer={printer_id}",
            f"archive={queue_item.archive_id or ''}",
            f"library={queue_item.library_file_id or ''}",
            f"plate={queue_item.plate_id or ''}",
        )
    )


def _public_blocked(
    cycle: SwapmodStateMachineCycle,
    *,
    queue_item: PrintQueueItem | None,
    bed_cycle: BedAutomationCycle | None,
    bed_cycle_key: str,
    binding_key: str,
    queue_item_id: int,
    printer_id: int,
    blocked_reasons: list[str],
) -> dict[str, object]:
    return _public_payload(
        cycle,
        binding_id=None,
        binding_key=binding_key,
        queue_item_id=queue_item_id,
        printer_id=printer_id,
        bed_cycle_key=bed_cycle_key,
        bed_cycle=bed_cycle,
        queue_archive_id=queue_item.archive_id if queue_item is not None else None,
        queue_library_file_id=queue_item.library_file_id if queue_item is not None else None,
        queue_plate_id=queue_item.plate_id if queue_item is not None else None,
        queue_fingerprint=_queue_fingerprint(queue_item, printer_id=printer_id) if queue_item is not None else None,
        binding_status=QUEUE_READINESS_BINDING_BLOCKED,
        queue_readiness_bound=False,
        blocked_reasons=blocked_reasons,
        idempotent=False,
    )


def _public_existing_blocked(
    cycle: SwapmodStateMachineCycle,
    binding: SwapmodQueueReadinessBinding,
    *,
    queue_item: PrintQueueItem | None,
    bed_cycle: BedAutomationCycle | None,
    blocked_reasons: list[str],
    idempotent: bool,
) -> dict[str, object]:
    return _public_payload(
        cycle,
        binding_id=binding.id,
        binding_key=binding.binding_key,
        queue_item_id=binding.queue_item_id,
        printer_id=binding.printer_id,
        bed_cycle_key=binding.bed_cycle_key,
        bed_cycle=bed_cycle,
        queue_archive_id=queue_item.archive_id if queue_item is not None else binding.queue_archive_id,
        queue_library_file_id=queue_item.library_file_id if queue_item is not None else binding.queue_library_file_id,
        queue_plate_id=queue_item.plate_id if queue_item is not None else binding.queue_plate_id,
        queue_fingerprint=_queue_fingerprint(queue_item, printer_id=binding.printer_id)
        if queue_item is not None
        else binding.queue_fingerprint,
        binding_status=QUEUE_READINESS_BINDING_BLOCKED,
        queue_readiness_bound=False,
        blocked_reasons=blocked_reasons,
        idempotent=idempotent,
    )


def _public_binding(
    cycle: SwapmodStateMachineCycle,
    binding: SwapmodQueueReadinessBinding,
    *,
    queue_item: PrintQueueItem | None,
    bed_cycle: BedAutomationCycle | None,
    blocked_reasons: list[str],
    idempotent: bool,
) -> dict[str, object]:
    return _public_payload(
        cycle,
        binding_id=binding.id,
        binding_key=binding.binding_key,
        queue_item_id=binding.queue_item_id,
        printer_id=binding.printer_id,
        bed_cycle_key=binding.bed_cycle_key,
        bed_cycle=bed_cycle,
        queue_archive_id=binding.queue_archive_id,
        queue_library_file_id=binding.queue_library_file_id,
        queue_plate_id=binding.queue_plate_id,
        queue_fingerprint=binding.queue_fingerprint,
        binding_status=QUEUE_READINESS_BINDING_READY,
        queue_readiness_bound=True,
        blocked_reasons=blocked_reasons,
        idempotent=idempotent,
    )


def _public_payload(
    cycle: SwapmodStateMachineCycle,
    *,
    binding_id: int | None,
    binding_key: str,
    queue_item_id: int,
    printer_id: int,
    bed_cycle_key: str,
    bed_cycle: BedAutomationCycle | None,
    queue_archive_id: int | None,
    queue_library_file_id: int | None,
    queue_plate_id: int | None,
    queue_fingerprint: str | None,
    binding_status: str,
    queue_readiness_bound: bool,
    blocked_reasons: list[str],
    idempotent: bool,
) -> dict[str, object]:
    return {
        "binding_id": binding_id,
        "binding_key": binding_key,
        "binding_status": binding_status,
        "queue_readiness_bound": queue_readiness_bound,
        "blocked_reasons": blocked_reasons,
        "idempotent": idempotent,
        "queue_item_id": queue_item_id,
        "queue_archive_id": queue_archive_id,
        "queue_library_file_id": queue_library_file_id,
        "queue_plate_id": queue_plate_id,
        "queue_fingerprint": queue_fingerprint,
        "source_cycle_key": cycle.cycle_key,
        "source_state": cycle.state,
        "source_ready_for_next_print": cycle.ready_for_next_print,
        "source_manual_review_required": cycle.manual_review_required,
        "source_printer_id": cycle.printer_id,
        "source_print_run_id": cycle.source_print_run_id,
        "printer_id": printer_id,
        "bed_cycle_key": bed_cycle_key,
        "bed_cycle_id": bed_cycle.id if bed_cycle is not None else None,
        "bed_state": bed_cycle.state if bed_cycle is not None else None,
        "bed_ready_for_next_print": bool(bed_cycle.ready_for_next_print) if bed_cycle is not None else False,
        "bed_manual_review_required": bool(bed_cycle.manual_review_required) if bed_cycle is not None else False,
        "bed_blocked_reason": bed_cycle.blocked_reason if bed_cycle is not None else None,
        "record_only": True,
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }
