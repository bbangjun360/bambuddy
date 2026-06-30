from __future__ import annotations

import asyncio
import tempfile
from contextlib import nullcontext
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.database import Base
from backend.app.models.archive import PrintArchive
from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.print_queue import PrintQueueItem
from backend.app.models.printer import Printer
from backend.app.models.swapmod_queue_readiness_binding import SwapmodQueueReadinessBinding
from backend.app.services.swapmod_bed_readiness import record_swapmod_bed_readiness
from backend.app.services.swapmod_queue_readiness_binding import bind_swapmod_queue_readiness
from backend.app.services.swapmod_scheduler_queue_readiness_binding import (
    SCHEDULER_QUEUE_READINESS_BINDING_ALLOWED,
    SCHEDULER_QUEUE_READINESS_BINDING_BLOCKED,
    consume_scheduler_queue_readiness_binding,
    evaluate_scheduler_queue_readiness_binding_gate,
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


class SwapmodSchedulerQueueReadinessBindingServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        asyncio.get_running_loop().slow_callback_duration = 1.0
        from backend.app.models import (  # noqa: F401
            api_key,
            archive,
            auth_ephemeral,
            bed_automation,
            group,
            library,
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

    async def create_ready_swapmod_cycle(
        self,
        *,
        printer_id: int = 101,
        source_print_run_id: str = "print-run-081",
        cycle_key: str,
    ):
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

    async def record_ready_bed_cycle(self, cycle, *, handoff_key: str) -> None:
        await record_swapmod_bed_readiness(
            self.session,
            cycle,
            handoff_key=handoff_key,
            printer_id=cycle.printer_id,
            enabled=True,
            bed_automation_enabled=True,
            bed_automation_dry_run=True,
        )

    async def create_queue_item(
        self,
        *,
        printer_id: int | None = 101,
        status: str = "pending",
        archive_id: int | None = 303,
        library_file_id: int | None = None,
        plate_id: int | None = 1,
    ) -> PrintQueueItem:
        item = PrintQueueItem(
            printer_id=printer_id,
            archive_id=archive_id,
            library_file_id=library_file_id,
            plate_id=plate_id,
            status=status,
            position=1,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def create_ready_binding(
        self,
        *,
        cycle_key: str = "scheduler-binding-ready",
        binding_key: str = "scheduler-binding-ready-key",
        printer_id: int = 101,
        archive_id: int | None = 303,
        plate_id: int | None = 1,
    ) -> tuple[object, PrintQueueItem, dict[str, object]]:
        cycle = await self.create_ready_swapmod_cycle(printer_id=printer_id, cycle_key=cycle_key)
        await self.record_ready_bed_cycle(cycle, handoff_key=f"{cycle_key}-handoff")
        item = await self.create_queue_item(printer_id=printer_id, archive_id=archive_id, plate_id=plate_id)
        payload = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key=binding_key,
            queue_item_id=item.id,
            printer_id=printer_id,
            enabled=True,
            bed_automation_enabled=True,
        )
        return cycle, item, payload

    async def test_disabled_gate_allows_without_binding(self) -> None:
        item = await self.create_queue_item()

        payload = await evaluate_scheduler_queue_readiness_binding_gate(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            enabled=False,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_QUEUE_READINESS_BINDING_ALLOWED)
        self.assertTrue(payload["next_print_allowed"])
        self.assertFalse(payload["enforced"])
        self.assertEqual(payload["blocked_reasons"], [])
        self.assertFalse(payload["real_command_sent"])
        self.assertFalse(payload["printer_command_sent"])

    async def test_enabled_gate_blocks_when_binding_is_missing(self) -> None:
        item = await self.create_queue_item()

        payload = await evaluate_scheduler_queue_readiness_binding_gate(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(payload["next_print_allowed"])
        self.assertIn("queue_readiness_binding_missing", payload["blocked_reasons"])
        self.assertFalse(payload["real_command_sent"])
        self.assertFalse(payload["printer_command_sent"])

    async def test_enabled_gate_allows_ready_existing_binding(self) -> None:
        cycle, item, binding_payload = await self.create_ready_binding(cycle_key="scheduler-binding-allow")

        payload = await evaluate_scheduler_queue_readiness_binding_gate(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_QUEUE_READINESS_BINDING_ALLOWED)
        self.assertTrue(payload["next_print_allowed"])
        self.assertTrue(payload["enforced"])
        self.assertEqual(payload["binding_id"], binding_payload["binding_id"])
        self.assertEqual(payload["source_cycle_key"], cycle.cycle_key)
        self.assertEqual(payload["blocked_reasons"], [])

    async def test_enabled_gate_blocks_when_binding_was_already_consumed(self) -> None:
        _cycle, item, binding_payload = await self.create_ready_binding(cycle_key="scheduler-binding-consumed")
        binding = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert binding is not None
        binding.consumed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.session.flush()

        payload = await evaluate_scheduler_queue_readiness_binding_gate(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(payload["next_print_allowed"])
        self.assertIn("queue_readiness_binding_consumed", payload["blocked_reasons"])

    async def test_enabled_gate_replays_bed_readiness_and_blocks_when_stale(self) -> None:
        _cycle, item, _binding_payload = await self.create_ready_binding(cycle_key="scheduler-binding-stale-bed")
        bed = (await self.session.execute(select(BedAutomationCycle))).scalar_one()
        bed.ready_for_next_print = False
        bed.state = "MANUAL_REVIEW_REQUIRED"
        bed.manual_review_required = True
        await self.session.flush()

        payload = await evaluate_scheduler_queue_readiness_binding_gate(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(payload["next_print_allowed"])
        self.assertIn("bed_manual_review_required", payload["blocked_reasons"])
        self.assertIn("bed_not_ready_for_next_print", payload["blocked_reasons"])

    async def test_enabled_gate_replays_queue_fingerprint_and_blocks_when_changed(self) -> None:
        _cycle, item, _binding_payload = await self.create_ready_binding(
            cycle_key="scheduler-binding-stale-fingerprint",
            archive_id=901,
            plate_id=1,
        )
        item.archive_id = 902
        item.plate_id = 2
        await self.session.flush()

        payload = await evaluate_scheduler_queue_readiness_binding_gate(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(payload["next_print_allowed"])
        self.assertIn("queue_fingerprint_mismatch", payload["blocked_reasons"])

    async def test_enabled_gate_blocks_when_binding_identity_no_longer_matches_cycle(self) -> None:
        _cycle, item, binding_payload = await self.create_ready_binding(cycle_key="scheduler-binding-identity")
        other_cycle = await self.create_ready_swapmod_cycle(cycle_key="scheduler-binding-other-identity")
        await self.record_ready_bed_cycle(other_cycle, handoff_key="scheduler-binding-other-identity-handoff")
        binding = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert binding is not None
        binding.source_print_run_id = "different-print-run"
        binding.bed_cycle_key = "swapmod-bed-readiness:scheduler-binding-other-identity"
        await self.session.flush()

        payload = await evaluate_scheduler_queue_readiness_binding_gate(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], SCHEDULER_QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(payload["next_print_allowed"])
        self.assertIn("queue_readiness_binding_source_print_run_mismatch", payload["blocked_reasons"])
        self.assertIn("queue_readiness_binding_bed_cycle_mismatch", payload["blocked_reasons"])

    async def test_consume_marks_ready_binding_after_successful_start(self) -> None:
        _cycle, item, binding_payload = await self.create_ready_binding(cycle_key="scheduler-binding-consume")

        payload = await consume_scheduler_queue_readiness_binding(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            enabled=True,
        )

        self.assertTrue(payload["queue_readiness_binding_consumed"])
        self.assertEqual(payload["binding_id"], binding_payload["binding_id"])
        refreshed = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert refreshed is not None
        self.assertIsNotNone(refreshed.consumed_at)

    async def test_consume_blocks_when_binding_is_already_consumed(self) -> None:
        _cycle, item, binding_payload = await self.create_ready_binding(cycle_key="scheduler-binding-consume-once")
        first = await consume_scheduler_queue_readiness_binding(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            enabled=True,
        )
        self.assertTrue(first["queue_readiness_binding_consumed"])

        second = await consume_scheduler_queue_readiness_binding(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            enabled=True,
        )

        self.assertFalse(second["queue_readiness_binding_consumed"])
        self.assertEqual(second["binding_id"], binding_payload["binding_id"])
        self.assertIn("queue_readiness_binding_consumed", second["blocked_reasons"])

    async def create_startable_queue_item(self) -> tuple[Printer, PrintQueueItem, Path]:
        printer = Printer(
            name="A1 Mini Scheduler Binding",
            ip_address="192.0.2.81",
            serial_number="WP081SERIAL",
            access_code="12345678",
            model="A1 mini",
        )
        self.session.add(printer)
        await self.session.flush()

        relative_path = Path("archives") / f"wp081-{printer.id}.gcode.3mf"
        source_path = self.base_dir / relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"placeholder 3mf")
        archive = PrintArchive(
            printer_id=printer.id,
            filename=f"wp081-{printer.id}.gcode.3mf",
            print_name="WP081",
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

    async def create_ready_binding_for_startable_item(self, printer: Printer, item: PrintQueueItem) -> dict[str, object]:
        cycle = await self.create_ready_swapmod_cycle(
            printer_id=printer.id,
            source_print_run_id="print-run-wp081-start",
            cycle_key="scheduler-binding-start-ready",
        )
        await self.record_ready_bed_cycle(cycle, handoff_key="scheduler-binding-start-ready-handoff")
        return await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="scheduler-binding-start-ready-key",
            queue_item_id=item.id,
            printer_id=printer.id,
            enabled=True,
            bed_automation_enabled=True,
        )

    async def run_start_print_with_successful_mocks(
        self,
        item: PrintQueueItem,
        *,
        binding_gate_enabled: bool,
        start_print_return: bool = True,
        consume_result: dict[str, object] | None = None,
    ):
        from backend.app.services import print_scheduler as scheduler_module
        from backend.app.services.print_scheduler import PrintScheduler

        previous_next_gate_enabled = scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled
        previous_binding_gate_enabled = scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled
        previous_bed_enabled = scheduler_module.settings.farm_bed_automation_enabled
        previous_base_dir = scheduler_module.settings.base_dir
        scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = False
        scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled = binding_gate_enabled
        scheduler_module.settings.farm_bed_automation_enabled = True
        scheduler_module.settings.base_dir = self.base_dir

        def close_spawned_coroutine(coro, *args, **kwargs):
            coro.close()
            return None

        register_mock = MagicMock()
        consume_context = (
            patch.object(
                scheduler_module,
                "consume_scheduler_queue_readiness_binding",
                AsyncMock(return_value=consume_result),
            )
            if consume_result is not None
            else nullcontext(None)
        )
        try:
            with (
                patch.object(scheduler_module.printer_manager, "is_connected", return_value=True),
                patch.object(
                    scheduler_module.printer_manager,
                    "get_status",
                    return_value=SimpleNamespace(state="IDLE", subtask_id="old-subtask", gcode_file=None),
                ),
                patch.object(scheduler_module.printer_manager, "set_awaiting_plate_clear", MagicMock()) as clear_mock,
                patch.object(
                    scheduler_module.printer_manager,
                    "start_print",
                    MagicMock(return_value=start_print_return),
                ) as start_mock,
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
                consume_context as consume_mock,
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
            "consume": consume_mock,
        }

    async def test_start_print_disabled_binding_gate_preserves_existing_upload_and_start_path(self) -> None:
        _printer, item, _source_path = await self.create_startable_queue_item()

        mocks = await self.run_start_print_with_successful_mocks(item, binding_gate_enabled=False)

        self.assertTrue(mocks["start_handled"])
        mocks["upload"].assert_called_once()
        mocks["start"].assert_called_once()
        refreshed = (
            await self.session.execute(select(PrintQueueItem).where(PrintQueueItem.id == item.id))
        ).scalar_one()
        self.assertEqual(refreshed.status, "printing")

    async def test_start_print_enabled_binding_gate_blocks_before_upload_status_or_printer_start_when_missing(
        self,
    ) -> None:
        from backend.app.services import print_scheduler as scheduler_module
        from backend.app.services.print_scheduler import PrintScheduler

        _printer, item, _source_path = await self.create_startable_queue_item()
        previous_next_gate_enabled = scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled
        previous_binding_gate_enabled = scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled
        previous_bed_enabled = scheduler_module.settings.farm_bed_automation_enabled
        previous_base_dir = scheduler_module.settings.base_dir
        scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = False
        scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled = True
        scheduler_module.settings.farm_bed_automation_enabled = True
        scheduler_module.settings.base_dir = self.base_dir
        try:
            with (
                patch.object(scheduler_module.printer_manager, "is_connected", return_value=True),
                patch.object(scheduler_module.printer_manager, "set_awaiting_plate_clear", MagicMock()) as clear_mock,
                patch.object(
                    scheduler_module.printer_manager,
                    "start_print",
                    MagicMock(side_effect=AssertionError("must not start printer")),
                ) as start_mock,
                patch.object(
                    scheduler_module,
                    "delete_file_async",
                    AsyncMock(side_effect=AssertionError("must not delete remote file")),
                ) as delete_mock,
                patch.object(
                    scheduler_module,
                    "upload_file_async",
                    AsyncMock(side_effect=AssertionError("must not upload file")),
                ) as upload_mock,
            ):
                with self.assertLogs("backend.app.services.print_scheduler", level="WARNING") as captured:
                    start_handled = await PrintScheduler()._start_print(self.session, item)
        finally:
            scheduler_module.settings.farm_swapmod_scheduler_next_print_gate_enabled = previous_next_gate_enabled
            scheduler_module.settings.farm_swapmod_scheduler_queue_readiness_binding_enabled = previous_binding_gate_enabled
            scheduler_module.settings.farm_bed_automation_enabled = previous_bed_enabled
            scheduler_module.settings.base_dir = previous_base_dir

        self.assertFalse(start_handled)
        self.assertIn("SwapMod scheduler queue-readiness binding gate blocked", "\n".join(captured.output))
        clear_mock.assert_not_called()
        start_mock.assert_not_called()
        delete_mock.assert_not_called()
        upload_mock.assert_not_called()
        refreshed = (
            await self.session.execute(select(PrintQueueItem).where(PrintQueueItem.id == item.id))
        ).scalar_one()
        self.assertEqual(refreshed.status, "pending")
        self.assertIsNone(refreshed.started_at)

    async def test_start_print_enabled_ready_binding_allows_path_and_consumes_binding(self) -> None:
        printer, item, _source_path = await self.create_startable_queue_item()
        binding_payload = await self.create_ready_binding_for_startable_item(printer, item)

        mocks = await self.run_start_print_with_successful_mocks(item, binding_gate_enabled=True)

        self.assertTrue(mocks["start_handled"])
        mocks["upload"].assert_called_once()
        mocks["start"].assert_called_once()
        refreshed = (
            await self.session.execute(select(PrintQueueItem).where(PrintQueueItem.id == item.id))
        ).scalar_one()
        self.assertEqual(refreshed.status, "printing")
        binding = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert binding is not None
        self.assertIsNotNone(binding.consumed_at)

    async def test_start_print_logs_when_post_start_binding_consumption_returns_blocked(self) -> None:
        printer, item, _source_path = await self.create_startable_queue_item()
        await self.create_ready_binding_for_startable_item(printer, item)
        consume_result = {
            "queue_readiness_binding_consumed": False,
            "blocked_reasons": ["queue_readiness_binding_missing"],
            "binding_id": None,
            "queue_item_id": item.id,
            "printer_id": printer.id,
        }

        with self.assertLogs("backend.app.services.print_scheduler", level="WARNING") as captured:
            mocks = await self.run_start_print_with_successful_mocks(
                item,
                binding_gate_enabled=True,
                consume_result=consume_result,
            )

        self.assertTrue(mocks["start_handled"])
        assert mocks["consume"] is not None
        mocks["consume"].assert_awaited_once()
        logs = "\n".join(captured.output)
        self.assertIn("failed to consume SwapMod scheduler queue-readiness binding", logs)
        self.assertIn("queue_readiness_binding_missing", logs)

    async def test_start_print_does_not_consume_binding_when_printer_start_returns_false(self) -> None:
        printer, item, _source_path = await self.create_startable_queue_item()
        binding_payload = await self.create_ready_binding_for_startable_item(printer, item)

        with self.assertLogs("backend.app.services.print_scheduler", level="ERROR") as captured:
            mocks = await self.run_start_print_with_successful_mocks(
                item,
                binding_gate_enabled=True,
                start_print_return=False,
            )

        self.assertIn("Failed to start print", "\n".join(captured.output))
        self.assertTrue(mocks["start_handled"])
        mocks["upload"].assert_called_once()
        mocks["start"].assert_called_once()
        binding = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert binding is not None
        self.assertIsNone(binding.consumed_at)
        refreshed = (
            await self.session.execute(select(PrintQueueItem).where(PrintQueueItem.id == item.id))
        ).scalar_one()
        self.assertEqual(refreshed.status, "failed")


if __name__ == "__main__":
    unittest.main()
