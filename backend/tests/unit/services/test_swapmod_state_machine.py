from __future__ import annotations

import unittest

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.database import Base
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.services.swapmod_state_machine import (
    BLOCKED_TIMEOUT,
    BLOCKED_UNKNOWN_STATE,
    CANARY_GATE_BLOCKED,
    CANARY_GATE_READY,
    LOAD_NEXT_PLATE,
    LOADING_PLATE,
    MANUAL_REVIEW_REQUIRED,
    PRINT_FINISHED,
    PROCESS_RESTARTED,
    READY_FOR_NEXT_PRINT,
    READY_TO_LOAD,
    READY_TO_RELEASE,
    RELEASE_PLATE,
    RELEASING_PLATE,
    RETRY_AVAILABLE,
    RETRY_REQUESTED,
    START_STEP,
    STEP_MOCK_FAILED,
    STEP_MOCK_SUCCEEDED,
    TIMEOUT,
    VERIFY_FAILED,
    VERIFY_LOADED,
    VERIFY_PASSED,
    VERIFY_PLATE_READY,
    VERIFY_PLATE_RELEASED,
    VERIFY_RELEASED,
    WAITING_FOR_PRINT_FINISH,
    apply_swapmod_event,
    apply_swapmod_transport_step,
    apply_swapmod_verification,
    evaluate_swapmod_canary_execution_gate,
    create_swapmod_cycle,
    create_swapmod_operator_trigger,
    get_swapmod_cycle,
    public_swapmod_cycle,
    required_swapmod_canary_approval_phrase,
    recover_swapmod_cycle_after_restart,
)


async def get_cycle(session: AsyncSession, cycle_key: str):
    cycle = await get_swapmod_cycle(session, cycle_key=cycle_key)
    assert cycle is not None
    return cycle


class SwapmodStateMachineServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
            group,
            print_log,
            print_queue,
            settings,
            swapmod_state_machine,
            user,
        )

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.session = self.sessionmaker()

    async def asyncTearDown(self) -> None:
        await self.session.close()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def count_rows(self, model) -> int:
        result = await self.session.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())

    async def test_initial_cycle_waits_for_print_finish_and_exposes_no_real_execution(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-cycle-safe", printer_id=101)
        payload = public_swapmod_cycle(cycle)

        self.assertEqual(cycle.state, WAITING_FOR_PRINT_FINISH)
        self.assertTrue(cycle.dry_run)
        self.assertFalse(cycle.ready_for_next_print)
        self.assertFalse(cycle.manual_review_required)
        self.assertFalse(cycle.retry_available)
        self.assertEqual(cycle.transition_count, 0)
        self.assertFalse(payload["real_execution_supported"])
        self.assertFalse(payload["printer_command_sent"])

    async def test_happy_path_reaches_ready_for_next_print_only_after_loaded_verification(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-cycle-success", printer_id=101)

        steps = [
            (PRINT_FINISHED, "event-1", None, None, None, READY_TO_RELEASE),
            (START_STEP, "event-2", RELEASE_PLATE, None, None, RELEASING_PLATE),
            (STEP_MOCK_SUCCEEDED, "event-3", RELEASE_PLATE, None, None, VERIFY_RELEASED),
            (VERIFY_PASSED, "event-4", VERIFY_PLATE_RELEASED, "manual", "pass", READY_TO_LOAD),
            (START_STEP, "event-5", LOAD_NEXT_PLATE, None, None, LOADING_PLATE),
            (STEP_MOCK_SUCCEEDED, "event-6", LOAD_NEXT_PLATE, None, None, VERIFY_LOADED),
            (VERIFY_PASSED, "event-7", VERIFY_PLATE_READY, "camera_mock", "pass", READY_FOR_NEXT_PRINT),
        ]
        for event, event_id, step, verification_source, verification_result, expected_state in steps:
            cycle = await apply_swapmod_event(
                self.session,
                cycle,
                event,
                event_id=event_id,
                step=step,
                verification_source=verification_source,
                verification_result=verification_result,
            )
            self.assertEqual(cycle.state, expected_state)

        payload = public_swapmod_cycle(cycle)
        self.assertTrue(payload["ready_for_next_print"])
        self.assertFalse(payload["manual_review_required"])
        self.assertFalse(payload["retry_available"])
        self.assertFalse(payload["real_execution_supported"])
        self.assertFalse(payload["printer_command_sent"])
        self.assertEqual(payload["transition_log"][-1]["verification_source"], "camera_mock")

    async def test_step_failure_moves_to_retry_available_and_retry_reenters_same_stage(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-cycle-retry", printer_id=101)
        cycle = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="event-1")
        cycle = await apply_swapmod_event(
            self.session,
            cycle,
            START_STEP,
            event_id="event-2",
            step=RELEASE_PLATE,
        )

        cycle = await apply_swapmod_event(
            self.session,
            cycle,
            STEP_MOCK_FAILED,
            event_id="event-3",
            step=RELEASE_PLATE,
            note="operator saw partial release",
        )

        self.assertEqual(cycle.state, RETRY_AVAILABLE)
        self.assertTrue(cycle.retry_available)
        self.assertEqual(cycle.retry_step, RELEASE_PLATE)
        self.assertFalse(cycle.manual_review_required)
        self.assertFalse(cycle.ready_for_next_print)

        cycle = await apply_swapmod_event(self.session, cycle, RETRY_REQUESTED, event_id="event-4")

        self.assertEqual(cycle.state, READY_TO_RELEASE)
        self.assertFalse(cycle.retry_available)
        self.assertIsNone(cycle.retry_step)

    async def test_verification_failure_requires_manual_review(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-cycle-review", printer_id=101)
        cycle = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="event-1")
        cycle = await apply_swapmod_event(self.session, cycle, START_STEP, event_id="event-2", step=RELEASE_PLATE)
        cycle = await apply_swapmod_event(self.session, cycle, STEP_MOCK_SUCCEEDED, event_id="event-3", step=RELEASE_PLATE)

        cycle = await apply_swapmod_event(
            self.session,
            cycle,
            VERIFY_FAILED,
            event_id="event-4",
            step=VERIFY_PLATE_RELEASED,
            verification_source="manual",
            verification_result="fail",
        )

        self.assertEqual(cycle.state, MANUAL_REVIEW_REQUIRED)
        self.assertTrue(cycle.manual_review_required)
        self.assertFalse(cycle.ready_for_next_print)
        self.assertFalse(cycle.retry_available)
        self.assertIn("verification failed", cycle.blocked_reason.lower())

    async def test_timeout_blocks_cycle_safely(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-cycle-timeout", printer_id=101)
        cycle = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="event-1")

        cycle = await apply_swapmod_event(self.session, cycle, TIMEOUT, event_id="event-timeout")

        self.assertEqual(cycle.state, BLOCKED_TIMEOUT)
        self.assertTrue(cycle.manual_review_required)
        self.assertFalse(cycle.ready_for_next_print)
        self.assertIn("timeout", cycle.blocked_reason.lower())

    async def test_restart_during_active_step_requires_manual_review(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-cycle-restart", printer_id=101)
        cycle = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="event-1")
        cycle = await apply_swapmod_event(self.session, cycle, START_STEP, event_id="event-2", step=RELEASE_PLATE)
        self.assertEqual(cycle.state, RELEASING_PLATE)

        cycle = await recover_swapmod_cycle_after_restart(self.session, cycle, event_id="event-restart")

        self.assertEqual(cycle.state, MANUAL_REVIEW_REQUIRED)
        self.assertTrue(cycle.manual_review_required)
        self.assertFalse(cycle.ready_for_next_print)
        self.assertEqual(cycle.transition_log[-1]["event"], PROCESS_RESTARTED)

    async def test_duplicate_event_is_idempotent(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-cycle-duplicate", printer_id=101)

        first = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="same-event")
        first_log = list(first.transition_log)
        second = await apply_swapmod_event(self.session, first, PRINT_FINISHED, event_id="same-event")

        self.assertEqual(second.state, READY_TO_RELEASE)
        self.assertEqual(second.transition_count, 1)
        self.assertEqual(second.transition_log, first_log)
        self.assertEqual(second.seen_event_ids, ["same-event"])

    async def test_invalid_transition_blocks_unknown_state(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-cycle-invalid", printer_id=101)

        cycle = await apply_swapmod_event(self.session, cycle, STEP_MOCK_SUCCEEDED, event_id="event-invalid")

        self.assertEqual(cycle.state, BLOCKED_UNKNOWN_STATE)
        self.assertTrue(cycle.manual_review_required)
        self.assertFalse(cycle.ready_for_next_print)
        self.assertIn("invalid transition", cycle.blocked_reason.lower())

    async def test_state_machine_never_creates_queue_or_print_log_entries(self) -> None:
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)

        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-cycle-no-dispatch", printer_id=101)
        cycle = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="event-1")
        cycle = await apply_swapmod_event(self.session, cycle, START_STEP, event_id="event-2", step=RELEASE_PLATE)
        cycle = await apply_swapmod_event(self.session, cycle, STEP_MOCK_SUCCEEDED, event_id="event-3", step=RELEASE_PLATE)

        self.assertEqual(cycle.state, VERIFY_RELEASED)
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)

    async def test_operator_trigger_starts_cycle_at_ready_to_release_without_real_commands(self) -> None:
        cycle = await create_swapmod_operator_trigger(
            self.session,
            trigger_key="operator-trigger-001",
            cycle_key="swapmod-operator-cycle",
            printer_id=101,
            source_print_run_id="print-run-operator-001",
            operator_intent="START_SWAPMOD_PLATE_CHANGE",
        )
        payload = public_swapmod_cycle(cycle)

        self.assertEqual(cycle.state, READY_TO_RELEASE)
        self.assertEqual(cycle.current_step, RELEASE_PLATE)
        self.assertEqual(cycle.transition_count, 1)
        self.assertEqual(cycle.transition_log[-1]["event"], PRINT_FINISHED)
        self.assertFalse(payload["ready_for_next_print"])
        self.assertFalse(payload["manual_review_required"])
        self.assertFalse(payload["retry_available"])
        self.assertFalse(payload["real_execution_supported"])
        self.assertFalse(payload["printer_command_sent"])
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)

    async def test_operator_trigger_is_idempotent_by_trigger_key(self) -> None:
        first = await create_swapmod_operator_trigger(
            self.session,
            trigger_key="operator-trigger-duplicate",
            cycle_key="swapmod-operator-duplicate",
            printer_id=101,
            source_print_run_id="print-run-operator-duplicate",
            operator_intent="START_SWAPMOD_PLATE_CHANGE",
        )
        first_log = list(first.transition_log)

        second = await create_swapmod_operator_trigger(
            self.session,
            trigger_key="operator-trigger-duplicate",
            cycle_key="swapmod-operator-duplicate",
            printer_id=101,
            source_print_run_id="print-run-operator-duplicate",
            operator_intent="START_SWAPMOD_PLATE_CHANGE",
        )

        self.assertEqual(second.state, READY_TO_RELEASE)
        self.assertEqual(second.transition_count, 1)
        self.assertEqual(second.transition_log, first_log)

    async def test_verification_adapter_passes_released_plate_to_ready_to_load(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-verification-pass", printer_id=101)
        cycle = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="event-1")
        cycle = await apply_swapmod_event(self.session, cycle, START_STEP, event_id="event-2", step=RELEASE_PLATE)
        cycle = await apply_swapmod_event(self.session, cycle, STEP_MOCK_SUCCEEDED, event_id="event-3", step=RELEASE_PLATE)

        cycle = await apply_swapmod_verification(
            self.session,
            cycle,
            verification_key="verification-pass-001",
            verification_source="manual",
            verification_result="pass",
        )

        self.assertEqual(cycle.state, READY_TO_LOAD)
        self.assertEqual(cycle.current_step, LOAD_NEXT_PLATE)
        self.assertFalse(cycle.manual_review_required)
        self.assertFalse(cycle.ready_for_next_print)
        self.assertEqual(cycle.transition_log[-1]["event"], VERIFY_PASSED)
        self.assertEqual(cycle.transition_log[-1]["verification_source"], "manual")

    async def test_verification_adapter_failed_loaded_plate_requires_manual_review(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-verification-fail", printer_id=101)
        for event, event_id, step, verification_source, verification_result in (
            (PRINT_FINISHED, "event-1", None, None, None),
            (START_STEP, "event-2", RELEASE_PLATE, None, None),
            (STEP_MOCK_SUCCEEDED, "event-3", RELEASE_PLATE, None, None),
            (VERIFY_PASSED, "event-4", VERIFY_PLATE_RELEASED, "manual", "pass"),
            (START_STEP, "event-5", LOAD_NEXT_PLATE, None, None),
            (STEP_MOCK_SUCCEEDED, "event-6", LOAD_NEXT_PLATE, None, None),
        ):
            cycle = await apply_swapmod_event(
                self.session,
                cycle,
                event,
                event_id=event_id,
                step=step,
                verification_source=verification_source,
                verification_result=verification_result,
            )

        cycle = await apply_swapmod_verification(
            self.session,
            cycle,
            verification_key="verification-fail-001",
            verification_source="camera_mock",
            verification_result="fail",
        )

        self.assertEqual(cycle.state, MANUAL_REVIEW_REQUIRED)
        self.assertTrue(cycle.manual_review_required)
        self.assertFalse(cycle.ready_for_next_print)
        self.assertEqual(cycle.transition_log[-1]["event"], VERIFY_FAILED)
        self.assertEqual(cycle.transition_log[-1]["verification_source"], "camera_mock")

    async def test_transport_boundary_dry_run_success_advances_to_verification_without_real_send(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-transport-success", printer_id=101)
        cycle = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="event-1")

        result = await apply_swapmod_transport_step(
            self.session,
            cycle,
            transport_key="transport-success-001",
            step=RELEASE_PLATE,
            mock_result="success",
            dry_run=True,
            transport_enabled=True,
            allow_real_transport=False,
        )

        self.assertEqual(result["transport_status"], "DRY_RUN_STEP_COMPLETED")
        self.assertFalse(result["real_transport_supported"])
        self.assertFalse(result["real_command_sent"])
        self.assertEqual(result["state"], VERIFY_RELEASED)
        self.assertEqual(result["current_step"], VERIFY_PLATE_RELEASED)
        self.assertEqual(result["transition_log"][-2]["event"], START_STEP)
        self.assertEqual(result["transition_log"][-1]["event"], STEP_MOCK_SUCCEEDED)
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)

    async def test_transport_boundary_dry_run_failure_exposes_retry_without_real_send(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-transport-failure", printer_id=101)
        cycle = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="event-1")

        result = await apply_swapmod_transport_step(
            self.session,
            cycle,
            transport_key="transport-failure-001",
            step=RELEASE_PLATE,
            mock_result="failure",
            dry_run=True,
            transport_enabled=True,
            allow_real_transport=False,
        )

        self.assertEqual(result["transport_status"], "DRY_RUN_STEP_FAILED")
        self.assertFalse(result["real_transport_supported"])
        self.assertFalse(result["real_command_sent"])
        self.assertEqual(result["state"], RETRY_AVAILABLE)
        self.assertTrue(result["retry_available"])
        self.assertEqual(result["retry_step"], RELEASE_PLATE)

    async def test_transport_boundary_timeout_blocks_without_real_send(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-transport-timeout", printer_id=101)
        cycle = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="event-1")

        result = await apply_swapmod_transport_step(
            self.session,
            cycle,
            transport_key="transport-timeout-001",
            step=RELEASE_PLATE,
            mock_result="timeout",
            dry_run=True,
            transport_enabled=True,
            allow_real_transport=False,
        )

        self.assertEqual(result["transport_status"], "DRY_RUN_STEP_TIMEOUT")
        self.assertFalse(result["real_transport_supported"])
        self.assertFalse(result["real_command_sent"])
        self.assertEqual(result["state"], BLOCKED_TIMEOUT)
        self.assertTrue(result["manual_review_required"])

    async def test_canary_execution_gate_blocks_without_ready_cycle_or_operator_confirmation(self) -> None:
        cycle = await create_swapmod_operator_trigger(
            self.session,
            trigger_key="canary-gate-not-ready-trigger",
            cycle_key="swapmod-canary-gate-not-ready",
            printer_id=101,
            operator_intent="START_SWAPMOD_PLATE_CHANGE",
        )

        result = evaluate_swapmod_canary_execution_gate(
            cycle,
            gate_key="canary-gate-not-ready",
            canary_printer_alias="canary-alpha",
            requested_action="ARM_DRY_RUN",
            operator_approved=False,
            operator_approval_phrase=None,
            checklist={
                "operator_present": False,
                "canary_device_named": True,
                "camera_ready": True,
                "build_plate_clear": True,
                "emergency_stop_reachable": True,
                "dry_run_transport_verified": True,
            },
            gate_enabled=True,
            gate_dry_run=True,
            transport_enabled=True,
            transport_dry_run=True,
            allow_real_transport=False,
            allow_real_execution=False,
        )

        self.assertEqual(result["gate_status"], CANARY_GATE_BLOCKED)
        self.assertFalse(result["ready_for_canary"])
        self.assertIn("cycle_not_ready_for_next_print", result["blocked_reasons"])
        self.assertIn("operator_approval_missing", result["blocked_reasons"])
        self.assertIn("operator_phrase_mismatch", result["blocked_reasons"])
        self.assertIn("checklist_incomplete", result["blocked_reasons"])
        self.assertFalse(result["real_execution_supported"])
        self.assertFalse(result["real_command_sent"])
        self.assertFalse(result["printer_command_sent"])
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)

    async def test_canary_execution_gate_ready_only_after_verified_ready_cycle(self) -> None:
        cycle = await create_swapmod_operator_trigger(
            self.session,
            trigger_key="canary-gate-ready-trigger",
            cycle_key="swapmod-canary-gate-ready",
            printer_id=101,
            operator_intent="START_SWAPMOD_PLATE_CHANGE",
        )
        release = await apply_swapmod_transport_step(
            self.session,
            cycle,
            transport_key="canary-gate-release",
            step=RELEASE_PLATE,
            mock_result="success",
            dry_run=True,
            transport_enabled=True,
            allow_real_transport=False,
        )
        cycle = await get_cycle(self.session, release["cycle_key"])
        cycle = await apply_swapmod_verification(
            self.session,
            cycle,
            verification_key="canary-gate-release-verification",
            verification_source="manual",
            verification_result="pass",
        )
        load = await apply_swapmod_transport_step(
            self.session,
            cycle,
            transport_key="canary-gate-load",
            step=LOAD_NEXT_PLATE,
            mock_result="success",
            dry_run=True,
            transport_enabled=True,
            allow_real_transport=False,
        )
        cycle = await get_cycle(self.session, load["cycle_key"])
        cycle = await apply_swapmod_verification(
            self.session,
            cycle,
            verification_key="canary-gate-load-verification",
            verification_source="camera_mock",
            verification_result="pass",
        )
        phrase = required_swapmod_canary_approval_phrase(
            cycle_key="swapmod-canary-gate-ready",
            canary_printer_alias="canary-alpha",
        )

        result = evaluate_swapmod_canary_execution_gate(
            cycle,
            gate_key="canary-gate-ready",
            canary_printer_alias="canary-alpha",
            requested_action="ARM_DRY_RUN",
            operator_approved=True,
            operator_approval_phrase=phrase,
            checklist={
                "operator_present": True,
                "canary_device_named": True,
                "camera_ready": True,
                "build_plate_clear": True,
                "emergency_stop_reachable": True,
                "dry_run_transport_verified": True,
            },
            gate_enabled=True,
            gate_dry_run=True,
            transport_enabled=True,
            transport_dry_run=True,
            allow_real_transport=False,
            allow_real_execution=False,
        )

        self.assertEqual(result["gate_status"], CANARY_GATE_READY)
        self.assertTrue(result["ready_for_canary"])
        self.assertEqual(result["execution_mode"], "DRY_RUN_CANARY_GATE_ONLY")
        self.assertEqual(result["canary_printer_alias"], "canary-alpha")
        self.assertEqual(result["required_operator_approval_phrase"], phrase)
        self.assertEqual(result["blocked_reasons"], [])
        self.assertFalse(result["real_execution_supported"])
        self.assertFalse(result["real_command_sent"])
        self.assertFalse(result["printer_command_sent"])
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)

    async def test_canary_execution_gate_blocks_real_execution_and_real_transport_flags(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-canary-gate-flags", printer_id=101)
        phrase = required_swapmod_canary_approval_phrase(
            cycle_key="swapmod-canary-gate-flags",
            canary_printer_alias="canary-alpha",
        )

        result = evaluate_swapmod_canary_execution_gate(
            cycle,
            gate_key="canary-gate-flags",
            canary_printer_alias="canary-alpha",
            requested_action="ARM_DRY_RUN",
            operator_approved=True,
            operator_approval_phrase=phrase,
            checklist={
                "operator_present": True,
                "canary_device_named": True,
                "camera_ready": True,
                "build_plate_clear": True,
                "emergency_stop_reachable": True,
                "dry_run_transport_verified": True,
            },
            gate_enabled=True,
            gate_dry_run=False,
            transport_enabled=True,
            transport_dry_run=False,
            allow_real_transport=True,
            allow_real_execution=True,
        )

        self.assertEqual(result["gate_status"], CANARY_GATE_BLOCKED)
        self.assertIn("canary_gate_dry_run_required", result["blocked_reasons"])
        self.assertIn("transport_dry_run_required", result["blocked_reasons"])
        self.assertIn("real_transport_not_supported", result["blocked_reasons"])
        self.assertIn("real_execution_not_supported", result["blocked_reasons"])
        self.assertFalse(result["real_command_sent"])


if __name__ == "__main__":
    unittest.main()
