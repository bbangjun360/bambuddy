from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.swapmod_scheduler_next_print_gate import evaluate_scheduler_next_print_gate
from backend.app.services.swapmod_scheduler_queue_readiness_binding import (
    evaluate_scheduler_queue_readiness_binding_gate,
)

SCHEDULER_HANDOFF_DIAGNOSTICS_ALLOWED = "allowed"
SCHEDULER_HANDOFF_DIAGNOSTICS_BLOCKED = "blocked"


async def evaluate_swapmod_scheduler_handoff_diagnostics(
    db: AsyncSession,
    *,
    queue_item_id: int,
    printer_id: int | None,
    scheduler_next_print_gate_enabled: bool,
    scheduler_queue_readiness_binding_enabled: bool,
    bed_automation_enabled: bool,
) -> dict[str, object]:
    next_print_gate = await evaluate_scheduler_next_print_gate(
        db,
        printer_id=printer_id,
        enabled=scheduler_next_print_gate_enabled,
        bed_automation_enabled=bed_automation_enabled,
    )
    queue_readiness_binding_gate = await evaluate_scheduler_queue_readiness_binding_gate(
        db,
        queue_item_id=queue_item_id,
        printer_id=printer_id,
        enabled=scheduler_queue_readiness_binding_enabled,
        bed_automation_enabled=bed_automation_enabled,
    )
    handoff_identity_blocked_reasons = _handoff_identity_blocked_reasons(
        next_print_gate,
        queue_readiness_binding_gate,
    )
    blocked_reasons = _combined_blocked_reasons(
        list(next_print_gate.get("blocked_reasons") or []),
        list(queue_readiness_binding_gate.get("blocked_reasons") or []),
        handoff_identity_blocked_reasons,
    )
    scheduler_start_allowed = not blocked_reasons

    return {
        "mode": "SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS",
        "gate_status": SCHEDULER_HANDOFF_DIAGNOSTICS_ALLOWED
        if scheduler_start_allowed
        else SCHEDULER_HANDOFF_DIAGNOSTICS_BLOCKED,
        "scheduler_start_allowed": scheduler_start_allowed,
        "next_print_allowed": scheduler_start_allowed,
        "blocked_reasons": blocked_reasons,
        "handoff_identity_blocked_reasons": handoff_identity_blocked_reasons,
        "queue_item_id": queue_item_id,
        "printer_id": printer_id,
        "latest_print_log_id": next_print_gate.get("latest_print_log_id"),
        "latest_print_run_id": next_print_gate.get("latest_print_run_id"),
        "source_cycle_key": next_print_gate.get("source_cycle_key"),
        "binding_id": queue_readiness_binding_gate.get("binding_id"),
        "binding_key": queue_readiness_binding_gate.get("binding_key"),
        "binding_source_print_run_id": queue_readiness_binding_gate.get("source_print_run_id"),
        "binding_source_cycle_key": queue_readiness_binding_gate.get("source_cycle_key"),
        "bed_cycle_key": queue_readiness_binding_gate.get("bed_cycle_key"),
        "queue_readiness_binding_consumed": queue_readiness_binding_gate.get(
            "queue_readiness_binding_consumed"
        ),
        "scheduler_next_print_gate": next_print_gate,
        "scheduler_queue_readiness_binding_gate": queue_readiness_binding_gate,
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }


def _handoff_identity_blocked_reasons(
    next_print_gate: dict[str, object],
    queue_readiness_binding_gate: dict[str, object],
) -> list[str]:
    if not next_print_gate.get("enforced") or not queue_readiness_binding_gate.get("enforced"):
        return []

    reasons: list[str] = []
    if next_print_gate.get("latest_print_run_id") != queue_readiness_binding_gate.get("source_print_run_id"):
        reasons.append("scheduler_handoff_source_print_run_mismatch")

    if next_print_gate.get("source_cycle_key") != queue_readiness_binding_gate.get("source_cycle_key"):
        reasons.append("scheduler_handoff_source_cycle_mismatch")

    return reasons


def _combined_blocked_reasons(*reason_groups: list[str]) -> list[str]:
    combined: list[str] = []
    for reasons in reason_groups:
        for reason in reasons:
            if reason not in combined:
                combined.append(reason)
    return combined
