from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.database import Base
from backend.app.models.archive import PrintArchive
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.models.printer import Printer
from backend.app.models.swapmod_queue_readiness_binding import SwapmodQueueReadinessBinding
from backend.app.services.bed_automation import READY_FOR_NEXT_PRINT as BED_READY_FOR_NEXT_PRINT
from backend.app.services.swapmod_bed_readiness import record_swapmod_bed_readiness
from backend.app.services.swapmod_queue_readiness_binding import bind_swapmod_queue_readiness
from backend.app.services.swapmod_scheduler_next_print_gate import scheduler_print_run_key
from backend.app.services.swapmod_state_machine import (
    LOAD_NEXT_PLATE,
    PRINT_FINISHED,
    RELEASE_PLATE,
    START_STEP,
    STEP_MOCK_SUCCEEDED,
    VERIFY_PASSED,
    VERIFY_PLATE_READY,
    VERIFY_PLATE_RELEASED,
    apply_swapmod_event,
    create_swapmod_cycle,
)


class SwapmodSchedulerHandoffChainTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        asyncio.get_running_loop().slow_callback_duration = 1.0
        from backend.app.models import (  # noqa: F401
            api_key,
            archive,
            auth_ephemeral,
            bed_automation,
            erp_draft_write,
            group,
            library,
            print_log,
            print_queue,
            printer,
            settings,
            swapmod_queue_readiness_binding,
            swapmod_state_machine,
            user,
        )

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.session = self.sessionmaker()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

    async def asyncTearDown(self) -> None:
        await self.session.close()
        self.temp_dir.cleanup()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def create_startable_queue_item(self) -> tuple[Printer, PrintQueueItem]:
        printer = Printer(
            name="A1 Mini Scheduler Handoff",
            ip_address="192.0.2.82",
            serial_number="WP082SERIAL",
            access_code="12345678",
            model="A1 mini",
        )
        self.session.add(printer)
        await self.session.flush()

        relative_path = Path("archives") / f"wp082-{printer.id}.gcode.3mf"
        source_path = self.base_dir / relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"placeholder 3mf")
        archive = PrintArchive(
            printer_id=printer.id,
            filename=f"wp082-{printer.id}.gcode.3mf",
            print_name="WP082",
            file_path=str(relative_path),
            file_size=source_path.stat().st_size,
            status="completed",
        )
        self.session.add(archive)
        await self.session.flush()
        item = PrintQueueItem(printer_id=printer.id, archive_id=archive.id, status="pending", position=1, plate_id=1)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(printer)
        await self.session.refresh(item)
        return printer, item

    async def create_print_log(self, printer: Printer, *, status: str = "completed") -> PrintLogEntry:
        entry = PrintLogEntry(
            printer_id=printer.id,
            printer_name=printer.name,
            print_name="Finished plate",
            status=status,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def create_ready_swapmod_cycle(self, *, printer: Printer, source_print_run_id: str, cycle_key: str):
        cycle = await create_swapmod_cycle(
            self.session,
            cycle_key=cycle_key,
            printer_id=printer.id,
            source_print_run_id=source_print_run_id,
        )
        for event, event_id, step, verification_source, verification_result in (
            (PRINT_FINISHED, "event-1", None, None, None),
            (START_STEP, "event-2", RELEASE_PLATE, None, None),
            (STEP_MOCK_SUCCEEDED, "event-3", RELEASE_PLATE, None, None),
            (VERIFY_PASSED, "event-4", VERIFY_PLATE_RELEASED, "manual", "pass"),
            (START_STEP, "event-5", LOAD_NEXT_PLATE, None, None),
            (STEP_MOCK_SUCCEEDED, "event-6", LOAD_NEXT_PLATE, None, None),
            (VERIFY_PASSED, "event-7", VERIFY_PLATE_READY, "camera_mock", "pass"),
        ):
            cycle = await apply_swapmod_event(
                self.session,
                cycle,
                event,
                event_id=f"{cycle_key}:{event_id}",
                step=step,
                verification_source=verification_source,
                verification_result=verification_result,
            )
        return cycle

    async def record_ready_bed_handoff(self, cycle) -> dict[str, object]:
        return await record_swapmod_bed_readiness(
            self.session,
            cycle,
            handoff_key=f"{cycle.cycle_key}-bed-ready",
            printer_id=cycle.printer_id,
            enabled=True,
            bed_automation_enabled=True,
            bed_automation_dry_run=True,
        )

    async def bind_queue_item_to_ready_handoff(
        self,
        *,
        cycle,
        item: PrintQueueItem,
        printer: Printer,
    ) -> dict[str, object]:
        return await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key=f"{cycle.cycle_key}-queue-binding",
            queue_item_id=item.id,
            printer_id=printer.id,
            enabled=True,
            bed_automation_enabled=True,
        )

    async def run_start_print_with_handoff_gates(self, item: PrintQueueItem):
        from backend.app.services import print_scheduler as scheduler_module
        from backend.app.services.print_scheduler import PrintScheduler

        previous_next_gate_enabled = scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled
        previous_binding_gate_enabled = scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled
        previous_bed_enabled = scheduler_module.settings.farm_bed_automation_enabled
        previous_base_dir = scheduler_module.settings.base_dir
        scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = True
        scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled = True
        scheduler_module.settings.farm_bed_automation_enabled = True
        scheduler_module.settings.base_dir = self.base_dir

        def close_spawned_coroutine(coro, *args, **kwargs):
            coro.close()
            return None

        register_mock = MagicMock()
        try:
            with (
                patch.object(scheduler_module.printer_manager, "is_connected", return_value=True),
                patch.object(
                    scheduler_module.printer_manager,
                    "get_status",
                    return_value=SimpleNamespace(state="IDLE", subtask_id="old-subtask", gcode_file=None),
                ),
                patch.object(scheduler_module.printer_manager, "set_awaiting_plate_clear", MagicMock()) as clear_mock,
                patch.object(scheduler_module.printer_manager, "start_print", MagicMock(return_value=True)) as start_mock,
                patch.object(scheduler_module, "get_ftp_retry_settings", AsyncMock(return_value=(False, 1, 0, 5))),
                patch.object(scheduler_module, "delete_file_async", AsyncMock(return_value=True)) as delete_mock,
                patch.object(scheduler_module, "upload_file_async", AsyncMock(return_value=True)) as upload_mock,
                patch.object(
                    scheduler_module,
                    "spawn_background_task",
                    MagicMock(side_effect=close_spawned_coroutine),
                ) as spawn_mock,
                patch.object(scheduler_module, "cache_3mf_download", MagicMock()) as cache_mock,
                patch.dict("sys.modules", {"backend.app.main": SimpleNamespace(register_expected_print=register_mock)}),
                patch.object(scheduler_module.notification_service, "on_queue_job_started", AsyncMock()) as notify_mock,
                patch.object(scheduler_module.notification_service, "on_queue_job_failed", AsyncMock()) as fail_notify_mock,
                patch("backend.app.services.mqtt_relay.mqtt_relay.on_queue_job_started", AsyncMock()) as mqtt_mock,
            ):
                start_handled = await PrintScheduler()._start_print(self.session, item)
        finally:
            scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = previous_next_gate_enabled
            scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled = previous_binding_gate_enabled
            scheduler_module.settings.farm_bed_automation_enabled = previous_bed_enabled
            scheduler_module.settings.base_dir = previous_base_dir

        return {
            "start_handled": start_handled,
            "clear": clear_mock,
            "start": start_mock,
            "delete": delete_mock,
            "upload": upload_mock,
            "spawn": spawn_mock,
            "cache": cache_mock,
            "register": register_mock,
            "notify": notify_mock,
            "fail_notify": fail_notify_mock,
            "mqtt": mqtt_mock,
        }

    async def run_start_print_expect_block_before_external_calls(self, item: PrintQueueItem) -> tuple[bool, str]:
        from backend.app.services import print_scheduler as scheduler_module
        from backend.app.services.print_scheduler import PrintScheduler

        previous_next_gate_enabled = scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled
        previous_binding_gate_enabled = scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled
        previous_bed_enabled = scheduler_module.settings.farm_bed_automation_enabled
        previous_base_dir = scheduler_module.settings.base_dir
        scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = True
        scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled = True
        scheduler_module.settings.farm_bed_automation_enabled = True
        scheduler_module.settings.base_dir = self.base_dir
        try:
            with (
                patch.object(scheduler_module.printer_manager, "is_connected", return_value=True),
                patch.object(
                    scheduler_module.printer_manager,
                    "set_awaiting_plate_clear",
                    MagicMock(side_effect=AssertionError("must not clear bed state")),
                ),
                patch.object(
                    scheduler_module.printer_manager,
                    "start_print",
                    MagicMock(side_effect=AssertionError("must not start printer")),
                ),
                patch.object(
                    scheduler_module,
                    "get_ftp_retry_settings",
                    AsyncMock(side_effect=AssertionError("must not request FTP settings")),
                ),
                patch.object(
                    scheduler_module,
                    "delete_file_async",
                    AsyncMock(side_effect=AssertionError("must not delete remote file")),
                ),
                patch.object(
                    scheduler_module,
                    "upload_file_async",
                    AsyncMock(side_effect=AssertionError("must not upload file")),
                ),
            ):
                with self.assertLogs("backend.app.services.print_scheduler", level="WARNING") as captured:
                    start_handled = await PrintScheduler()._start_print(self.session, item)
        finally:
            scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = previous_next_gate_enabled
            scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled = previous_binding_gate_enabled
            scheduler_module.settings.farm_bed_automation_enabled = previous_bed_enabled
            scheduler_module.settings.base_dir = previous_base_dir

        return start_handled, "\n".join(captured.output)

    async def test_same_latest_run_bed_readiness_and_queue_binding_start_and_consume_once(self) -> None:
        printer, item = await self.create_startable_queue_item()
        run = await self.create_print_log(printer)
        cycle = await self.create_ready_swapmod_cycle(
            printer=printer,
            source_print_run_id=scheduler_print_run_key(run.id),
            cycle_key=f"wp082-ready-cycle-{run.id}",
        )
        bed_payload = await self.record_ready_bed_handoff(cycle)
        binding_payload = await self.bind_queue_item_to_ready_handoff(cycle=cycle, item=item, printer=printer)

        mocks = await self.run_start_print_with_handoff_gates(item)

        self.assertEqual(bed_payload["bed_state"], BED_READY_FOR_NEXT_PRINT)
        self.assertEqual(binding_payload["source_print_run_id"], scheduler_print_run_key(run.id))
        self.assertTrue(mocks["start_handled"])
        mocks["delete"].assert_awaited_once()
        mocks["upload"].assert_awaited_once()
        mocks["register"].assert_called_once()
        mocks["clear"].assert_called_once_with(printer.id, False)
        mocks["start"].assert_called_once()
        mocks["spawn"].assert_called_once()
        mocks["cache"].assert_called_once()
        mocks["notify"].assert_awaited_once()
        mocks["mqtt"].assert_awaited_once()
        mocks["fail_notify"].assert_not_awaited()

        refreshed = await self.session.get(PrintQueueItem, item.id)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "printing")
        self.assertIsNotNone(refreshed.started_at)
        binding = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert binding is not None
        self.assertIsNotNone(binding.consumed_at)

    async def test_mismatched_latest_run_and_queue_binding_block_before_upload_or_start(self) -> None:
        printer, item = await self.create_startable_queue_item()
        latest_run = await self.create_print_log(printer)
        latest_cycle = await self.create_ready_swapmod_cycle(
            printer=printer,
            source_print_run_id=scheduler_print_run_key(latest_run.id),
            cycle_key=f"wp082-latest-cycle-{latest_run.id}",
        )
        await self.record_ready_bed_handoff(latest_cycle)
        other_cycle = await self.create_ready_swapmod_cycle(
            printer=printer,
            source_print_run_id="print-run-wp082-other",
            cycle_key="wp082-other-binding-cycle",
        )
        other_bed_payload = await self.record_ready_bed_handoff(other_cycle)
        binding_payload = await self.bind_queue_item_to_ready_handoff(cycle=other_cycle, item=item, printer=printer)

        start_handled, logs = await self.run_start_print_expect_block_before_external_calls(item)

        self.assertEqual(other_bed_payload["bed_state"], BED_READY_FOR_NEXT_PRINT)
        self.assertNotEqual(binding_payload["source_print_run_id"], scheduler_print_run_key(latest_run.id))
        self.assertNotEqual(binding_payload["source_cycle_key"], latest_cycle.cycle_key)
        self.assertFalse(start_handled)
        self.assertIn("SwapMod scheduler handoff chain blocked", logs)
        self.assertIn("scheduler_handoff_source_print_run_mismatch", logs)
        self.assertIn("scheduler_handoff_source_cycle_mismatch", logs)
        refreshed = await self.session.get(PrintQueueItem, item.id)
        assert refreshed is not None
        self.assertEqual(refreshed.status, "pending")
        self.assertIsNone(refreshed.started_at)
        binding = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert binding is not None
        self.assertIsNone(binding.consumed_at)


if __name__ == "__main__":
    unittest.main()
