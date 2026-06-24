from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.bed_automation import BedAutomationCycle

IDLE = "IDLE"
WAITING_FOR_COOLDOWN = "WAITING_FOR_COOLDOWN"
READY_TO_EJECT = "READY_TO_EJECT"
EJECTING_SIMULATED = "EJECTING_SIMULATED"
BED_CLEAR_SIMULATED = "BED_CLEAR_SIMULATED"
READY_FOR_NEXT_PRINT = "READY_FOR_NEXT_PRINT"
BLOCKED_UNKNOWN_STATE = "BLOCKED_UNKNOWN_STATE"
BLOCKED_TIMEOUT = "BLOCKED_TIMEOUT"
MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"

PRINT_COMPLETED = "PRINT_COMPLETED"
COOLDOWN_REACHED = "COOLDOWN_REACHED"
EJECT_REQUESTED = "EJECT_REQUESTED"
EJECT_CONFIRMED = "EJECT_CONFIRMED"
POST_CHECK_EMPTY = "POST_CHECK_EMPTY"
SIMULATED_FAILURE = "SIMULATED_FAILURE"
SIMULATED_TIMEOUT = "SIMULATED_TIMEOUT"
UNKNOWN_PHYSICAL_STATE = "UNKNOWN_PHYSICAL_STATE"
PROCESS_RESTARTED = "PROCESS_RESTARTED"

_VALID_TRANSITIONS = {
    IDLE: {PRINT_COMPLETED: WAITING_FOR_COOLDOWN},
    WAITING_FOR_COOLDOWN: {COOLDOWN_REACHED: READY_TO_EJECT},
    READY_TO_EJECT: {EJECT_REQUESTED: EJECTING_SIMULATED},
    EJECTING_SIMULATED: {EJECT_CONFIRMED: BED_CLEAR_SIMULATED},
    BED_CLEAR_SIMULATED: {POST_CHECK_EMPTY: READY_FOR_NEXT_PRINT},
}

_UNCERTAIN_STATES = frozenset({EJECTING_SIMULATED})


@dataclass(frozen=True)
class SimulatedAdapterResult:
    outcome: str
    failure_class: str | None = None
    verified_empty: bool = False


@dataclass
class SimulatedBedAutomationAdapter:
    scenario: str = "success"
    calls: list[dict[str, object]] = field(default_factory=list)
    network_calls_made: int = 0
    hardware_calls_made: int = 0
    _results_by_key: dict[str, SimulatedAdapterResult] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.scenario not in {"success", "failure", "timeout", "unknown"}:
            raise ValueError(f"unsupported simulated bed scenario: {self.scenario}")

    def clear_bed(self, *, cycle_key: str, idempotency_key: str, dry_run: bool = True) -> SimulatedAdapterResult:
        existing = self._results_by_key.get(idempotency_key)
        if existing is not None:
            return existing

        self.calls.append({"cycle_key": cycle_key, "idempotency_key": idempotency_key, "dry_run": dry_run})
        if self.scenario == "success":
            result = SimulatedAdapterResult(outcome="success", verified_empty=True)
        elif self.scenario == "failure":
            result = SimulatedAdapterResult(outcome="failure", failure_class="simulated_failure")
        elif self.scenario == "timeout":
            result = SimulatedAdapterResult(outcome="timeout", failure_class="simulated_timeout")
        else:
            result = SimulatedAdapterResult(outcome="unknown", failure_class="unknown_physical_state")
        self._results_by_key[idempotency_key] = result
        return result


async def create_simulated_cycle(
    db: AsyncSession,
    *,
    cycle_key: str,
    printer_id: int | None = None,
    source_print_run_id: str | None = None,
) -> BedAutomationCycle:
    result = await db.execute(select(BedAutomationCycle).where(BedAutomationCycle.cycle_key == cycle_key))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing

    cycle = BedAutomationCycle(
        cycle_key=cycle_key,
        printer_id=printer_id,
        source_print_run_id=source_print_run_id,
        state=IDLE,
        dry_run=settings.farm_bed_automation_dry_run,
        ready_for_next_print=False,
        manual_review_required=False,
        blocked_reason=None,
        seen_event_ids=[],
        transition_log=[],
        transition_count=0,
    )
    db.add(cycle)
    await db.flush()
    await db.refresh(cycle)
    return cycle


async def apply_simulated_event(
    db: AsyncSession,
    cycle: BedAutomationCycle,
    event: str,
    *,
    event_id: str,
) -> BedAutomationCycle:
    if event_id in (cycle.seen_event_ids or []):
        return cycle

    from_state = cycle.state
    reason: str | None = None

    if event == SIMULATED_FAILURE:
        to_state = MANUAL_REVIEW_REQUIRED
        reason = "simulated failure requires manual review"
        cycle.manual_review_required = True
        cycle.ready_for_next_print = False
    elif event == SIMULATED_TIMEOUT:
        to_state = BLOCKED_TIMEOUT
        reason = "simulated timeout leaves bed state unproven"
        cycle.manual_review_required = True
        cycle.ready_for_next_print = False
    elif event == UNKNOWN_PHYSICAL_STATE:
        to_state = MANUAL_REVIEW_REQUIRED
        reason = "simulator cannot prove bed state"
        cycle.manual_review_required = True
        cycle.ready_for_next_print = False
    elif event == PROCESS_RESTARTED and from_state in _UNCERTAIN_STATES:
        to_state = MANUAL_REVIEW_REQUIRED
        reason = "restart during simulated execution requires manual review"
        cycle.manual_review_required = True
        cycle.ready_for_next_print = False
    else:
        to_state = _VALID_TRANSITIONS.get(from_state, {}).get(event)
        if to_state is None:
            to_state = BLOCKED_UNKNOWN_STATE
            reason = f"invalid transition {from_state} -> {event}"
            cycle.manual_review_required = True
            cycle.ready_for_next_print = False
        elif to_state == READY_FOR_NEXT_PRINT:
            cycle.ready_for_next_print = True
            cycle.manual_review_required = False
            cycle.blocked_reason = None
        else:
            cycle.ready_for_next_print = False
            cycle.manual_review_required = False
            cycle.blocked_reason = None

    cycle.state = to_state
    if reason is not None:
        cycle.blocked_reason = reason

    cycle.seen_event_ids = [*(cycle.seen_event_ids or []), event_id]
    cycle.transition_count = int(cycle.transition_count or 0) + 1
    cycle.transition_log = [
        *(cycle.transition_log or []),
        {
            "event": event,
            "event_id": event_id,
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
        },
    ]
    await db.flush()
    await db.refresh(cycle)
    return cycle


async def recover_uncertain_cycle_after_restart(
    db: AsyncSession,
    cycle: BedAutomationCycle,
    *,
    event_id: str,
) -> BedAutomationCycle:
    return await apply_simulated_event(db, cycle, PROCESS_RESTARTED, event_id=event_id)


async def run_simulated_bed_clear(
    db: AsyncSession,
    *,
    cycle_key: str,
    printer_id: int | None,
    adapter: SimulatedBedAutomationAdapter,
    idempotency_key: str,
    source_print_run_id: str | None = None,
) -> BedAutomationCycle:
    cycle = await create_simulated_cycle(
        db,
        cycle_key=cycle_key,
        printer_id=printer_id,
        source_print_run_id=source_print_run_id,
    )
    result = adapter.clear_bed(cycle_key=cycle_key, idempotency_key=idempotency_key, dry_run=cycle.dry_run)

    cycle = await apply_simulated_event(db, cycle, PRINT_COMPLETED, event_id=f"{idempotency_key}:print-completed")
    if result.outcome == "success":
        for suffix, event in (
            ("cooldown", COOLDOWN_REACHED),
            ("eject-requested", EJECT_REQUESTED),
            ("eject-confirmed", EJECT_CONFIRMED),
            ("post-check-empty", POST_CHECK_EMPTY),
        ):
            cycle = await apply_simulated_event(db, cycle, event, event_id=f"{idempotency_key}:{suffix}")
    elif result.outcome == "failure":
        cycle = await apply_simulated_event(db, cycle, SIMULATED_FAILURE, event_id=f"{idempotency_key}:failure")
    elif result.outcome == "timeout":
        cycle = await apply_simulated_event(db, cycle, SIMULATED_TIMEOUT, event_id=f"{idempotency_key}:timeout")
    else:
        cycle = await apply_simulated_event(db, cycle, UNKNOWN_PHYSICAL_STATE, event_id=f"{idempotency_key}:unknown")
    return cycle
