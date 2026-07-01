from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.swapmod_scheduler_next_print_gate import evaluate_scheduler_next_print_gate
from backend.app.services.swapmod_scheduler_queue_readiness_binding import (
    evaluate_scheduler_queue_readiness_binding_gate,
)

SCHEDULER_HANDOFF_DIAGNOSTICS_ALLOWED = "allowed"
SCHEDULER_HANDOFF_DIAGNOSTICS_BLOCKED = "blocked"
SCHEDULER_HANDOFF_DIAGNOSTICS_REASON_CATALOG_VERSION = 1

_SCHEDULER_HANDOFF_DIAGNOSTICS_REASON_SOURCE_ORDER = (
    "scheduler_next_print_gate",
    "scheduler_queue_readiness_binding_gate",
    "handoff_identity",
)

_SCHEDULER_HANDOFF_DIAGNOSTICS_REASON_CATALOG = {
    "scheduler_next_print_gate": [
        {"reason": "printer_missing", "operator_action": "review_printer_selection"},
        {"reason": "bed_automation_disabled", "operator_action": "review_bed_automation_gate"},
        {"reason": "last_print_run_missing", "operator_action": "review_latest_print_log"},
        {
            "reason": "swapmod_cycle_missing_for_last_print",
            "operator_action": "review_swapmod_cycle_for_latest_print",
        },
        {"reason": "printer_mismatch", "operator_action": "review_printer_identity"},
        {"reason": "swapmod_manual_review_required", "operator_action": "resolve_swapmod_manual_review"},
        {"reason": "swapmod_cycle_not_ready", "operator_action": "complete_swapmod_ready_verification"},
        {"reason": "bed_readiness_record_missing", "operator_action": "review_bed_readiness_handoff"},
        {"reason": "bed_printer_missing", "operator_action": "review_bed_readiness_printer"},
        {"reason": "bed_printer_mismatch", "operator_action": "review_bed_printer_identity"},
        {"reason": "bed_manual_review_required", "operator_action": "resolve_bed_manual_review"},
        {"reason": "bed_not_ready_for_next_print", "operator_action": "verify_bed_ready_for_next_print"},
    ],
    "scheduler_queue_readiness_binding_gate": [
        {"reason": "printer_missing", "operator_action": "review_printer_selection"},
        {"reason": "bed_automation_disabled", "operator_action": "review_bed_automation_gate"},
        {"reason": "queue_readiness_binding_missing", "operator_action": "review_queue_readiness_binding"},
        {
            "reason": "queue_readiness_binding_printer_mismatch",
            "operator_action": "review_binding_printer_identity",
        },
        {"reason": "queue_readiness_binding_consumed", "operator_action": "select_unconsumed_queue_binding"},
        {"reason": "swapmod_cycle_missing_for_binding", "operator_action": "review_binding_source_cycle"},
        {
            "reason": "queue_readiness_binding_source_print_run_mismatch",
            "operator_action": "review_binding_print_run_identity",
        },
        {
            "reason": "queue_readiness_binding_bed_cycle_mismatch",
            "operator_action": "review_binding_bed_cycle_identity",
        },
        {"reason": "queue_readiness_binding_not_ready", "operator_action": "recheck_queue_readiness_binding"},
        {"reason": "queue_fingerprint_mismatch", "operator_action": "review_current_queue_item_binding"},
        {"reason": "printer_mismatch", "operator_action": "review_printer_identity"},
        {"reason": "swapmod_manual_review_required", "operator_action": "resolve_swapmod_manual_review"},
        {"reason": "swapmod_cycle_not_ready", "operator_action": "complete_swapmod_ready_verification"},
        {"reason": "bed_readiness_record_missing", "operator_action": "review_bed_readiness_handoff"},
        {"reason": "bed_printer_missing", "operator_action": "review_bed_readiness_printer"},
        {"reason": "bed_printer_mismatch", "operator_action": "review_bed_printer_identity"},
        {"reason": "bed_manual_review_required", "operator_action": "resolve_bed_manual_review"},
        {"reason": "bed_not_ready_for_next_print", "operator_action": "verify_bed_ready_for_next_print"},
        {"reason": "queue_item_missing", "operator_action": "review_queue_item_exists"},
        {"reason": "queue_status_not_pending", "operator_action": "review_queue_item_pending_status"},
        {"reason": "queue_printer_missing", "operator_action": "review_queue_printer_assignment"},
        {"reason": "queue_printer_mismatch", "operator_action": "review_queue_printer_identity"},
        {"reason": "queue_source_missing", "operator_action": "review_queue_source_file"},
    ],
    "handoff_identity": [
        {
            "reason": "scheduler_handoff_source_print_run_mismatch",
            "operator_action": "review_handoff_print_run_identity",
        },
        {
            "reason": "scheduler_handoff_source_cycle_mismatch",
            "operator_action": "review_handoff_cycle_identity",
        },
    ],
}

_OPERATOR_ACTIONS_BY_SOURCE_REASON = {
    source: {str(entry["reason"]): str(entry["operator_action"]) for entry in entries}
    for source, entries in _SCHEDULER_HANDOFF_DIAGNOSTICS_REASON_CATALOG.items()
}


def swapmod_scheduler_handoff_diagnostics_blocked_reason_catalog() -> dict[str, object]:
    return {
        "contract_version": SCHEDULER_HANDOFF_DIAGNOSTICS_REASON_CATALOG_VERSION,
        "sources": {
            source: [dict(entry) for entry in _SCHEDULER_HANDOFF_DIAGNOSTICS_REASON_CATALOG[source]]
            for source in _SCHEDULER_HANDOFF_DIAGNOSTICS_REASON_SOURCE_ORDER
        },
    }


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
    gate_status = (
        SCHEDULER_HANDOFF_DIAGNOSTICS_ALLOWED
        if scheduler_start_allowed
        else SCHEDULER_HANDOFF_DIAGNOSTICS_BLOCKED
    )

    return {
        "mode": "SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS",
        "gate_status": gate_status,
        "scheduler_start_allowed": scheduler_start_allowed,
        "next_print_allowed": scheduler_start_allowed,
        "blocked_reasons": blocked_reasons,
        "handoff_identity_blocked_reasons": handoff_identity_blocked_reasons,
        "diagnostics_summary": _diagnostics_summary(
            gate_status=gate_status,
            scheduler_start_allowed=scheduler_start_allowed,
            blocked_reasons=blocked_reasons,
            next_print_gate=next_print_gate,
            queue_readiness_binding_gate=queue_readiness_binding_gate,
            handoff_identity_blocked_reasons=handoff_identity_blocked_reasons,
        ),
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


def _diagnostics_summary(
    *,
    gate_status: str,
    scheduler_start_allowed: bool,
    blocked_reasons: list[str],
    next_print_gate: dict[str, object],
    queue_readiness_binding_gate: dict[str, object],
    handoff_identity_blocked_reasons: list[str],
) -> dict[str, object]:
    next_print_reasons = list(next_print_gate.get("blocked_reasons") or [])
    queue_readiness_binding_reasons = list(queue_readiness_binding_gate.get("blocked_reasons") or [])
    blocked_reason_sources = {
        "scheduler_next_print_gate": next_print_reasons,
        "scheduler_queue_readiness_binding_gate": queue_readiness_binding_reasons,
        "handoff_identity": handoff_identity_blocked_reasons,
    }
    blocked_reason_details = _blocked_reason_details(blocked_reasons, blocked_reason_sources)
    primary_operator_action, primary_operator_action_source = _primary_operator_action(blocked_reason_details)
    enforced_gates: list[str] = []
    if next_print_gate.get("enforced"):
        enforced_gates.append("scheduler_next_print_gate")
    if queue_readiness_binding_gate.get("enforced"):
        enforced_gates.append("scheduler_queue_readiness_binding_gate")

    identity_available = all(
        (
            next_print_gate.get("latest_print_run_id"),
            queue_readiness_binding_gate.get("source_print_run_id"),
            next_print_gate.get("source_cycle_key"),
            queue_readiness_binding_gate.get("source_cycle_key"),
        )
    )
    if len(enforced_gates) < 2:
        handoff_identity_status = "not_enforced"
    elif not identity_available:
        handoff_identity_status = "not_available"
    elif handoff_identity_blocked_reasons:
        handoff_identity_status = "mismatch"
    else:
        handoff_identity_status = "matched"

    return {
        "contract_version": 1,
        "gate_status": gate_status,
        "scheduler_start_allowed": scheduler_start_allowed,
        "primary_blocker": blocked_reasons[0] if blocked_reasons else None,
        "primary_operator_action": primary_operator_action,
        "primary_operator_action_source": primary_operator_action_source,
        "blocked_reason_details": blocked_reason_details,
        "blocked_reason_count": len(blocked_reasons),
        "blocked_reason_sources": blocked_reason_sources,
        "enforced_gates": enforced_gates,
        "handoff_identity_status": handoff_identity_status,
        "read_only": True,
        "real_command_sent": False,
        "printer_command_sent": False,
        "scheduler_dispatch_supported": False,
    }


def _blocked_reason_details(
    blocked_reasons: list[str],
    blocked_reason_sources: dict[str, list[str]],
) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    for reason in blocked_reasons:
        sources = [
            source
            for source in _SCHEDULER_HANDOFF_DIAGNOSTICS_REASON_SOURCE_ORDER
            if reason in blocked_reason_sources.get(source, [])
        ]
        operator_action = "review_diagnostics_blocker"
        operator_action_source = None
        for source in sources:
            action = _OPERATOR_ACTIONS_BY_SOURCE_REASON.get(source, {}).get(reason)
            if action is None:
                continue
            operator_action = action
            operator_action_source = source
            break
        details.append(
            {
                "reason": reason,
                "sources": sources,
                "operator_action": operator_action,
                "operator_action_source": operator_action_source,
            }
        )
    return details


def _primary_operator_action(
    blocked_reason_details: list[dict[str, object]],
) -> tuple[str | None, str | None]:
    if not blocked_reason_details:
        return None, None

    first_detail = blocked_reason_details[0]
    return (
        str(first_detail["operator_action"]),
        first_detail["operator_action_source"] if first_detail["operator_action_source"] is not None else None,
    )


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
