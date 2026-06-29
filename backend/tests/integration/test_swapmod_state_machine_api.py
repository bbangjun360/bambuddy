from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import swapmod_state_machine as swapmod_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.erp_draft_write import ErpDraftWriteRecord
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.models.swapmod_state_machine import SwapmodStateMachineCycle
from backend.app.services.swapmod_state_machine import (
    BLOCKED_TIMEOUT,
    LOAD_NEXT_PLATE,
    PRINT_FINISHED,
    READY_FOR_NEXT_PRINT,
    READY_TO_RELEASE,
    READY_TO_LOAD,
    RELEASE_PLATE,
    RETRY_AVAILABLE,
    RETRY_REQUESTED,
    START_STEP,
    STEP_MOCK_FAILED,
    STEP_MOCK_SUCCEEDED,
    VERIFY_FAILED,
    VERIFY_PASSED,
    VERIFY_RELEASED,
    VERIFY_PLATE_READY,
    VERIFY_PLATE_RELEASED,
)
from backend.tests.integration.test_plate_change_3mf_postprocess_api import ASGITransport, AsyncClient


class SwapmodStateMachineApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
            bed_automation,
            erp_draft_write,
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

        async def override_get_db():
            async with self.sessionmaker() as session:
                try:
                    yield session
                    await session.commit()
                except BaseException:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        self.patches = [
            patch("backend.app.core.database.async_session", self.sessionmaker),
            patch("backend.app.core.auth.async_session", self.sessionmaker),
            patch("backend.app.main.async_session", self.sessionmaker),
        ]
        for patcher in self.patches:
            patcher.start()

        self.previous_enabled = swapmod_route.settings.farm_swapmod_state_machine_enabled
        self.previous_dry_run = swapmod_route.settings.farm_swapmod_state_machine_dry_run
        self.previous_transport_enabled = swapmod_route.settings.farm_swapmod_transport_enabled
        self.previous_transport_dry_run = swapmod_route.settings.farm_swapmod_transport_dry_run
        self.previous_allow_real_transport = swapmod_route.settings.farm_swapmod_allow_real_transport
        swapmod_route.settings.farm_swapmod_state_machine_enabled = False
        swapmod_route.settings.farm_swapmod_state_machine_dry_run = True
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        swapmod_route.settings.farm_swapmod_state_machine_enabled = self.previous_enabled
        swapmod_route.settings.farm_swapmod_state_machine_dry_run = self.previous_dry_run
        swapmod_route.settings.farm_swapmod_transport_enabled = self.previous_transport_enabled
        swapmod_route.settings.farm_swapmod_transport_dry_run = self.previous_transport_dry_run
        swapmod_route.settings.farm_swapmod_allow_real_transport = self.previous_allow_real_transport
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def count_rows(self, model) -> int:
        async with self.sessionmaker() as session:
            return int((await session.execute(select(func.count()).select_from(model))).scalar_one())

    async def assert_no_control_rows(self) -> None:
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 0)

    def enable_state_machine(self) -> None:
        swapmod_route.settings.farm_swapmod_state_machine_enabled = True


    def enable_transport_boundary(self) -> None:
        swapmod_route.settings.farm_swapmod_transport_enabled = True
        swapmod_route.settings.farm_swapmod_transport_dry_run = True
        swapmod_route.settings.farm_swapmod_allow_real_transport = False

    async def post_event(self, cycle_key: str, event_id: str, event: str, **overrides: object):
        payload: dict[str, object] = {"event_id": event_id, "event": event}
        payload.update(overrides)
        return await self.client.post(f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/events", json=payload)

    async def test_status_reports_safe_defaults_when_disabled(self) -> None:
        response = await self.client.get("/api/v1/swapmod-state-machine/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["enabled"])
        self.assertTrue(body["dry_run"])
        self.assertFalse(body["real_execution_supported"])
        self.assertFalse(body["printer_command_sent"])
        self.assertIn(PRINT_FINISHED, body["supported_events"])

    async def test_cycle_creation_is_disabled_by_default(self) -> None:
        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles",
            json={"cycle_key": "api-disabled-cycle", "printer_id": 101},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())
        self.assertEqual(await self.count_rows(SwapmodStateMachineCycle), 0)
        await self.assert_no_control_rows()

    async def test_operator_trigger_is_disabled_by_default(self) -> None:
        response = await self.client.post(
            "/api/v1/swapmod-state-machine/operator-triggers",
            json={
                "trigger_key": "api-trigger-disabled",
                "cycle_key": "api-trigger-disabled-cycle",
                "printer_id": 101,
                "source_print_run_id": "print-run-disabled",
                "operator_intent": "START_SWAPMOD_PLATE_CHANGE",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())
        self.assertEqual(await self.count_rows(SwapmodStateMachineCycle), 0)
        await self.assert_no_control_rows()

    async def test_enabled_cycle_can_reach_ready_for_next_print_without_sending_commands(self) -> None:
        self.enable_state_machine()
        cycle_key = "api-success-cycle"

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles",
            json={"cycle_key": cycle_key, "printer_id": 101, "source_print_run_id": "print-run-001"},
        )
        self.assertEqual(response.status_code, 202, response.text)
        self.assertFalse(response.json()["ready_for_next_print"])

        events = [
            ("event-1", PRINT_FINISHED, {}),
            ("event-2", START_STEP, {"step": RELEASE_PLATE}),
            ("event-3", STEP_MOCK_SUCCEEDED, {"step": RELEASE_PLATE}),
            (
                "event-4",
                VERIFY_PASSED,
                {"step": VERIFY_PLATE_RELEASED, "verification_source": "manual", "verification_result": "pass"},
            ),
            ("event-5", START_STEP, {"step": LOAD_NEXT_PLATE}),
            ("event-6", STEP_MOCK_SUCCEEDED, {"step": LOAD_NEXT_PLATE}),
            (
                "event-7",
                VERIFY_PASSED,
                {"step": VERIFY_PLATE_READY, "verification_source": "camera_mock", "verification_result": "pass"},
            ),
        ]
        body = None
        for event_id, event, extra in events:
            event_response = await self.post_event(cycle_key, event_id, event, **extra)
            self.assertEqual(event_response.status_code, 200, event_response.text)
            body = event_response.json()

        self.assertIsNotNone(body)
        self.assertEqual(body["state"], READY_FOR_NEXT_PRINT)
        self.assertTrue(body["ready_for_next_print"])
        self.assertFalse(body["manual_review_required"])
        self.assertFalse(body["retry_available"])
        self.assertFalse(body["real_execution_supported"])
        self.assertFalse(body["printer_command_sent"])
        await self.assert_no_control_rows()

    async def test_enabled_retry_and_manual_review_paths_are_explicit(self) -> None:
        self.enable_state_machine()
        cycle_key = "api-retry-cycle"
        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles",
            json={"cycle_key": cycle_key, "printer_id": 101},
        )
        self.assertEqual(response.status_code, 202, response.text)
        await self.post_event(cycle_key, "event-1", PRINT_FINISHED)
        await self.post_event(cycle_key, "event-2", START_STEP, step=RELEASE_PLATE)

        retry_response = await self.post_event(cycle_key, "event-3", STEP_MOCK_FAILED, step=RELEASE_PLATE)
        self.assertEqual(retry_response.status_code, 200, retry_response.text)
        self.assertTrue(retry_response.json()["retry_available"])

        retry_ready = await self.post_event(cycle_key, "event-4", RETRY_REQUESTED)
        self.assertEqual(retry_ready.status_code, 200, retry_ready.text)
        await self.post_event(cycle_key, "event-5", START_STEP, step=RELEASE_PLATE)
        await self.post_event(cycle_key, "event-6", STEP_MOCK_SUCCEEDED, step=RELEASE_PLATE)
        review_response = await self.post_event(
            cycle_key,
            "event-7",
            VERIFY_FAILED,
            step=VERIFY_PLATE_RELEASED,
            verification_source="manual",
            verification_result="fail",
        )
        self.assertEqual(review_response.status_code, 200, review_response.text)
        self.assertTrue(review_response.json()["manual_review_required"])
        self.assertFalse(review_response.json()["ready_for_next_print"])

    async def test_schema_rejects_raw_command_field(self) -> None:
        self.enable_state_machine()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles",
            json={"cycle_key": "api-raw-field", "printer_id": 101, "raw_command": "blocked"},
        )

        self.assertEqual(response.status_code, 422)

    async def test_operator_trigger_starts_ready_to_release_without_sending_commands(self) -> None:
        self.enable_state_machine()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/operator-triggers",
            json={
                "trigger_key": "api-trigger-001",
                "cycle_key": "api-trigger-cycle",
                "printer_id": 101,
                "source_print_run_id": "print-run-trigger-001",
                "operator_intent": "START_SWAPMOD_PLATE_CHANGE",
            },
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["state"], READY_TO_RELEASE)
        self.assertEqual(body["current_step"], RELEASE_PLATE)
        self.assertFalse(body["ready_for_next_print"])
        self.assertFalse(body["manual_review_required"])
        self.assertFalse(body["retry_available"])
        self.assertFalse(body["real_execution_supported"])
        self.assertFalse(body["printer_command_sent"])
        self.assertEqual(body["transition_log"][-1]["event"], PRINT_FINISHED)
        await self.assert_no_control_rows()

    async def test_operator_trigger_is_idempotent_by_trigger_key(self) -> None:
        self.enable_state_machine()
        payload = {
            "trigger_key": "api-trigger-duplicate",
            "cycle_key": "api-trigger-duplicate-cycle",
            "printer_id": 101,
            "source_print_run_id": "print-run-trigger-duplicate",
            "operator_intent": "START_SWAPMOD_PLATE_CHANGE",
        }

        first = await self.client.post("/api/v1/swapmod-state-machine/operator-triggers", json=payload)
        second = await self.client.post("/api/v1/swapmod-state-machine/operator-triggers", json=payload)

        self.assertEqual(first.status_code, 202, first.text)
        self.assertEqual(second.status_code, 202, second.text)
        self.assertEqual(second.json()["state"], READY_TO_RELEASE)
        self.assertEqual(second.json()["transition_count"], 1)
        self.assertEqual(second.json()["transition_log"], first.json()["transition_log"])

    async def test_operator_trigger_schema_rejects_raw_command_and_unknown_intent(self) -> None:
        self.enable_state_machine()
        raw_response = await self.client.post(
            "/api/v1/swapmod-state-machine/operator-triggers",
            json={
                "trigger_key": "api-trigger-raw",
                "cycle_key": "api-trigger-raw-cycle",
                "printer_id": 101,
                "operator_intent": "START_SWAPMOD_PLATE_CHANGE",
                "raw_command": "blocked",
            },
        )
        unknown_intent_response = await self.client.post(
            "/api/v1/swapmod-state-machine/operator-triggers",
            json={
                "trigger_key": "api-trigger-unknown",
                "cycle_key": "api-trigger-unknown-cycle",
                "printer_id": 101,
                "operator_intent": "START_NEXT_PRINT",
            },
        )

        self.assertEqual(raw_response.status_code, 422)
        self.assertEqual(unknown_intent_response.status_code, 422)

    async def test_verification_endpoint_applies_manual_pass_result(self) -> None:
        self.enable_state_machine()
        cycle_key = "api-verification-pass-cycle"
        create_response = await self.client.post(
            "/api/v1/swapmod-state-machine/operator-triggers",
            json={
                "trigger_key": "api-verification-trigger",
                "cycle_key": cycle_key,
                "printer_id": 101,
                "operator_intent": "START_SWAPMOD_PLATE_CHANGE",
            },
        )
        self.assertEqual(create_response.status_code, 202, create_response.text)
        await self.post_event(cycle_key, "event-start-release", START_STEP, step=RELEASE_PLATE)
        await self.post_event(cycle_key, "event-release-success", STEP_MOCK_SUCCEEDED, step=RELEASE_PLATE)

        response = await self.client.post(
            f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/verifications",
            json={
                "verification_key": "api-verification-pass",
                "verification_source": "manual",
                "verification_result": "pass",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["state"], READY_TO_LOAD)
        self.assertEqual(body["current_step"], LOAD_NEXT_PLATE)
        self.assertFalse(body["real_execution_supported"])
        self.assertFalse(body["printer_command_sent"])
        await self.assert_no_control_rows()

    async def test_verification_endpoint_applies_camera_mock_fail_result(self) -> None:
        self.enable_state_machine()
        cycle_key = "api-verification-fail-cycle"
        await self.client.post(
            "/api/v1/swapmod-state-machine/cycles",
            json={"cycle_key": cycle_key, "printer_id": 101},
        )
        await self.post_event(cycle_key, "event-1", PRINT_FINISHED)
        await self.post_event(cycle_key, "event-2", START_STEP, step=RELEASE_PLATE)
        await self.post_event(cycle_key, "event-3", STEP_MOCK_SUCCEEDED, step=RELEASE_PLATE)

        response = await self.client.post(
            f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/verifications",
            json={
                "verification_key": "api-verification-fail",
                "verification_source": "camera_mock",
                "verification_result": "fail",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["manual_review_required"])
        self.assertFalse(body["ready_for_next_print"])
        self.assertEqual(body["transition_log"][-1]["event"], VERIFY_FAILED)

    async def test_verification_endpoint_rejects_unknown_source_and_raw_command(self) -> None:
        self.enable_state_machine()
        cycle_key = "api-verification-schema-cycle"
        await self.client.post(
            "/api/v1/swapmod-state-machine/cycles",
            json={"cycle_key": cycle_key, "printer_id": 101},
        )

        source_response = await self.client.post(
            f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/verifications",
            json={
                "verification_key": "bad-source",
                "verification_source": "live_camera",
                "verification_result": "pass",
            },
        )
        raw_response = await self.client.post(
            f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/verifications",
            json={
                "verification_key": "raw-command",
                "verification_source": "manual",
                "verification_result": "pass",
                "raw_command": "blocked",
            },
        )

        self.assertEqual(source_response.status_code, 422)
        self.assertEqual(raw_response.status_code, 422)

    async def test_transport_boundary_is_disabled_by_default(self) -> None:
        self.enable_state_machine()
        cycle_key = "api-transport-disabled-cycle"
        await self.client.post(
            "/api/v1/swapmod-state-machine/cycles",
            json={"cycle_key": cycle_key, "printer_id": 101},
        )

        response = await self.client.post(
            f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/transport-steps",
            json={"transport_key": "api-transport-disabled", "step": RELEASE_PLATE, "mock_result": "success"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())

    async def test_transport_boundary_dry_run_success_returns_audit_and_verification_state(self) -> None:
        self.enable_state_machine()
        self.enable_transport_boundary()
        cycle_key = "api-transport-success-cycle"
        await self.client.post(
            "/api/v1/swapmod-state-machine/operator-triggers",
            json={
                "trigger_key": "api-transport-trigger",
                "cycle_key": cycle_key,
                "printer_id": 101,
                "operator_intent": "START_SWAPMOD_PLATE_CHANGE",
            },
        )

        response = await self.client.post(
            f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/transport-steps",
            json={"transport_key": "api-transport-success", "step": RELEASE_PLATE, "mock_result": "success"},
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["transport_status"], "DRY_RUN_STEP_COMPLETED")
        self.assertEqual(body["transport_mode"], "DRY_RUN")
        self.assertFalse(body["real_transport_supported"])
        self.assertFalse(body["real_command_sent"])
        self.assertFalse(body["printer_command_sent"])
        self.assertEqual(body["state"], VERIFY_RELEASED)
        self.assertEqual(body["current_step"], VERIFY_PLATE_RELEASED)
        await self.assert_no_control_rows()

    async def test_transport_boundary_dry_run_failure_and_timeout_paths_are_safe(self) -> None:
        self.enable_state_machine()
        self.enable_transport_boundary()
        failure_cycle = "api-transport-failure-cycle"
        timeout_cycle = "api-transport-timeout-cycle"
        for cycle_key in (failure_cycle, timeout_cycle):
            await self.client.post(
                "/api/v1/swapmod-state-machine/operator-triggers",
                json={
                    "trigger_key": f"{cycle_key}-trigger",
                    "cycle_key": cycle_key,
                    "printer_id": 101,
                    "operator_intent": "START_SWAPMOD_PLATE_CHANGE",
                },
            )

        failure = await self.client.post(
            f"/api/v1/swapmod-state-machine/cycles/{failure_cycle}/transport-steps",
            json={"transport_key": "api-transport-failure", "step": RELEASE_PLATE, "mock_result": "failure"},
        )
        timeout = await self.client.post(
            f"/api/v1/swapmod-state-machine/cycles/{timeout_cycle}/transport-steps",
            json={"transport_key": "api-transport-timeout", "step": RELEASE_PLATE, "mock_result": "timeout"},
        )

        self.assertEqual(failure.status_code, 202, failure.text)
        self.assertEqual(timeout.status_code, 202, timeout.text)
        self.assertEqual(failure.json()["state"], RETRY_AVAILABLE)
        self.assertTrue(failure.json()["retry_available"])
        self.assertEqual(timeout.json()["state"], BLOCKED_TIMEOUT)
        self.assertTrue(timeout.json()["manual_review_required"])

    async def test_transport_boundary_schema_rejects_unknown_step_and_result(self) -> None:
        self.enable_state_machine()
        self.enable_transport_boundary()
        cycle_key = "api-transport-schema-cycle"
        await self.client.post(
            "/api/v1/swapmod-state-machine/cycles",
            json={"cycle_key": cycle_key, "printer_id": 101},
        )

        step_response = await self.client.post(
            f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/transport-steps",
            json={"transport_key": "bad-step", "step": "SEND_RAW", "mock_result": "success"},
        )
        result_response = await self.client.post(
            f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/transport-steps",
            json={"transport_key": "bad-result", "step": RELEASE_PLATE, "mock_result": "real"},
        )

        self.assertEqual(step_response.status_code, 422)
        self.assertEqual(result_response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
