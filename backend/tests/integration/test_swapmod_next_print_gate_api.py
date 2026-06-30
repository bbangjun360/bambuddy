from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import swapmod_bed_readiness as bed_readiness_route
from backend.app.api.routes import swapmod_state_machine as swapmod_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.erp_draft_write import ErpDraftWriteRecord
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.services.swapmod_next_print_gate import NEXT_PRINT_GATE_BLOCKED, NEXT_PRINT_GATE_READY
from backend.app.services.swapmod_state_machine import LOAD_NEXT_PLATE, RELEASE_PLATE
from backend.tests.integration.test_plate_change_3mf_postprocess_api import ASGITransport, AsyncClient


class SwapmodNextPrintGateApiTest(unittest.IsolatedAsyncioTestCase):
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

        self.previous_values = {
            "farm_swapmod_state_machine_enabled": swapmod_route.settings.farm_swapmod_state_machine_enabled,
            "farm_swapmod_transport_enabled": swapmod_route.settings.farm_swapmod_transport_enabled,
            "farm_swapmod_transport_dry_run": swapmod_route.settings.farm_swapmod_transport_dry_run,
            "farm_swapmod_allow_real_transport": swapmod_route.settings.farm_swapmod_allow_real_transport,
            "farm_swapmod_bed_readiness_handoff_enabled": (
                bed_readiness_route.settings.farm_swapmod_bed_readiness_handoff_enabled
            ),
            "farm_swapmod_next_print_gate_enabled": swapmod_route.settings.farm_swapmod_next_print_gate_enabled,
            "farm_bed_automation_enabled": bed_readiness_route.settings.farm_bed_automation_enabled,
            "farm_bed_automation_dry_run": bed_readiness_route.settings.farm_bed_automation_dry_run,
        }
        swapmod_route.settings.farm_swapmod_state_machine_enabled = True
        swapmod_route.settings.farm_swapmod_transport_enabled = True
        swapmod_route.settings.farm_swapmod_transport_dry_run = True
        swapmod_route.settings.farm_swapmod_allow_real_transport = False
        swapmod_route.settings.farm_swapmod_next_print_gate_enabled = False
        bed_readiness_route.settings.farm_swapmod_bed_readiness_handoff_enabled = False
        bed_readiness_route.settings.farm_bed_automation_enabled = True
        bed_readiness_route.settings.farm_bed_automation_dry_run = True
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        for name, value in self.previous_values.items():
            setattr(swapmod_route.settings, name, value)
            setattr(bed_readiness_route.settings, name, value)
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def count_rows(self, model) -> int:
        async with self.sessionmaker() as session:
            return int((await session.execute(select(func.count()).select_from(model))).scalar_one())

    async def assert_no_dispatch_or_downstream_rows(self) -> None:
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 0)

    def enable_bed_readiness_handoff(self) -> None:
        bed_readiness_route.settings.farm_swapmod_bed_readiness_handoff_enabled = True
        bed_readiness_route.settings.farm_bed_automation_enabled = True
        bed_readiness_route.settings.farm_bed_automation_dry_run = True

    def enable_next_print_gate(self) -> None:
        swapmod_route.settings.farm_swapmod_next_print_gate_enabled = True
        bed_readiness_route.settings.farm_bed_automation_enabled = True
        bed_readiness_route.settings.farm_bed_automation_dry_run = True

    async def create_ready_cycle(self, cycle_key: str) -> None:
        response = await self.client.post(
            "/api/v1/swapmod-state-machine/operator-triggers",
            json={
                "trigger_key": f"{cycle_key}-trigger",
                "cycle_key": cycle_key,
                "printer_id": 101,
                "source_print_run_id": "print-run-api-078",
                "operator_intent": "START_SWAPMOD_PLATE_CHANGE",
            },
        )
        self.assertEqual(response.status_code, 202, response.text)
        for suffix, step in (("release", RELEASE_PLATE), ("load", LOAD_NEXT_PLATE)):
            transport_response = await self.client.post(
                f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/transport-steps",
                json={"transport_key": f"{cycle_key}-{suffix}", "step": step, "mock_result": "success"},
            )
            self.assertEqual(transport_response.status_code, 202, transport_response.text)
            verification_response = await self.client.post(
                f"/api/v1/swapmod-state-machine/cycles/{cycle_key}/verifications",
                json={
                    "verification_key": f"{cycle_key}-{suffix}-verification",
                    "verification_source": "manual",
                    "verification_result": "pass",
                },
            )
            self.assertEqual(verification_response.status_code, 200, verification_response.text)

    async def record_bed_ready(self, cycle_key: str) -> None:
        self.enable_bed_readiness_handoff()
        response = await self.client.post(
            f"/api/v1/swapmod-bed-readiness/cycles/{cycle_key}/records",
            json={"handoff_key": f"{cycle_key}-handoff", "printer_id": 101},
        )
        self.assertEqual(response.status_code, 202, response.text)

    async def test_next_print_gate_status_reports_safe_defaults(self) -> None:
        response = await self.client.get("/api/v1/swapmod-state-machine/next-print-gates/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["enabled"])
        self.assertTrue(body["evaluate_only"])
        self.assertFalse(body["real_command_sent"])
        self.assertFalse(body["printer_command_sent"])
        self.assertFalse(body["queue_dispatch_supported"])
        self.assertFalse(body["scheduler_dispatch_supported"])

    async def test_next_print_gate_is_disabled_by_default(self) -> None:
        await self.create_ready_cycle("api-next-disabled")
        await self.record_bed_ready("api-next-disabled")

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles/api-next-disabled/next-print-gates",
            json={"gate_key": "api-next-disabled-gate", "printer_id": 101},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())
        self.assertEqual(await self.count_rows(BedAutomationCycle), 1)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_ready_swapmod_and_bed_record_returns_gate_ready_without_dispatch(self) -> None:
        await self.create_ready_cycle("api-next-ready")
        await self.record_bed_ready("api-next-ready")
        self.enable_next_print_gate()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles/api-next-ready/next-print-gates",
            json={"gate_key": "api-next-ready-gate", "printer_id": 101},
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["gate_status"], NEXT_PRINT_GATE_READY)
        self.assertTrue(body["next_print_allowed"])
        self.assertEqual(body["blocked_reasons"], [])
        self.assertFalse(body["queue_dispatch_supported"])
        self.assertFalse(body["scheduler_dispatch_supported"])
        self.assertEqual(await self.count_rows(BedAutomationCycle), 1)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_requested_printer_mismatch_returns_blocked_without_dispatch(self) -> None:
        await self.create_ready_cycle("api-next-printer-mismatch")
        await self.record_bed_ready("api-next-printer-mismatch")
        self.enable_next_print_gate()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles/api-next-printer-mismatch/next-print-gates",
            json={"gate_key": "api-next-printer-mismatch-gate", "printer_id": 202},
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["gate_status"], NEXT_PRINT_GATE_BLOCKED)
        self.assertFalse(body["next_print_allowed"])
        self.assertIn("printer_mismatch", body["blocked_reasons"])
        self.assertIn("bed_printer_mismatch", body["blocked_reasons"])
        self.assertEqual(await self.count_rows(BedAutomationCycle), 1)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_missing_bed_record_returns_blocked_without_mutation(self) -> None:
        await self.create_ready_cycle("api-next-missing-bed")
        self.enable_next_print_gate()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles/api-next-missing-bed/next-print-gates",
            json={"gate_key": "api-next-missing-bed-gate", "printer_id": 101},
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["gate_status"], NEXT_PRINT_GATE_BLOCKED)
        self.assertFalse(body["next_print_allowed"])
        self.assertIn("bed_readiness_record_missing", body["blocked_reasons"])
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_schema_rejects_raw_command_and_dispatch_fields(self) -> None:
        await self.create_ready_cycle("api-next-schema")
        self.enable_next_print_gate()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles/api-next-schema/next-print-gates",
            json={
                "gate_key": "api-next-schema-gate",
                "printer_id": 101,
                "raw_gcode": "G28",
                "start_print": True,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)
        await self.assert_no_dispatch_or_downstream_rows()


if __name__ == "__main__":
    unittest.main()
