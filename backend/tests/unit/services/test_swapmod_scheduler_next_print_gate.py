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
from backend.app.services.bed_automation import READY_FOR_NEXT_PRINT as BED_READY_FOR_NEXT_PRINT
from backend.app.services.swapmod_bed_readiness import record_swapmod_bed_readiness
from backend.app.services.swapmod_scheduler_next_print_gate import (
    SCHEDULER_NEXT_PRINT_GATE_ALLOWED,
    SCHEDULER_NEXT_PRINT_GATE_BLOCKED,
    evaluate_scheduler_next_print_gate,
    scheduler_print_run_key,
)
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


class SwapmodSchedulerNextPrintGateServiceTest(unittest.IsolatedAsyncioTestCase):
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

    async def create_print_log(self, printer_id: int = 101, *, status: str = "completed") -> PrintLogEntry:
        entry = PrintLogEntry(
            printer_id=printer_id,
            printer_name=f"Printer {printer_id}",
            print_name="Finished plate",
            status=status,
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def create_ready_swapmod_cycle(self, *, printer_id: int, source_print_run_id: str, cycle_key: str):
        cycle = await create_swapmod_cycle(
            self.session,
            cycle_key=cycle_key,
            printer_id=printer_id,
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

    async def record_ready_bed(self, cycle, *, handoff_key: str = "scheduler-handoff") -> None:
        await record_swapmod_bed_readiness(
            self.session,
            cycle,
            handoff_key=handoff_key,
            printer_id=cycle.printer_id,
            enabled=True,
            bed_automation_enabled=True,
            bed_automation_dry_run=True,
        )

    async def test_disabled_gate_allows_without_print_log(self) -> None:
        payload = await evaluate_scheduler_next_print_gate(
            self.session,
            printer_id=101,
            enabled=False,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_NEXT_PRINT_GATE_ALLOWED)
        self.assertTrue(payload["next_print_allowed"])
        self.assertFalse(payload["enforced"])
        self.assertEqual(payload["blocked_reasons"], [])

    async def test_enabled_gate_blocks_when_latest_print_log_is_missing(self) -> None:
        payload = await evaluate_scheduler_next_print_gate(
            self.session,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_NEXT_PRINT_GATE_BLOCKED)
        self.assertFalse(payload["next_print_allowed"])
        self.assertIn("last_print_run_missing", payload["blocked_reasons"])

    async def test_enabled_gate_blocks_when_swapmod_cycle_for_latest_run_is_missing(self) -> None:
        run = await self.create_print_log(printer_id=101)

        payload = await evaluate_scheduler_next_print_gate(
            self.session,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_NEXT_PRINT_GATE_BLOCKED)
        self.assertEqual(payload["latest_print_run_id"], scheduler_print_run_key(run.id))
        self.assertIn("swapmod_cycle_missing_for_last_print", payload["blocked_reasons"])

    async def test_ready_cycle_for_older_print_does_not_allow_newer_print(self) -> None:
        older = await self.create_print_log(printer_id=101)
        old_cycle = await self.create_ready_swapmod_cycle(
            printer_id=101,
            source_print_run_id=scheduler_print_run_key(older.id),
            cycle_key="scheduler-old-ready",
        )
        await self.record_ready_bed(old_cycle, handoff_key="old-ready")
        newer = await self.create_print_log(printer_id=101)

        payload = await evaluate_scheduler_next_print_gate(
            self.session,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_NEXT_PRINT_GATE_BLOCKED)
        self.assertEqual(payload["latest_print_run_id"], scheduler_print_run_key(newer.id))
        self.assertIn("swapmod_cycle_missing_for_last_print", payload["blocked_reasons"])

    async def test_ready_cycle_and_bed_record_for_latest_run_allows_next_print(self) -> None:
        run = await self.create_print_log(printer_id=101)
        cycle = await self.create_ready_swapmod_cycle(
            printer_id=101,
            source_print_run_id=scheduler_print_run_key(run.id),
            cycle_key="scheduler-ready-latest",
        )
        await self.record_ready_bed(cycle, handoff_key="latest-ready")

        payload = await evaluate_scheduler_next_print_gate(
            self.session,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_NEXT_PRINT_GATE_ALLOWED)
        self.assertTrue(payload["next_print_allowed"])
        self.assertEqual(payload["blocked_reasons"], [])
        self.assertEqual(payload["latest_print_run_id"], scheduler_print_run_key(run.id))
        self.assertEqual(payload["source_cycle_key"], "scheduler-ready-latest")
        self.assertEqual(payload["bed_state"], BED_READY_FOR_NEXT_PRINT)

    async def create_startable_queue_item(self, *, printer_id: int | None = None) -> tuple[Printer, PrintQueueItem, Path]:
        printer = Printer(
            name="A1 Mini Scheduler Gate",
            ip_address="192.0.2.79",
            serial_number=f"WP079SERIAL{printer_id or 0}",
            access_code="12345678",
            model="A1 mini",
        )
        self.session.add(printer)
        await self.session.flush()
        if printer_id is not None:
            printer.id = printer_id

        relative_path = Path("archives") / f"wp079-{printer.id}.gcode.3mf"
        source_path = self.base_dir / relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"placeholder 3mf")
        archive = PrintArchive(
            printer_id=printer.id,
            filename=f"wp079-{printer.id}.gcode.3mf",
            print_name="WP079",
            file_path=str(relative_path),
            file_size=source_path.stat().st_size,
            status="completed",
        )
        self.session.add(archive)
        await self.session.flush()
        item = PrintQueueItem(printer_id=printer.id, archive_id=archive.id, status="pending", position=1)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(printer)
        await self.session.refresh(item)
        return printer, item, source_path

    async def run_start_print_with_successful_mocks(self, item: PrintQueueItem, *, gate_enabled: bool):
        from backend.app.services import print_scheduler as scheduler_module
        from backend.app.services.print_scheduler import PrintScheduler

        previous_gate_enabled = scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled
        previous_bed_enabled = scheduler_module.settings.farm_bed_automation_enabled
        previous_base_dir = scheduler_module.settings.base_dir
        scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = gate_enabled
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
                patch.object(scheduler_module, "spawn_background_task", MagicMock(side_effect=close_spawned_coroutine)) as spawn_mock,
                patch.object(scheduler_module, "cache_3mf_download", MagicMock()) as cache_mock,
                patch.dict("sys.modules", {"backend.app.main": SimpleNamespace(register_expected_print=register_mock)}),
                patch.object(scheduler_module.notification_service, "on_queue_job_started", AsyncMock()) as notify_mock,
                patch("backend.app.services.mqtt_relay.mqtt_relay.on_queue_job_started", AsyncMock()) as mqtt_mock,
            ):
                start_handled = await PrintScheduler()._start_print(self.session, item)
        finally:
            scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = previous_gate_enabled
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
            "mqtt": mqtt_mock,
        }

    async def test_start_print_disabled_gate_preserves_existing_upload_and_start_path(self) -> None:
        _printer, item, _source_path = await self.create_startable_queue_item()

        mocks = await self.run_start_print_with_successful_mocks(item, gate_enabled=False)

        self.assertTrue(mocks["start_handled"])
        mocks["delete"].assert_called_once()
        mocks["upload"].assert_called_once()
        mocks["register"].assert_called_once()
        mocks["clear"].assert_called_once_with(item.printer_id, False)
        mocks["start"].assert_called_once()
        mocks["spawn"].assert_called_once()
        mocks["cache"].assert_called_once()
        mocks["notify"].assert_awaited_once()
        mocks["mqtt"].assert_awaited_once()

        refreshed = (
            await self.session.execute(select(PrintQueueItem).where(PrintQueueItem.id == item.id))
        ).scalar_one()
        self.assertEqual(refreshed.status, "printing")
        self.assertIsNotNone(refreshed.started_at)

    async def test_start_print_enabled_ready_gate_allows_existing_upload_and_start_path(self) -> None:
        printer, item, _source_path = await self.create_startable_queue_item()
        run = await self.create_print_log(printer_id=printer.id)
        cycle = await self.create_ready_swapmod_cycle(
            printer_id=printer.id,
            source_print_run_id=scheduler_print_run_key(run.id),
            cycle_key="scheduler-start-ready",
        )
        await self.record_ready_bed(cycle, handoff_key="scheduler-start-ready")

        mocks = await self.run_start_print_with_successful_mocks(item, gate_enabled=True)

        self.assertTrue(mocks["start_handled"])
        mocks["upload"].assert_called_once()
        mocks["start"].assert_called_once()
        refreshed = (
            await self.session.execute(select(PrintQueueItem).where(PrintQueueItem.id == item.id))
        ).scalar_one()
        self.assertEqual(refreshed.status, "printing")

    async def test_start_print_blocks_before_upload_status_or_printer_start_when_gate_blocks(self) -> None:
        from backend.app.services import print_scheduler as scheduler_module
        from backend.app.services.print_scheduler import PrintScheduler

        printer, item, _source_path = await self.create_startable_queue_item()
        await self.create_print_log(printer_id=printer.id)

        previous_enabled = getattr(scheduler_module.settings, "farm_swapmod_scheduler_next_print_gate_enabled", False)
        previous_bed_enabled = scheduler_module.settings.farm_bed_automation_enabled
        previous_base_dir = scheduler_module.settings.base_dir
        scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = True
        scheduler_module.settings.farm_bed_automation_enabled = True
        scheduler_module.settings.base_dir = self.base_dir
        def close_spawned_coroutine(coro, *args, **kwargs):
            coro.close()
            return None

        register_mock = MagicMock()
        try:
            with (
                patch.object(scheduler_module.printer_manager, "is_connected", return_value=True),
                patch.object(scheduler_module.printer_manager, "set_awaiting_plate_clear", MagicMock()) as clear_mock,
                patch.object(scheduler_module.printer_manager, "start_print", MagicMock(side_effect=AssertionError("must not start printer"))) as start_mock,
                patch.object(scheduler_module, "delete_file_async", AsyncMock(side_effect=AssertionError("must not delete remote file"))) as delete_mock,
                patch.object(scheduler_module, "upload_file_async", AsyncMock(side_effect=AssertionError("must not upload file"))) as upload_mock,
            ):
                with self.assertLogs("backend.app.services.print_scheduler", level="WARNING") as captured:
                    start_handled = await PrintScheduler()._start_print(self.session, item)
        finally:
            scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = previous_enabled
            scheduler_module.settings.farm_bed_automation_enabled = previous_bed_enabled
            scheduler_module.settings.base_dir = previous_base_dir

        self.assertFalse(start_handled)
        self.assertIn("SwapMod scheduler next-print gate blocked", "\n".join(captured.output))
        clear_mock.assert_not_called()
        start_mock.assert_not_called()
        delete_mock.assert_not_called()
        upload_mock.assert_not_called()

        refreshed = (
            await self.session.execute(select(PrintQueueItem).where(PrintQueueItem.id == item.id))
        ).scalar_one()
        self.assertEqual(refreshed.status, "pending")
        self.assertIsNone(refreshed.started_at)

    async def test_check_queue_does_not_mark_sjf_jump_when_gate_blocks(self) -> None:
        from backend.app.services import print_scheduler as scheduler_module
        from backend.app.services.print_scheduler import PrintScheduler

        older = PrintQueueItem(
            printer_id=101,
            archive_id=1,
            status="pending",
            position=1,
            print_time_seconds=1000,
        )
        shorter = PrintQueueItem(
            printer_id=101,
            archive_id=2,
            status="pending",
            position=2,
            print_time_seconds=100,
        )
        self.session.add_all([older, shorter])
        await self.session.commit()

        scheduler = PrintScheduler()
        with (
            patch("backend.app.services.print_scheduler.async_session", self.sessionmaker),
            patch.object(scheduler, "_get_bool_setting", AsyncMock(side_effect=[True, False])),
            patch.object(scheduler, "_is_printer_idle", return_value=True),
            patch.object(scheduler, "_compute_ams_mapping_for_printer", AsyncMock(return_value=None)),
            patch.object(scheduler, "_block_on_filament_deficit", AsyncMock(return_value=False)),
            patch.object(scheduler, "_start_print", AsyncMock(return_value=False)) as start_mock,
            patch.object(scheduler, "_check_auto_drying", AsyncMock()),
            patch.object(scheduler_module.printer_manager, "is_connected", return_value=True),
        ):
            await scheduler.check_queue()

        start_mock.assert_awaited_once()
        refreshed = (
            await self.session.execute(select(PrintQueueItem).order_by(PrintQueueItem.position))
        ).scalars().all()
        self.assertFalse(refreshed[0].been_jumped)
        self.assertFalse(refreshed[1].been_jumped)
        self.assertEqual([item.status for item in refreshed], ["pending", "pending"])


if __name__ == "__main__":
    unittest.main()
