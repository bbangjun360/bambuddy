from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.swapmod_queue_readiness_binding import SwapmodQueueReadinessBinding
from backend.app.models.swapmod_state_machine import SwapmodStateMachineCycle
from backend.app.services.swapmod_bed_readiness import swapmod_bed_cycle_key
from backend.app.services.swapmod_queue_readiness_binding import evaluate_existing_swapmod_queue_readiness_binding

SCHEDULER_QUEUE_READINESS_BINDING_ALLOWED = "allowed"
SCHEDULER_QUEUE_READINESS_BINDING_BLOCKED = "blocked"


async def evaluate_scheduler_queue_readiness_binding_gate(
    db: AsyncSession,
    *,
    queue_item_id: int,
    printer_id: int | None,
    enabled: bool,
    bed_automation_enabled: bool,
) -> dict[str, object]:
    if not enabled:
        return _allowed_payload(
            enforced=False,
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=None,
            details={},
        )

    if printer_id is None:
        return _blocked_payload(
            blocked_reasons=["printer_missing"],
            queue_item_id=queue_item_id,
            printer_id=None,
            binding=None,
            details={},
        )

    if not bed_automation_enabled:
        return _blocked_payload(
            blocked_reasons=["bed_automation_disabled"],
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=None,
            details={},
        )

    binding = await _get_binding_by_queue_item(db, queue_item_id=queue_item_id)
    if binding is None:
        return _blocked_payload(
            blocked_reasons=["queue_readiness_binding_missing"],
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=None,
            details={},
        )

    if binding.printer_id != printer_id:
        return _blocked_payload(
            blocked_reasons=["queue_readiness_binding_printer_mismatch"],
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=binding,
            details={},
        )

    if binding.consumed_at is not None:
        return _blocked_payload(
            blocked_reasons=["queue_readiness_binding_consumed"],
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=binding,
            details={},
        )

    cycle = await _get_cycle_by_key(db, cycle_key=binding.source_cycle_key)
    if cycle is None:
        return _blocked_payload(
            blocked_reasons=["swapmod_cycle_missing_for_binding"],
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=binding,
            details={},
        )

    identity_blocked_reasons = []
    if binding.source_print_run_id != cycle.source_print_run_id:
        identity_blocked_reasons.append("queue_readiness_binding_source_print_run_mismatch")
    if binding.bed_cycle_key != swapmod_bed_cycle_key(source_cycle_key=cycle.cycle_key):
        identity_blocked_reasons.append("queue_readiness_binding_bed_cycle_mismatch")
    if identity_blocked_reasons:
        return _blocked_payload(
            blocked_reasons=identity_blocked_reasons,
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=binding,
            details={
                "source_print_run_id": cycle.source_print_run_id,
                "expected_bed_cycle_key": swapmod_bed_cycle_key(source_cycle_key=cycle.cycle_key),
            },
        )

    details = await evaluate_existing_swapmod_queue_readiness_binding(db, cycle, binding, idempotent=True)
    blocked_reasons = list(details.get("blocked_reasons") or [])
    if not details.get("queue_readiness_bound") and not blocked_reasons:
        blocked_reasons.append("queue_readiness_binding_not_ready")

    payload = _allowed_payload if not blocked_reasons else _blocked_payload
    return payload(
        enforced=True,
        blocked_reasons=blocked_reasons,
        queue_item_id=queue_item_id,
        printer_id=printer_id,
        binding=binding,
        details=details,
    )


async def consume_scheduler_queue_readiness_binding(
    db: AsyncSession,
    *,
    queue_item_id: int,
    printer_id: int | None,
    enabled: bool,
) -> dict[str, object]:
    if not enabled:
        return _consume_payload(
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=None,
            consumed=False,
            blocked_reasons=[],
            enforced=False,
        )

    if printer_id is None:
        return _consume_payload(
            queue_item_id=queue_item_id,
            printer_id=None,
            binding=None,
            consumed=False,
            blocked_reasons=["printer_missing"],
            enforced=True,
        )

    binding = await _get_binding_by_queue_item(db, queue_item_id=queue_item_id)
    if binding is None:
        return _consume_payload(
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=None,
            consumed=False,
            blocked_reasons=["queue_readiness_binding_missing"],
            enforced=True,
        )

    if binding.printer_id != printer_id:
        return _consume_payload(
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=binding,
            consumed=False,
            blocked_reasons=["queue_readiness_binding_printer_mismatch"],
            enforced=True,
        )

    if binding.consumed_at is not None:
        return _consume_payload(
            queue_item_id=queue_item_id,
            printer_id=printer_id,
            binding=binding,
            consumed=False,
            blocked_reasons=["queue_readiness_binding_consumed"],
            enforced=True,
        )

    binding.consumed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(binding)

    return _consume_payload(
        queue_item_id=queue_item_id,
        printer_id=printer_id,
        binding=binding,
        consumed=True,
        blocked_reasons=[],
        enforced=True,
    )


async def _get_binding_by_queue_item(
    db: AsyncSession,
    *,
    queue_item_id: int,
) -> SwapmodQueueReadinessBinding | None:
    result = await db.execute(
        select(SwapmodQueueReadinessBinding).where(SwapmodQueueReadinessBinding.queue_item_id == queue_item_id)
    )
    return result.scalar_one_or_none()


async def _get_cycle_by_key(
    db: AsyncSession,
    *,
    cycle_key: str,
) -> SwapmodStateMachineCycle | None:
    result = await db.execute(select(SwapmodStateMachineCycle).where(SwapmodStateMachineCycle.cycle_key == cycle_key))
    return result.scalar_one_or_none()


def _allowed_payload(
    *,
    enforced: bool,
    queue_item_id: int,
    printer_id: int | None,
    binding: SwapmodQueueReadinessBinding | None,
    details: dict[str, object],
    blocked_reasons: list[str] | None = None,
) -> dict[str, object]:
    return _base_payload(
        gate_status=SCHEDULER_QUEUE_READINESS_BINDING_ALLOWED,
        next_print_allowed=True,
        enforced=enforced,
        blocked_reasons=blocked_reasons or [],
        queue_item_id=queue_item_id,
        printer_id=printer_id,
        binding=binding,
        details=details,
    )


def _blocked_payload(
    *,
    blocked_reasons: list[str],
    queue_item_id: int,
    printer_id: int | None,
    binding: SwapmodQueueReadinessBinding | None,
    details: dict[str, object],
    enforced: bool = True,
) -> dict[str, object]:
    return _base_payload(
        gate_status=SCHEDULER_QUEUE_READINESS_BINDING_BLOCKED,
        next_print_allowed=False,
        enforced=enforced,
        blocked_reasons=blocked_reasons,
        queue_item_id=queue_item_id,
        printer_id=printer_id,
        binding=binding,
        details=details,
    )


def _base_payload(
    *,
    gate_status: str,
    next_print_allowed: bool,
    enforced: bool,
    blocked_reasons: list[str],
    queue_item_id: int,
    printer_id: int | None,
    binding: SwapmodQueueReadinessBinding | None,
    details: dict[str, object],
) -> dict[str, object]:
    return {
        **details,
        "mode": "SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_GATE",
        "gate_status": gate_status,
        "next_print_allowed": next_print_allowed,
        "enforced": enforced,
        "blocked_reasons": blocked_reasons,
        "queue_item_id": queue_item_id,
        "printer_id": printer_id,
        "binding_id": binding.id if binding is not None else details.get("binding_id"),
        "binding_key": binding.binding_key if binding is not None else details.get("binding_key"),
        "source_cycle_key": binding.source_cycle_key if binding is not None else details.get("source_cycle_key"),
        "source_print_run_id": binding.source_print_run_id if binding is not None else details.get("source_print_run_id"),
        "bed_cycle_key": binding.bed_cycle_key if binding is not None else details.get("bed_cycle_key"),
        "queue_fingerprint": binding.queue_fingerprint if binding is not None else details.get("queue_fingerprint"),
        "queue_readiness_binding_consumed": bool(binding.consumed_at) if binding is not None else False,
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }


def _consume_payload(
    *,
    queue_item_id: int,
    printer_id: int | None,
    binding: SwapmodQueueReadinessBinding | None,
    consumed: bool,
    blocked_reasons: list[str],
    enforced: bool,
) -> dict[str, object]:
    return {
        "mode": "SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_CONSUME",
        "enforced": enforced,
        "queue_readiness_binding_consumed": consumed,
        "blocked_reasons": blocked_reasons,
        "queue_item_id": queue_item_id,
        "printer_id": printer_id,
        "binding_id": binding.id if binding is not None else None,
        "binding_key": binding.binding_key if binding is not None else None,
        "source_cycle_key": binding.source_cycle_key if binding is not None else None,
        "bed_cycle_key": binding.bed_cycle_key if binding is not None else None,
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }
