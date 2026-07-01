from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.database import Base
from backend.app.models.archive import PrintArchive
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.models.printer import Printer
from backend.app.models.swapmod_queue_readiness_binding import SwapmodQueueReadinessBinding
from backend.app.services.swapmod_bed_readiness import record_swapmod_bed_readiness
from backend.app.services.swapmod_queue_readiness_binding import bind_swapmod_queue_readiness
from backend.app.services.swapmod_scheduler_handoff_diagnostics import (
    evaluate_swapmod_scheduler_handoff_diagnostics,
)
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


class SwapmodSchedulerHandoffDiagnosticsTest(unittest.IsolatedAsyncioTestCase):
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
            name="A1 Mini Handoff Diagnostics",
            ip_address="192.0.2.84",
            serial_number="WP084SERIAL",
            access_code="12345678",
            model="A1 mini",
        )
        self.session.add(printer)
        await self.session.flush()

        relative_path = Path("archives") / f"wp084-{printer.id}.gcode.3mf"
        source_path = self.base_dir / relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(b"placeholder 3mf")
        archive = PrintArchive(
            printer_id=printer.id,
            filename=f"wp084-{printer.id}.gcode.3mf",
            print_name="WP084",
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

    async def create_print_log(self, printer: Printer) -> PrintLogEntry:
        entry = PrintLogEntry(
            printer_id=printer.id,
            printer_name=printer.name,
            print_name="Finished plate",
            status="completed",
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
        await record_swapmod_bed_readiness(
            self.session,
            cycle,
            handoff_key=f"{cycle.cycle_key}-bed-ready",
            printer_id=cycle.printer_id,
            enabled=True,
            bed_automation_enabled=True,
            bed_automation_dry_run=True,
        )
        return cycle

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

    async def evaluate_diagnostics(self, item: PrintQueueItem) -> dict[str, object]:
        return await evaluate_swapmod_scheduler_handoff_diagnostics(
            self.session,
            queue_item_id=item.id,
            printer_id=item.printer_id,
            scheduler_next_print_gate_enabled=True,
            scheduler_queue_readiness_binding_enabled=True,
            bed_automation_enabled=True,
        )

    async def test_ready_handoff_reports_start_allowed_without_consuming_binding(self) -> None:
        printer, item = await self.create_startable_queue_item()
        run = await self.create_print_log(printer)
        cycle = await self.create_ready_swapmod_cycle(
            printer=printer,
            source_print_run_id=scheduler_print_run_key(run.id),
            cycle_key=f"wp084-ready-cycle-{run.id}",
        )
        binding_payload = await self.bind_queue_item_to_ready_handoff(cycle=cycle, item=item, printer=printer)

        diagnostics = await self.evaluate_diagnostics(item)

        self.assertEqual(diagnostics["mode"], "SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS")
        self.assertEqual(diagnostics["gate_status"], "allowed")
        self.assertTrue(diagnostics["scheduler_start_allowed"])
        self.assertEqual(diagnostics["blocked_reasons"], [])
        self.assertEqual(diagnostics["handoff_identity_blocked_reasons"], [])
        self.assertEqual(
            diagnostics["diagnostics_summary"],
            {
                "contract_version": 1,
                "gate_status": "allowed",
                "scheduler_start_allowed": True,
                "primary_blocker": None,
                "primary_operator_action": None,
                "primary_operator_action_source": None,
                "blocked_reason_count": 0,
                "blocked_reason_sources": {
                    "scheduler_next_print_gate": [],
                    "scheduler_queue_readiness_binding_gate": [],
                    "handoff_identity": [],
                },
                "enforced_gates": [
                    "scheduler_next_print_gate",
                    "scheduler_queue_readiness_binding_gate",
                ],
                "handoff_identity_status": "matched",
                "read_only": True,
                "real_command_sent": False,
                "printer_command_sent": False,
                "scheduler_dispatch_supported": False,
            },
        )
        self.assertEqual(diagnostics["latest_print_run_id"], scheduler_print_run_key(run.id))
        self.assertEqual(diagnostics["source_cycle_key"], cycle.cycle_key)
        self.assertFalse(diagnostics["real_command_sent"])
        self.assertFalse(diagnostics["printer_command_sent"])
        self.assertFalse(diagnostics["queue_dispatch_supported"])
        self.assertFalse(diagnostics["scheduler_dispatch_supported"])

        binding = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert binding is not None
        self.assertIsNone(binding.consumed_at)
        await self.session.refresh(item)
        self.assertEqual(item.status, "pending")
        self.assertIsNone(item.started_at)

    async def test_consumed_binding_reports_blocked_without_mutating_queue(self) -> None:
        printer, item = await self.create_startable_queue_item()
        run = await self.create_print_log(printer)
        cycle = await self.create_ready_swapmod_cycle(
            printer=printer,
            source_print_run_id=scheduler_print_run_key(run.id),
            cycle_key=f"wp084-consumed-cycle-{run.id}",
        )
        binding_payload = await self.bind_queue_item_to_ready_handoff(cycle=cycle, item=item, printer=printer)
        binding = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert binding is not None
        consumed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        binding.consumed_at = consumed_at
        await self.session.commit()

        diagnostics = await self.evaluate_diagnostics(item)

        self.assertEqual(diagnostics["gate_status"], "blocked")
        self.assertFalse(diagnostics["scheduler_start_allowed"])
        self.assertIn("queue_readiness_binding_consumed", diagnostics["blocked_reasons"])
        self.assertEqual(
            diagnostics["scheduler_queue_readiness_binding_gate"]["blocked_reasons"],
            ["queue_readiness_binding_consumed"],
        )
        summary = diagnostics["diagnostics_summary"]
        self.assertEqual(summary["primary_blocker"], "queue_readiness_binding_consumed")
        self.assertEqual(summary["primary_operator_action"], "select_unconsumed_queue_binding")
        self.assertEqual(summary["primary_operator_action_source"], "scheduler_queue_readiness_binding_gate")
        self.assertEqual(summary["blocked_reason_count"], 1)
        self.assertEqual(
            summary["blocked_reason_sources"],
            {
                "scheduler_next_print_gate": [],
                "scheduler_queue_readiness_binding_gate": ["queue_readiness_binding_consumed"],
                "handoff_identity": [],
            },
        )
        self.assertEqual(summary["handoff_identity_status"], "matched")
        self.assertFalse(diagnostics["printer_command_sent"])
        still_consumed = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert still_consumed is not None
        self.assertEqual(still_consumed.consumed_at, consumed_at)
        await self.session.refresh(item)
        self.assertEqual(item.status, "pending")
        self.assertIsNone(item.started_at)

    async def test_missing_gate_identity_reports_summary_not_available(self) -> None:
        printer, item = await self.create_startable_queue_item()

        diagnostics = await self.evaluate_diagnostics(item)

        self.assertEqual(diagnostics["gate_status"], "blocked")
        self.assertFalse(diagnostics["scheduler_start_allowed"])
        summary = diagnostics["diagnostics_summary"]
        self.assertEqual(summary["handoff_identity_status"], "not_available")
        self.assertEqual(summary["primary_blocker"], "last_print_run_missing")
        self.assertEqual(summary["primary_operator_action"], "review_latest_print_log")
        self.assertEqual(summary["primary_operator_action_source"], "scheduler_next_print_gate")
        self.assertIn("last_print_run_missing", diagnostics["blocked_reasons"])
        self.assertIn("queue_readiness_binding_missing", diagnostics["blocked_reasons"])
        self.assertEqual(
            summary["blocked_reason_sources"],
            {
                "scheduler_next_print_gate": ["last_print_run_missing"],
                "scheduler_queue_readiness_binding_gate": ["queue_readiness_binding_missing"],
                "handoff_identity": [],
            },
        )
        self.assertFalse(diagnostics["printer_command_sent"])
        await self.session.refresh(item)
        self.assertEqual(item.status, "pending")
        self.assertIsNone(item.started_at)

    async def test_mismatched_gate_identity_reports_handoff_chain_blocked_reasons(self) -> None:
        printer, item = await self.create_startable_queue_item()
        latest_run = await self.create_print_log(printer)
        latest_cycle = await self.create_ready_swapmod_cycle(
            printer=printer,
            source_print_run_id=scheduler_print_run_key(latest_run.id),
            cycle_key=f"wp084-latest-cycle-{latest_run.id}",
        )
        stale_cycle = await self.create_ready_swapmod_cycle(
            printer=printer,
            source_print_run_id="print_log:stale",
            cycle_key=f"wp084-stale-cycle-{latest_run.id}",
        )
        binding_payload = await self.bind_queue_item_to_ready_handoff(cycle=stale_cycle, item=item, printer=printer)

        diagnostics = await self.evaluate_diagnostics(item)

        self.assertEqual(diagnostics["gate_status"], "blocked")
        self.assertFalse(diagnostics["scheduler_start_allowed"])
        self.assertEqual(
            diagnostics["handoff_identity_blocked_reasons"],
            ["scheduler_handoff_source_print_run_mismatch", "scheduler_handoff_source_cycle_mismatch"],
        )
        self.assertIn("scheduler_handoff_source_print_run_mismatch", diagnostics["blocked_reasons"])
        self.assertIn("scheduler_handoff_source_cycle_mismatch", diagnostics["blocked_reasons"])
        summary = diagnostics["diagnostics_summary"]
        self.assertEqual(summary["primary_blocker"], "scheduler_handoff_source_print_run_mismatch")
        self.assertEqual(summary["primary_operator_action"], "review_handoff_print_run_identity")
        self.assertEqual(summary["primary_operator_action_source"], "handoff_identity")
        self.assertEqual(summary["blocked_reason_count"], 2)
        self.assertEqual(
            summary["blocked_reason_sources"],
            {
                "scheduler_next_print_gate": [],
                "scheduler_queue_readiness_binding_gate": [],
                "handoff_identity": [
                    "scheduler_handoff_source_print_run_mismatch",
                    "scheduler_handoff_source_cycle_mismatch",
                ],
            },
        )
        self.assertEqual(summary["handoff_identity_status"], "mismatch")
        self.assertEqual(diagnostics["latest_print_run_id"], scheduler_print_run_key(latest_run.id))
        self.assertEqual(diagnostics["source_cycle_key"], latest_cycle.cycle_key)
        self.assertEqual(
            diagnostics["scheduler_queue_readiness_binding_gate"]["source_cycle_key"],
            stale_cycle.cycle_key,
        )
        self.assertFalse(diagnostics["printer_command_sent"])
        binding = await self.session.get(SwapmodQueueReadinessBinding, binding_payload["binding_id"])
        assert binding is not None
        self.assertIsNone(binding.consumed_at)
        await self.session.refresh(item)
        self.assertEqual(item.status, "pending")
        self.assertIsNone(item.started_at)


if __name__ == "__main__":
    unittest.main()
