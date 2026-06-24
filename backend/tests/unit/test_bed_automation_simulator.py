from __future__ import annotations

import pytest
from sqlalchemy import func, select

from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.services.bed_automation import (
    BED_CLEAR_SIMULATED,
    BLOCKED_TIMEOUT,
    BLOCKED_UNKNOWN_STATE,
    COOLDOWN_REACHED,
    EJECT_CONFIRMED,
    EJECT_REQUESTED,
    EJECTING_SIMULATED,
    IDLE,
    MANUAL_REVIEW_REQUIRED,
    POST_CHECK_EMPTY,
    PRINT_COMPLETED,
    PROCESS_RESTARTED,
    READY_FOR_NEXT_PRINT,
    READY_TO_EJECT,
    SIMULATED_FAILURE,
    SIMULATED_TIMEOUT,
    UNKNOWN_PHYSICAL_STATE,
    WAITING_FOR_COOLDOWN,
    SimulatedBedAutomationAdapter,
    apply_simulated_event,
    create_simulated_cycle,
    recover_uncertain_cycle_after_restart,
    run_simulated_bed_clear,
)

pytestmark = pytest.mark.asyncio


async def _count(db_session, model) -> int:
    result = await db_session.execute(select(func.count()).select_from(model))
    return int(result.scalar_one())


async def test_initial_simulated_bed_cycle_state_is_safe(db_session):
    cycle = await create_simulated_cycle(db_session, cycle_key="cycle-safe", printer_id=101)

    assert cycle.state == IDLE
    assert cycle.dry_run is True
    assert cycle.ready_for_next_print is False
    assert cycle.manual_review_required is False
    assert cycle.blocked_reason is None
    assert cycle.transition_count == 0


async def test_valid_simulated_success_transition_reaches_ready_for_next_print(db_session):
    cycle = await create_simulated_cycle(db_session, cycle_key="cycle-success", printer_id=101)

    steps = [
        (PRINT_COMPLETED, "event-1", WAITING_FOR_COOLDOWN),
        (COOLDOWN_REACHED, "event-2", READY_TO_EJECT),
        (EJECT_REQUESTED, "event-3", EJECTING_SIMULATED),
        (EJECT_CONFIRMED, "event-4", BED_CLEAR_SIMULATED),
        (POST_CHECK_EMPTY, "event-5", READY_FOR_NEXT_PRINT),
    ]
    for event, event_id, expected_state in steps:
        cycle = await apply_simulated_event(db_session, cycle, event, event_id=event_id)
        assert cycle.state == expected_state

    assert cycle.ready_for_next_print is True
    assert cycle.manual_review_required is False
    assert cycle.transition_count == len(steps)
    assert [entry["to_state"] for entry in cycle.transition_log] == [state for _, _, state in steps]


async def test_simulated_failure_requires_manual_review(db_session):
    cycle = await create_simulated_cycle(db_session, cycle_key="cycle-failure", printer_id=101)
    cycle = await apply_simulated_event(db_session, cycle, PRINT_COMPLETED, event_id="event-1")

    cycle = await apply_simulated_event(db_session, cycle, SIMULATED_FAILURE, event_id="event-2")

    assert cycle.state == MANUAL_REVIEW_REQUIRED
    assert cycle.manual_review_required is True
    assert cycle.ready_for_next_print is False
    assert "simulated failure" in cycle.blocked_reason.lower()


async def test_simulated_timeout_blocks_cycle_safely(db_session):
    cycle = await create_simulated_cycle(db_session, cycle_key="cycle-timeout", printer_id=101)
    cycle = await apply_simulated_event(db_session, cycle, PRINT_COMPLETED, event_id="event-1")

    cycle = await apply_simulated_event(db_session, cycle, SIMULATED_TIMEOUT, event_id="event-2")

    assert cycle.state == BLOCKED_TIMEOUT
    assert cycle.manual_review_required is True
    assert cycle.ready_for_next_print is False
    assert "timeout" in cycle.blocked_reason.lower()


async def test_duplicate_event_handling_is_idempotent(db_session):
    cycle = await create_simulated_cycle(db_session, cycle_key="cycle-duplicate", printer_id=101)

    first = await apply_simulated_event(db_session, cycle, PRINT_COMPLETED, event_id="same-event")
    first_log = list(first.transition_log)
    second = await apply_simulated_event(db_session, first, PRINT_COMPLETED, event_id="same-event")

    assert second.state == WAITING_FOR_COOLDOWN
    assert second.transition_count == 1
    assert second.transition_log == first_log
    assert second.seen_event_ids == ["same-event"]


async def test_invalid_transition_blocks_unknown_state(db_session):
    cycle = await create_simulated_cycle(db_session, cycle_key="cycle-invalid", printer_id=101)

    cycle = await apply_simulated_event(db_session, cycle, EJECT_CONFIRMED, event_id="event-invalid")

    assert cycle.state == BLOCKED_UNKNOWN_STATE
    assert cycle.manual_review_required is True
    assert cycle.ready_for_next_print is False
    assert "invalid transition" in cycle.blocked_reason.lower()


async def test_unknown_physical_state_requires_manual_review(db_session):
    cycle = await create_simulated_cycle(db_session, cycle_key="cycle-unknown", printer_id=101)

    cycle = await apply_simulated_event(db_session, cycle, UNKNOWN_PHYSICAL_STATE, event_id="event-unknown")

    assert cycle.state == MANUAL_REVIEW_REQUIRED
    assert cycle.manual_review_required is True
    assert cycle.ready_for_next_print is False
    assert "cannot prove" in cycle.blocked_reason.lower()


async def test_restart_during_uncertain_execution_requires_manual_review(db_session):
    cycle = await create_simulated_cycle(db_session, cycle_key="cycle-restart", printer_id=101)
    cycle = await apply_simulated_event(db_session, cycle, PRINT_COMPLETED, event_id="event-1")
    cycle = await apply_simulated_event(db_session, cycle, COOLDOWN_REACHED, event_id="event-2")
    cycle = await apply_simulated_event(db_session, cycle, EJECT_REQUESTED, event_id="event-3")
    assert cycle.state == EJECTING_SIMULATED

    cycle = await recover_uncertain_cycle_after_restart(db_session, cycle, event_id="event-restart")

    assert cycle.state == MANUAL_REVIEW_REQUIRED
    assert cycle.manual_review_required is True
    assert cycle.ready_for_next_print is False
    assert cycle.transition_log[-1]["event"] == PROCESS_RESTARTED


async def test_simulator_never_creates_queue_or_print_log_entries(db_session):
    assert await _count(db_session, PrintQueueItem) == 0
    assert await _count(db_session, PrintLogEntry) == 0

    adapter = SimulatedBedAutomationAdapter(scenario="success")
    cycle = await run_simulated_bed_clear(
        db_session,
        cycle_key="cycle-no-dispatch",
        printer_id=101,
        adapter=adapter,
        idempotency_key="clear-1",
    )

    assert cycle.state == READY_FOR_NEXT_PRINT
    assert await _count(db_session, PrintQueueItem) == 0
    assert await _count(db_session, PrintLogEntry) == 0


async def test_simulated_adapter_classifies_failure_timeout_and_unknown_without_side_effects(db_session):
    cases = [
        ("failure", MANUAL_REVIEW_REQUIRED),
        ("timeout", BLOCKED_TIMEOUT),
        ("unknown", MANUAL_REVIEW_REQUIRED),
    ]
    for scenario, expected_state in cases:
        adapter = SimulatedBedAutomationAdapter(scenario=scenario)
        cycle = await run_simulated_bed_clear(
            db_session,
            cycle_key=f"cycle-{scenario}",
            printer_id=101,
            adapter=adapter,
            idempotency_key=f"clear-{scenario}",
        )

        assert cycle.state == expected_state
        assert cycle.ready_for_next_print is False
        assert cycle.manual_review_required is True
        assert adapter.network_calls_made == 0
        assert adapter.hardware_calls_made == 0
        assert len(adapter.calls) == 1

    assert await _count(db_session, PrintQueueItem) == 0
    assert await _count(db_session, PrintLogEntry) == 0
