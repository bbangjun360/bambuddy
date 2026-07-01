from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.permissions import Permission
from backend.app.models.user import User
from backend.app.schemas.swapmod_state_machine import (
    SwapmodCanaryExecutionGateRequest,
    SwapmodNextPrintGateRequest,
    SwapmodQueueReadinessBindingRequest,
    SwapmodOperatorTriggerRequest,
    SwapmodStateMachineCycleCreate,
    SwapmodTransportStepRequest,
    SwapmodVerificationRequest,
    SwapmodStateMachineEventRequest,
)
from backend.app.services.swapmod_queue_readiness_binding import (
    SwapmodQueueReadinessBindingError,
    bind_swapmod_queue_readiness,
    swapmod_queue_readiness_binding_status,
)
from backend.app.services.swapmod_scheduler_handoff_diagnostics import (
    evaluate_swapmod_scheduler_handoff_diagnostics,
)
from backend.app.services.swapmod_next_print_gate import (
    SwapmodNextPrintGateError,
    evaluate_swapmod_next_print_gate,
    swapmod_next_print_gate_status,
)
from backend.app.services.swapmod_state_machine import (
    apply_swapmod_event,
    apply_swapmod_transport_step,
    apply_swapmod_verification,
    evaluate_swapmod_canary_execution_gate,
    create_swapmod_cycle,
    create_swapmod_operator_trigger,
    get_swapmod_cycle,
    public_swapmod_cycle,
    swapmod_state_machine_status,
)

router = APIRouter(prefix="/swapmod-state-machine", tags=["swapmod-state-machine"])


def _require_enabled() -> None:
    if not settings.farm_swapmod_state_machine_enabled:
        raise HTTPException(status_code=404, detail="SwapMod state machine is disabled")


def _require_transport_enabled() -> None:
    if not settings.farm_swapmod_transport_enabled:
        raise HTTPException(status_code=404, detail="SwapMod transport boundary is disabled")
    if not settings.farm_swapmod_transport_dry_run or settings.farm_swapmod_allow_real_transport:
        raise HTTPException(
            status_code=400,
            detail={"code": "dry_run_required", "message": "SwapMod transport boundary is dry-run only"},
        )

def _require_canary_execution_gate_enabled() -> None:
    if not settings.farm_swapmod_canary_execution_gate_enabled:
        raise HTTPException(status_code=404, detail="SwapMod canary execution gate is disabled")
    if not settings.farm_swapmod_canary_execution_dry_run or settings.farm_swapmod_canary_allow_real_execution:
        raise HTTPException(
            status_code=400,
            detail={"code": "dry_run_required", "message": "SwapMod canary execution gate is dry-run only"},
        )


def _require_next_print_gate_enabled() -> None:
    if not settings.farm_swapmod_next_print_gate_enabled:
        raise HTTPException(status_code=404, detail="SwapMod next-print gate is disabled")
    if not settings.farm_bed_automation_enabled:
        raise HTTPException(
            status_code=400,
            detail={"code": "bed_automation_disabled", "message": "Bed automation must be enabled"},
        )


def _require_queue_readiness_binding_enabled() -> None:
    if not settings.farm_swapmod_queue_readiness_binding_enabled:
        raise HTTPException(status_code=404, detail="SwapMod queue-readiness binding is disabled")
    if not settings.farm_bed_automation_enabled:
        raise HTTPException(
            status_code=400,
            detail={"code": "bed_automation_disabled", "message": "Bed automation must be enabled"},
        )


@router.get("/status")
async def get_swapmod_state_machine_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return swapmod_state_machine_status(
        enabled=settings.farm_swapmod_state_machine_enabled,
        dry_run=settings.farm_swapmod_state_machine_dry_run,
    )


@router.get("/next-print-gates/status")
async def get_swapmod_next_print_gate_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return swapmod_next_print_gate_status(
        enabled=settings.farm_swapmod_next_print_gate_enabled,
        bed_automation_enabled=settings.farm_bed_automation_enabled,
    )


@router.get("/queue-readiness-bindings/status")
async def get_swapmod_queue_readiness_binding_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return swapmod_queue_readiness_binding_status(
        enabled=settings.farm_swapmod_queue_readiness_binding_enabled,
        bed_automation_enabled=settings.farm_bed_automation_enabled,
    )


@router.get("/scheduler-handoff-diagnostics/status")
async def get_swapmod_scheduler_handoff_diagnostics_status(
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return {
        "mode": "SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_API_STATUS",
        "api_enabled": True,
        "read_only": True,
        "required_query_parameters": ["queue_item_id", "printer_id"],
        "required_permission": Permission.PRINTERS_READ.value,
        "response_contract_version": 1,
        "diagnostics_summary_contract_version": 1,
        "mutates_state": False,
        "supported_summary_fields": [
            "contract_version",
            "gate_status",
            "scheduler_start_allowed",
            "primary_blocker",
            "blocked_reason_count",
            "blocked_reason_sources",
            "enforced_gates",
            "handoff_identity_status",
            "read_only",
            "real_command_sent",
            "printer_command_sent",
            "scheduler_dispatch_supported",
        ],
        "supported_handoff_identity_statuses": ["not_enforced", "not_available", "matched", "mismatch"],
        "supported_blocked_reason_sources": [
            "scheduler_next_print_gate",
            "scheduler_queue_readiness_binding_gate",
            "handoff_identity",
        ],
        "scheduler_next_print_gate_enabled": settings.farm_swapmod_scheduler_next_print_gate_enabled,
        "scheduler_queue_readiness_binding_enabled": (
            settings.farm_swapmod_scheduler_queue_readiness_binding_enabled
        ),
        "bed_automation_enabled": settings.farm_bed_automation_enabled,
        "real_execution_supported": False,
        "real_command_sent": False,
        "printer_command_sent": False,
        "queue_dispatch_supported": False,
        "scheduler_dispatch_supported": False,
    }


@router.get("/scheduler-handoff-diagnostics")
async def get_swapmod_scheduler_handoff_diagnostics(
    queue_item_id: int,
    printer_id: int,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_READ),
):
    return await evaluate_swapmod_scheduler_handoff_diagnostics(
        db,
        queue_item_id=queue_item_id,
        printer_id=printer_id,
        scheduler_next_print_gate_enabled=settings.farm_swapmod_scheduler_next_print_gate_enabled,
        scheduler_queue_readiness_binding_enabled=settings.farm_swapmod_scheduler_queue_readiness_binding_enabled,
        bed_automation_enabled=settings.farm_bed_automation_enabled,
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


@router.post("/operator-triggers", status_code=202)
async def create_swapmod_operator_trigger_request(
    body: SwapmodOperatorTriggerRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    try:
        cycle = await create_swapmod_operator_trigger(
            db,
            trigger_key=body.trigger_key,
            cycle_key=body.cycle_key,
            printer_id=body.printer_id,
            source_print_run_id=body.source_print_run_id,
            operator_intent=body.operator_intent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "unsupported_operator_intent", "message": str(exc)}) from exc
    return public_swapmod_cycle(cycle)


@router.post("/cycles/{cycle_key}/verifications")
async def apply_swapmod_state_machine_verification(
    cycle_key: str,
    body: SwapmodVerificationRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    cycle = await get_swapmod_cycle(db, cycle_key=cycle_key)
    if cycle is None:
        raise HTTPException(status_code=404, detail="SwapMod state machine cycle not found")
    try:
        cycle = await apply_swapmod_verification(
            db,
            cycle,
            verification_key=body.verification_key,
            verification_source=body.verification_source,
            verification_result=body.verification_result,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "unsupported_verification", "message": str(exc)}) from exc
    return public_swapmod_cycle(cycle)


@router.post("/cycles/{cycle_key}/transport-steps", status_code=202)
async def apply_swapmod_transport_step_request(
    cycle_key: str,
    body: SwapmodTransportStepRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    _require_transport_enabled()
    cycle = await get_swapmod_cycle(db, cycle_key=cycle_key)
    if cycle is None:
        raise HTTPException(status_code=404, detail="SwapMod state machine cycle not found")
    try:
        return await apply_swapmod_transport_step(
            db,
            cycle,
            transport_key=body.transport_key,
            step=body.step,
            mock_result=body.mock_result,
            dry_run=settings.farm_swapmod_transport_dry_run,
            transport_enabled=settings.farm_swapmod_transport_enabled,
            allow_real_transport=settings.farm_swapmod_allow_real_transport,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "unsupported_transport_step", "message": str(exc)}) from exc



@router.post("/cycles/{cycle_key}/canary-execution-gates", status_code=202)
async def evaluate_swapmod_canary_execution_gate_request(
    cycle_key: str,
    body: SwapmodCanaryExecutionGateRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    _require_canary_execution_gate_enabled()
    cycle = await get_swapmod_cycle(db, cycle_key=cycle_key)
    if cycle is None:
        raise HTTPException(status_code=404, detail="SwapMod state machine cycle not found")
    try:
        return evaluate_swapmod_canary_execution_gate(
            cycle,
            gate_key=body.gate_key,
            canary_printer_alias=body.canary_printer_alias,
            requested_action=body.requested_action,
            operator_approved=body.operator_approved,
            operator_approval_phrase=body.operator_approval_phrase,
            checklist=body.checklist.model_dump(),
            gate_enabled=settings.farm_swapmod_canary_execution_gate_enabled,
            gate_dry_run=settings.farm_swapmod_canary_execution_dry_run,
            transport_enabled=settings.farm_swapmod_transport_enabled,
            transport_dry_run=settings.farm_swapmod_transport_dry_run,
            allow_real_transport=settings.farm_swapmod_allow_real_transport,
            allow_real_execution=settings.farm_swapmod_canary_allow_real_execution,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "unsupported_canary_gate", "message": str(exc)}) from exc


@router.post("/cycles/{cycle_key}/next-print-gates", status_code=202)
async def evaluate_swapmod_next_print_gate_request(
    cycle_key: str,
    body: SwapmodNextPrintGateRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    _require_next_print_gate_enabled()
    cycle = await get_swapmod_cycle(db, cycle_key=cycle_key)
    if cycle is None:
        raise HTTPException(status_code=404, detail="SwapMod state machine cycle not found")
    try:
        return await evaluate_swapmod_next_print_gate(
            db,
            cycle,
            gate_key=body.gate_key,
            printer_id=body.printer_id,
            enabled=settings.farm_swapmod_next_print_gate_enabled,
            bed_automation_enabled=settings.farm_bed_automation_enabled,
        )
    except SwapmodNextPrintGateError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc


@router.post("/cycles/{cycle_key}/queue-readiness-bindings", status_code=202)
async def bind_swapmod_queue_readiness_request(
    cycle_key: str,
    body: SwapmodQueueReadinessBindingRequest,
    db: AsyncSession = Depends(get_db),
    _: User | None = RequirePermissionIfAuthEnabled(Permission.PRINTERS_CONTROL),
):
    _require_enabled()
    _require_queue_readiness_binding_enabled()
    cycle = await get_swapmod_cycle(db, cycle_key=cycle_key)
    if cycle is None:
        raise HTTPException(status_code=404, detail="SwapMod state machine cycle not found")
    try:
        return await bind_swapmod_queue_readiness(
            db,
            cycle,
            binding_key=body.binding_key,
            queue_item_id=body.queue_item_id,
            printer_id=body.printer_id,
            enabled=settings.farm_swapmod_queue_readiness_binding_enabled,
            bed_automation_enabled=settings.farm_bed_automation_enabled,
        )
    except SwapmodQueueReadinessBindingError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc


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
