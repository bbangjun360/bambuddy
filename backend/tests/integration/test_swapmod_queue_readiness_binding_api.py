from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import swapmod_bed_readiness as bed_readiness_route
from backend.app.api.routes import swapmod_state_machine as swapmod_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.erp_draft_write import ErpDraftWriteRecord
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.models.swapmod_queue_readiness_binding import SwapmodQueueReadinessBinding
from backend.app.services.swapmod_queue_readiness_binding import (
    QUEUE_READINESS_BINDING_BLOCKED,
    QUEUE_READINESS_BINDING_READY,
)
from backend.app.services.swapmod_state_machine import LOAD_NEXT_PLATE, RELEASE_PLATE
from backend.tests.integration.test_plate_change_3mf_postprocess_api import ASGITransport, AsyncClient


class SwapmodQueueReadinessBindingApiTest(unittest.IsolatedAsyncioTestCase):
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
            swapmod_queue_readiness_binding,
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
            "farm_swapmod_queue_readiness_binding_enabled": (
                swapmod_route.settings.farm_swapmod_queue_readiness_binding_enabled
            ),
            "farm_bed_automation_enabled": bed_readiness_route.settings.farm_bed_automation_enabled,
            "farm_bed_automation_dry_run": bed_readiness_route.settings.farm_bed_automation_dry_run,
        }
        swapmod_route.settings.farm_swapmod_state_machine_enabled = True
        swapmod_route.settings.farm_swapmod_transport_enabled = True
        swapmod_route.settings.farm_swapmod_transport_dry_run = True
        swapmod_route.settings.farm_swapmod_allow_real_transport = False
        swapmod_route.settings.farm_swapmod_queue_readiness_binding_enabled = False
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

    async def queue_item_status(self, queue_item_id: int) -> str:
        async with self.sessionmaker() as session:
            item = await session.get(PrintQueueItem, queue_item_id)
            self.assertIsNotNone(item)
            return item.status

    async def assert_no_downstream_rows(self) -> None:
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 0)

    def enable_bed_readiness_handoff(self) -> None:
        bed_readiness_route.settings.farm_swapmod_bed_readiness_handoff_enabled = True
        bed_readiness_route.settings.farm_bed_automation_enabled = True
        bed_readiness_route.settings.farm_bed_automation_dry_run = True

    def enable_queue_readiness_binding(self) -> None:
        swapmod_route.settings.farm_swapmod_queue_readiness_binding_enabled = True
        bed_readiness_route.settings.farm_bed_automation_enabled = True
        bed_readiness_route.settings.farm_bed_automation_dry_run = True

    async def create_queue_item(
        self,
        *,
        printer_id: int | None = 101,
        status: str = "pending",
        archive_id: int | None = 808,
        library_file_id: int | None = None,
        plate_id: int | None = 1,
    ) -> int:
        async with self.sessionmaker() as session:
            item = PrintQueueItem(
                printer_id=printer_id,
                archive_id=archive_id,
                library_file_id=library_file_id,
                plate_id=plate_id,
                status=status,
                position=1,
            )
            session.add(item)
            await session.commit()
            return item.id

    async def create_ready_cycle(self, cycle_key: str) -> None:
        response = await self.client.post(
            "/api/v1/swapmod-state-machine/operator-triggers",
            json={
                "trigger_key": f"{cycle_key}-trigger",
                "cycle_key": cycle_key,
                "printer_id": 101,
                "source_print_run_id": "print-run-api-080",
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

    async def test_queue_readiness_binding_status_reports_safe_defaults(self) -> None:
        response = await self.client.get("/api/v1/swapmod-state-machine/queue-readiness-bindings/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["enabled"])
        self.assertTrue(body["record_only"])
        self.assertFalse(body["real_command_sent"])
        self.assertFalse(body["printer_command_sent"])
        self.assertFalse(body["queue_dispatch_supported"])
        self.assertFalse(body["scheduler_dispatch_supported"])

    async def test_queue_readiness_binding_is_disabled_by_default(self) -> None:
        await self.create_ready_cycle("api-binding-disabled")
        await self.record_bed_ready("api-binding-disabled")
        queue_item_id = await self.create_queue_item()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles/api-binding-disabled/queue-readiness-bindings",
            json={"binding_key": "api-binding-disabled-key", "queue_item_id": queue_item_id, "printer_id": 101},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 0)
        self.assertEqual(await self.queue_item_status(queue_item_id), "pending")
        await self.assert_no_downstream_rows()

    async def test_ready_cycle_bed_and_pending_queue_creates_binding_without_dispatch(self) -> None:
        await self.create_ready_cycle("api-binding-ready")
        await self.record_bed_ready("api-binding-ready")
        queue_item_id = await self.create_queue_item()
        self.enable_queue_readiness_binding()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles/api-binding-ready/queue-readiness-bindings",
            json={"binding_key": "api-binding-ready-key", "queue_item_id": queue_item_id, "printer_id": 101},
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["binding_status"], QUEUE_READINESS_BINDING_READY)
        self.assertTrue(body["queue_readiness_bound"])
        self.assertEqual(body["queue_item_id"], queue_item_id)
        self.assertEqual(body["blocked_reasons"], [])
        self.assertFalse(body["queue_dispatch_supported"])
        self.assertFalse(body["scheduler_dispatch_supported"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        self.assertEqual(await self.queue_item_status(queue_item_id), "pending")
        await self.assert_no_downstream_rows()

    async def test_missing_bed_record_returns_blocked_without_binding(self) -> None:
        await self.create_ready_cycle("api-binding-missing-bed")
        queue_item_id = await self.create_queue_item()
        self.enable_queue_readiness_binding()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles/api-binding-missing-bed/queue-readiness-bindings",
            json={"binding_key": "api-binding-missing-bed-key", "queue_item_id": queue_item_id, "printer_id": 101},
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["binding_status"], QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(body["queue_readiness_bound"])
        self.assertIn("bed_readiness_record_missing", body["blocked_reasons"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 0)
        self.assertEqual(await self.queue_item_status(queue_item_id), "pending")
        await self.assert_no_downstream_rows()


    async def test_queue_without_source_returns_blocked_without_binding(self) -> None:
        await self.create_ready_cycle("api-binding-source-missing")
        await self.record_bed_ready("api-binding-source-missing")
        queue_item_id = await self.create_queue_item(archive_id=None, library_file_id=None)
        self.enable_queue_readiness_binding()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles/api-binding-source-missing/queue-readiness-bindings",
            json={"binding_key": "api-binding-source-missing-key", "queue_item_id": queue_item_id, "printer_id": 101},
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["binding_status"], QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(body["queue_readiness_bound"])
        self.assertIn("queue_source_missing", body["blocked_reasons"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 0)
        self.assertEqual(await self.queue_item_status(queue_item_id), "pending")
        await self.assert_no_downstream_rows()

    async def test_schema_rejects_raw_command_and_dispatch_fields(self) -> None:
        await self.create_ready_cycle("api-binding-schema")
        queue_item_id = await self.create_queue_item()
        self.enable_queue_readiness_binding()

        response = await self.client.post(
            "/api/v1/swapmod-state-machine/cycles/api-binding-schema/queue-readiness-bindings",
            json={
                "binding_key": "api-binding-schema-key",
                "queue_item_id": queue_item_id,
                "printer_id": 101,
                "raw_gcode": "G28",
                "start_print": True,
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 0)
        self.assertEqual(await self.queue_item_status(queue_item_id), "pending")
        await self.assert_no_downstream_rows()


if __name__ == "__main__":
    unittest.main()
