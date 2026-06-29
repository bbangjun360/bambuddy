from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.swapmod_state_machine import SwapmodStateMachineCycle

IDLE = "IDLE"
WAITING_FOR_PRINT_FINISH = "WAITING_FOR_PRINT_FINISH"
READY_TO_RELEASE = "READY_TO_RELEASE"
RELEASING_PLATE = "RELEASING_PLATE"
VERIFY_RELEASED = "VERIFY_RELEASED"
READY_TO_LOAD = "READY_TO_LOAD"
LOADING_PLATE = "LOADING_PLATE"
VERIFY_LOADED = "VERIFY_LOADED"
READY_FOR_NEXT_PRINT = "READY_FOR_NEXT_PRINT"
RETRY_AVAILABLE = "RETRY_AVAILABLE"
MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
BLOCKED_TIMEOUT = "BLOCKED_TIMEOUT"
BLOCKED_UNKNOWN_STATE = "BLOCKED_UNKNOWN_STATE"

PRINT_FINISHED = "PRINT_FINISHED"
START_STEP = "START_STEP"
STEP_MOCK_SUCCEEDED = "STEP_MOCK_SUCCEEDED"
STEP_MOCK_FAILED = "STEP_MOCK_FAILED"
VERIFY_PASSED = "VERIFY_PASSED"
VERIFY_FAILED = "VERIFY_FAILED"
RETRY_REQUESTED = "RETRY_REQUESTED"
MANUAL_OVERRIDE_PASSED = "MANUAL_OVERRIDE_PASSED"
TIMEOUT = "TIMEOUT"
PROCESS_RESTARTED = "PROCESS_RESTARTED"

RELEASE_PLATE = "RELEASE_PLATE"
VERIFY_PLATE_RELEASED = "VERIFY_PLATE_RELEASED"
LOAD_NEXT_PLATE = "LOAD_NEXT_PLATE"
VERIFY_PLATE_READY = "VERIFY_PLATE_READY"

START_SWAPMOD_PLATE_CHANGE = "START_SWAPMOD_PLATE_CHANGE"

SUPPORTED_STATES = (
    IDLE,
    WAITING_FOR_PRINT_FINISH,
    READY_TO_RELEASE,
    RELEASING_PLATE,
    VERIFY_RELEASED,
    READY_TO_LOAD,
    LOADING_PLATE,
    VERIFY_LOADED,
    READY_FOR_NEXT_PRINT,
    RETRY_AVAILABLE,
    MANUAL_REVIEW_REQUIRED,
    BLOCKED_TIMEOUT,
    BLOCKED_UNKNOWN_STATE,
)
SUPPORTED_EVENTS = (
    PRINT_FINISHED,
    START_STEP,
    STEP_MOCK_SUCCEEDED,
    STEP_MOCK_FAILED,
    VERIFY_PASSED,
    VERIFY_FAILED,
    RETRY_REQUESTED,
    MANUAL_OVERRIDE_PASSED,
    TIMEOUT,
    PROCESS_RESTARTED,
)
SUPPORTED_STEPS = (
    RELEASE_PLATE,
    VERIFY_PLATE_RELEASED,
    LOAD_NEXT_PLATE,
    VERIFY_PLATE_READY,
)

_ACTIVE_STATES = frozenset({RELEASING_PLATE, LOADING_PLATE})


async def create_swapmod_cycle(
    db: AsyncSession,
    *,
    cycle_key: str,
    printer_id: int | None = None,
    source_print_run_id: str | None = None,
) -> SwapmodStateMachineCycle:
    result = await db.execute(select(SwapmodStateMachineCycle).where(SwapmodStateMachineCycle.cycle_key == cycle_key))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    cycle = SwapmodStateMachineCycle(
        cycle_key=cycle_key,
        printer_id=printer_id,
        source_print_run_id=source_print_run_id,
        state=WAITING_FOR_PRINT_FINISH,
        dry_run=settings.farm_swapmod_state_machine_dry_run,
        ready_for_next_print=False,
        manual_review_required=False,
        retry_available=False,
        blocked_reason=None,
        current_step=None,
        retry_step=None,
        verification_source=None,
        verification_result=None,
        note=None,
        seen_event_ids=[],
        transition_log=[],
        transition_count=0,
    )
    db.add(cycle)
    await db.flush()
    await db.refresh(cycle)
    return cycle


async def create_swapmod_operator_trigger(
    db: AsyncSession,
    *,
    trigger_key: str,
    cycle_key: str,
    printer_id: int | None = None,
    source_print_run_id: str | None = None,
    operator_intent: str,
) -> SwapmodStateMachineCycle:
    if operator_intent != START_SWAPMOD_PLATE_CHANGE:
        raise ValueError("unsupported SwapMod operator intent")

    cycle = await create_swapmod_cycle(
        db,
        cycle_key=cycle_key,
        printer_id=printer_id,
        source_print_run_id=source_print_run_id,
    )
    event_id = f"operator-trigger:{trigger_key}:print-finished"
    if event_id in (cycle.seen_event_ids or []):
        return cycle
    if cycle.state not in {IDLE, WAITING_FOR_PRINT_FINISH}:
        return cycle

    return await apply_swapmod_event(
        db,
        cycle,
        PRINT_FINISHED,
        event_id=event_id,
        note="operator requested SwapMod plate-change start",
    )


async def get_swapmod_cycle(db: AsyncSession, *, cycle_key: str) -> SwapmodStateMachineCycle | None:
    result = await db.execute(select(SwapmodStateMachineCycle).where(SwapmodStateMachineCycle.cycle_key == cycle_key))
    return result.scalar_one_or_none()


async def apply_swapmod_event(
    db: AsyncSession,
    cycle: SwapmodStateMachineCycle,
    event: str,
    *,
    event_id: str,
    step: str | None = None,
    verification_source: str | None = None,
    verification_result: str | None = None,
    note: str | None = None,
) -> SwapmodStateMachineCycle:
    if event_id in (cycle.seen_event_ids or []):
        return cycle

    from_state = cycle.state
    to_state: str | None = None
    reason: str | None = None
    next_current_step = cycle.current_step
    next_retry_step = cycle.retry_step

    if event == TIMEOUT:
        to_state = BLOCKED_TIMEOUT
        reason = "timeout leaves SwapMod plate state unproven"
        next_current_step = None
    elif event == PROCESS_RESTARTED and from_state in _ACTIVE_STATES:
        to_state = MANUAL_REVIEW_REQUIRED
        reason = "restart during SwapMod step requires manual review"
        next_current_step = None
    elif event == PROCESS_RESTARTED:
        to_state = from_state
        reason = "restart observed outside active SwapMod step"
    elif event == PRINT_FINISHED and from_state in {IDLE, WAITING_FOR_PRINT_FINISH}:
        to_state = READY_TO_RELEASE
        next_current_step = RELEASE_PLATE
    elif event == START_STEP:
        if from_state == READY_TO_RELEASE and step == RELEASE_PLATE:
            to_state = RELEASING_PLATE
            next_current_step = RELEASE_PLATE
        elif from_state == READY_TO_LOAD and step == LOAD_NEXT_PLATE:
            to_state = LOADING_PLATE
            next_current_step = LOAD_NEXT_PLATE
    elif event == STEP_MOCK_SUCCEEDED:
        if from_state == RELEASING_PLATE and _matches_step(step, RELEASE_PLATE):
            to_state = VERIFY_RELEASED
            next_current_step = VERIFY_PLATE_RELEASED
        elif from_state == LOADING_PLATE and _matches_step(step, LOAD_NEXT_PLATE):
            to_state = VERIFY_LOADED
            next_current_step = VERIFY_PLATE_READY
    elif event == STEP_MOCK_FAILED:
        if from_state == RELEASING_PLATE and _matches_step(step, RELEASE_PLATE):
            to_state = RETRY_AVAILABLE
            reason = "release step failed; retry available"
            next_retry_step = RELEASE_PLATE
        elif from_state == LOADING_PLATE and _matches_step(step, LOAD_NEXT_PLATE):
            to_state = RETRY_AVAILABLE
            reason = "load step failed; retry available"
            next_retry_step = LOAD_NEXT_PLATE
    elif event == RETRY_REQUESTED and from_state == RETRY_AVAILABLE:
        if cycle.retry_step == RELEASE_PLATE:
            to_state = READY_TO_RELEASE
            next_current_step = RELEASE_PLATE
            next_retry_step = None
        elif cycle.retry_step == LOAD_NEXT_PLATE:
            to_state = READY_TO_LOAD
            next_current_step = LOAD_NEXT_PLATE
            next_retry_step = None
    elif event == VERIFY_PASSED:
        if from_state == VERIFY_RELEASED and _verification_matches(step, VERIFY_PLATE_RELEASED, verification_result, "pass"):
            to_state = READY_TO_LOAD
            next_current_step = LOAD_NEXT_PLATE
        elif from_state == VERIFY_LOADED and _verification_matches(step, VERIFY_PLATE_READY, verification_result, "pass"):
            to_state = READY_FOR_NEXT_PRINT
            next_current_step = None
    elif event == VERIFY_FAILED:
        if from_state in {VERIFY_RELEASED, VERIFY_LOADED}:
            expected_step = VERIFY_PLATE_RELEASED if from_state == VERIFY_RELEASED else VERIFY_PLATE_READY
            if _verification_matches(step, expected_step, verification_result, "fail"):
                to_state = MANUAL_REVIEW_REQUIRED
                reason = "verification failed; manual review required"
                next_current_step = None
    elif event == MANUAL_OVERRIDE_PASSED and from_state == MANUAL_REVIEW_REQUIRED:
        if step == VERIFY_PLATE_RELEASED:
            to_state = READY_TO_LOAD
            next_current_step = LOAD_NEXT_PLATE
        elif step == VERIFY_PLATE_READY:
            to_state = READY_FOR_NEXT_PRINT
            next_current_step = None
        elif step == RELEASE_PLATE:
            to_state = READY_TO_RELEASE
            next_current_step = RELEASE_PLATE
        elif step == LOAD_NEXT_PLATE:
            to_state = READY_TO_LOAD
            next_current_step = LOAD_NEXT_PLATE

    if to_state is None:
        to_state = BLOCKED_UNKNOWN_STATE
        reason = f"invalid transition {from_state} -> {event}"
        next_current_step = None

    _apply_flags(cycle, to_state=to_state, reason=reason)
    cycle.state = to_state
    cycle.current_step = next_current_step
    cycle.retry_step = next_retry_step if to_state == RETRY_AVAILABLE else None
    if verification_source is not None:
        cycle.verification_source = verification_source
    if verification_result is not None:
        cycle.verification_result = verification_result
    if note is not None:
        cycle.note = note[:512]

    cycle.seen_event_ids = [*(cycle.seen_event_ids or []), event_id]
    cycle.transition_count = int(cycle.transition_count or 0) + 1
    cycle.transition_log = [
        *(cycle.transition_log or []),
        {
            "event": event,
            "event_id": event_id,
            "from_state": from_state,
            "to_state": to_state,
            "step": step,
            "verification_source": verification_source,
            "verification_result": verification_result,
            "reason": reason,
        },
    ]
    await db.flush()
    await db.refresh(cycle)
    return cycle


async def recover_swapmod_cycle_after_restart(
    db: AsyncSession,
    cycle: SwapmodStateMachineCycle,
    *,
    event_id: str,
) -> SwapmodStateMachineCycle:
    return await apply_swapmod_event(db, cycle, PROCESS_RESTARTED, event_id=event_id)


def public_swapmod_cycle(cycle: SwapmodStateMachineCycle) -> dict[str, object]:
    return {
        "id": cycle.id,
        "cycle_key": cycle.cycle_key,
        "printer_id": cycle.printer_id,
        "source_print_run_id": cycle.source_print_run_id,
        "state": cycle.state,
        "dry_run": cycle.dry_run,
        "real_execution_supported": False,
        "printer_command_sent": False,
        "ready_for_next_print": cycle.ready_for_next_print,
        "manual_review_required": cycle.manual_review_required,
        "retry_available": cycle.retry_available,
        "blocked_reason": cycle.blocked_reason,
        "current_step": cycle.current_step,
        "retry_step": cycle.retry_step,
        "verification_source": cycle.verification_source,
        "verification_result": cycle.verification_result,
        "note": cycle.note,
        "seen_event_ids": list(cycle.seen_event_ids or []),
        "transition_log": list(cycle.transition_log or []),
        "transition_count": int(cycle.transition_count or 0),
        "created_at": _iso(cycle.created_at),
        "updated_at": _iso(cycle.updated_at),
    }


def swapmod_state_machine_status(*, enabled: bool, dry_run: bool) -> dict[str, object]:
    return {
        "mode": "DRY_RUN_STATE_MACHINE_ONLY",
        "enabled": enabled,
        "dry_run": dry_run,
        "real_execution_supported": False,
        "printer_command_sent": False,
        "supported_states": list(SUPPORTED_STATES),
        "supported_events": list(SUPPORTED_EVENTS),
        "supported_steps": list(SUPPORTED_STEPS),
    }


def _matches_step(actual: str | None, expected: str) -> bool:
    return actual is None or actual == expected


def _verification_matches(
    step: str | None,
    expected_step: str,
    verification_result: str | None,
    expected_result: str,
) -> bool:
    if step != expected_step:
        return False
    return verification_result is None or verification_result == expected_result


def _apply_flags(cycle: SwapmodStateMachineCycle, *, to_state: str, reason: str | None) -> None:
    cycle.ready_for_next_print = to_state == READY_FOR_NEXT_PRINT
    cycle.manual_review_required = to_state in {
        MANUAL_REVIEW_REQUIRED,
        BLOCKED_TIMEOUT,
        BLOCKED_UNKNOWN_STATE,
    }
    cycle.retry_available = to_state == RETRY_AVAILABLE
    if reason is not None:
        cycle.blocked_reason = reason
    elif to_state not in {MANUAL_REVIEW_REQUIRED, BLOCKED_TIMEOUT, BLOCKED_UNKNOWN_STATE, RETRY_AVAILABLE}:
        cycle.blocked_reason = None


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None
