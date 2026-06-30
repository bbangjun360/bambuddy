from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.database import Base
from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.erp_draft_write import ErpDraftWriteRecord
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.models.swapmod_queue_readiness_binding import SwapmodQueueReadinessBinding
from backend.app.services.bed_automation import READY_FOR_NEXT_PRINT
from backend.app.services.swapmod_bed_readiness import record_swapmod_bed_readiness
from backend.app.services.swapmod_queue_readiness_binding import (
    QUEUE_READINESS_BINDING_BLOCKED,
    QUEUE_READINESS_BINDING_READY,
    SwapmodQueueReadinessBindingError,
    bind_swapmod_queue_readiness,
    swapmod_queue_readiness_binding_status,
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


class SwapmodQueueReadinessBindingServiceTest(unittest.IsolatedAsyncioTestCase):
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
        self.session = self.sessionmaker()

    async def asyncTearDown(self) -> None:
        await self.session.close()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def count_rows(self, model) -> int:
        result = await self.session.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())

    async def create_ready_swapmod_cycle(self, cycle_key: str = "swapmod-binding-ready"):
        cycle = await create_swapmod_cycle(
            self.session,
            cycle_key=cycle_key,
            printer_id=101,
            source_print_run_id="print-run-080",
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

    async def record_ready_bed_cycle(self, cycle, *, handoff_key: str = "binding-handoff") -> None:
        await record_swapmod_bed_readiness(
            self.session,
            cycle,
            handoff_key=handoff_key,
            printer_id=101,
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

    async def assert_no_downstream_rows(self) -> None:
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 0)

    def test_status_reports_record_only_safe_defaults(self) -> None:
        payload = swapmod_queue_readiness_binding_status(enabled=False, bed_automation_enabled=False)

        self.assertEqual(payload["mode"], "SWAPMOD_QUEUE_READINESS_BINDING_RECORD_ONLY")
        self.assertFalse(payload["enabled"])
        self.assertTrue(payload["record_only"])
        self.assertFalse(payload["real_command_sent"])
        self.assertFalse(payload["printer_command_sent"])
        self.assertFalse(payload["queue_dispatch_supported"])
        self.assertFalse(payload["scheduler_dispatch_supported"])

    async def test_disabled_binding_raises_without_creating_binding(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-disabled")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-disabled-handoff")
        item = await self.create_queue_item()

        with self.assertRaises(SwapmodQueueReadinessBindingError) as ctx:
            await bind_swapmod_queue_readiness(
                self.session,
                cycle,
                binding_key="binding-disabled-key",
                queue_item_id=item.id,
                printer_id=101,
                enabled=False,
                bed_automation_enabled=True,
            )

        self.assertEqual(ctx.exception.code, "queue_readiness_binding_disabled")
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 0)
        self.assertEqual(await self.count_rows(BedAutomationCycle), 1)
        await self.assert_no_downstream_rows()

    async def test_ready_cycle_bed_and_pending_queue_creates_binding_without_dispatch(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-ready")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-ready-handoff")
        item = await self.create_queue_item(archive_id=404, plate_id=2)

        payload = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-ready-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["binding_status"], QUEUE_READINESS_BINDING_READY)
        self.assertTrue(payload["queue_readiness_bound"])
        self.assertEqual(payload["queue_item_id"], item.id)
        self.assertEqual(payload["source_cycle_key"], "binding-ready")
        self.assertEqual(payload["queue_archive_id"], 404)
        self.assertEqual(payload["queue_plate_id"], 2)
        self.assertEqual(payload["blocked_reasons"], [])
        self.assertEqual(payload["bed_state"], READY_FOR_NEXT_PRINT)
        self.assertFalse(payload["real_command_sent"])
        self.assertFalse(payload["printer_command_sent"])
        self.assertFalse(payload["queue_dispatch_supported"])
        self.assertFalse(payload["scheduler_dispatch_supported"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        await self.assert_no_downstream_rows()

    async def test_repeat_same_binding_is_idempotent(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-idempotent")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-idempotent-handoff")
        item = await self.create_queue_item(library_file_id=909, archive_id=None, plate_id=None)

        first = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-idempotent-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )
        second = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-idempotent-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(first["binding_id"], second["binding_id"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        await self.assert_no_downstream_rows()

    async def test_queue_printer_mismatch_blocks_without_binding(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-printer-mismatch")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-printer-mismatch-handoff")
        item = await self.create_queue_item(printer_id=202)

        payload = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-printer-mismatch-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["binding_status"], QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(payload["queue_readiness_bound"])
        self.assertIn("queue_printer_mismatch", payload["blocked_reasons"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 0)
        await self.assert_no_downstream_rows()

    async def test_missing_bed_record_blocks_without_binding(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-missing-bed")
        item = await self.create_queue_item()

        payload = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-missing-bed-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["binding_status"], QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(payload["queue_readiness_bound"])
        self.assertIn("bed_readiness_record_missing", payload["blocked_reasons"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 0)
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)
        await self.assert_no_downstream_rows()

    async def test_non_pending_queue_status_blocks_without_binding(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-non-pending")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-non-pending-handoff")
        item = await self.create_queue_item(status="printing")

        payload = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-non-pending-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["binding_status"], QUEUE_READINESS_BINDING_BLOCKED)
        self.assertIn("queue_status_not_pending", payload["blocked_reasons"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 0)
        await self.assert_no_downstream_rows()

    async def test_existing_binding_key_cannot_be_reused_for_different_queue_item(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-conflict")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-conflict-handoff")
        first_item = await self.create_queue_item(archive_id=501)
        second_item = await self.create_queue_item(archive_id=502)
        await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-conflict-key",
            queue_item_id=first_item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        with self.assertRaises(SwapmodQueueReadinessBindingError) as ctx:
            await bind_swapmod_queue_readiness(
                self.session,
                cycle,
                binding_key="binding-conflict-key",
                queue_item_id=second_item.id,
                printer_id=101,
                enabled=True,
                bed_automation_enabled=True,
            )

        self.assertEqual(ctx.exception.code, "binding_conflict")
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        await self.assert_no_downstream_rows()

    async def test_existing_binding_key_cannot_be_replayed_for_different_cycle(self) -> None:
        first_cycle = await self.create_ready_swapmod_cycle("binding-replay-first")
        await self.record_ready_bed_cycle(first_cycle, handoff_key="binding-replay-first-handoff")
        item = await self.create_queue_item(archive_id=601)
        await bind_swapmod_queue_readiness(
            self.session,
            first_cycle,
            binding_key="binding-replay-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )
        second_cycle = await self.create_ready_swapmod_cycle("binding-replay-second")
        await self.record_ready_bed_cycle(second_cycle, handoff_key="binding-replay-second-handoff")

        with self.assertRaises(SwapmodQueueReadinessBindingError) as ctx:
            await bind_swapmod_queue_readiness(
                self.session,
                second_cycle,
                binding_key="binding-replay-key",
                queue_item_id=item.id,
                printer_id=101,
                enabled=True,
                bed_automation_enabled=True,
            )

        self.assertEqual(ctx.exception.code, "binding_conflict")
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        await self.assert_no_downstream_rows()

    async def test_existing_binding_key_cannot_be_replayed_for_different_printer(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-replay-printer")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-replay-printer-handoff")
        item = await self.create_queue_item(archive_id=602)
        await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-replay-printer-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        with self.assertRaises(SwapmodQueueReadinessBindingError) as ctx:
            await bind_swapmod_queue_readiness(
                self.session,
                cycle,
                binding_key="binding-replay-printer-key",
                queue_item_id=item.id,
                printer_id=202,
                enabled=True,
                bed_automation_enabled=True,
            )

        self.assertEqual(ctx.exception.code, "binding_conflict")
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        await self.assert_no_downstream_rows()

    async def test_idempotent_replay_rechecks_queue_status_and_returns_blocked_when_stale(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-stale-queue")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-stale-queue-handoff")
        item = await self.create_queue_item(archive_id=701)
        first = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-stale-queue-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )
        self.assertEqual(first["binding_status"], QUEUE_READINESS_BINDING_READY)
        item.status = "printing"
        await self.session.flush()

        replay = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-stale-queue-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(replay["binding_id"], first["binding_id"])
        self.assertEqual(replay["binding_status"], QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(replay["queue_readiness_bound"])
        self.assertTrue(replay["idempotent"])
        self.assertIn("queue_status_not_pending", replay["blocked_reasons"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        await self.assert_no_downstream_rows()

    async def test_idempotent_replay_rechecks_bed_status_and_returns_blocked_when_stale(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-stale-bed")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-stale-bed-handoff")
        item = await self.create_queue_item(archive_id=702)
        first = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-stale-bed-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )
        self.assertEqual(first["binding_status"], QUEUE_READINESS_BINDING_READY)
        bed = (await self.session.execute(select(BedAutomationCycle))).scalar_one()
        bed.ready_for_next_print = False
        bed.state = "MANUAL_REVIEW_REQUIRED"
        bed.manual_review_required = True
        await self.session.flush()

        replay = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-stale-bed-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(replay["binding_id"], first["binding_id"])
        self.assertEqual(replay["binding_status"], QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(replay["queue_readiness_bound"])
        self.assertTrue(replay["idempotent"])
        self.assertIn("bed_manual_review_required", replay["blocked_reasons"])
        self.assertIn("bed_not_ready_for_next_print", replay["blocked_reasons"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        await self.assert_no_downstream_rows()

    async def test_same_bed_readiness_proof_cannot_bind_multiple_queue_items(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-single-proof")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-single-proof-handoff")
        first_item = await self.create_queue_item(archive_id=801)
        second_item = await self.create_queue_item(archive_id=802)
        await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-single-proof-first",
            queue_item_id=first_item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        with self.assertRaises(SwapmodQueueReadinessBindingError) as ctx:
            await bind_swapmod_queue_readiness(
                self.session,
                cycle,
                binding_key="binding-single-proof-second",
                queue_item_id=second_item.id,
                printer_id=101,
                enabled=True,
                bed_automation_enabled=True,
            )

        self.assertEqual(ctx.exception.code, "binding_conflict")
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        await self.assert_no_downstream_rows()

    async def test_idempotent_replay_rechecks_queue_fingerprint_and_returns_blocked_when_changed(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-stale-fingerprint")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-stale-fingerprint-handoff")
        item = await self.create_queue_item(archive_id=901, plate_id=1)
        first = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-stale-fingerprint-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )
        self.assertEqual(first["binding_status"], QUEUE_READINESS_BINDING_READY)
        item.archive_id = 902
        item.plate_id = 2
        await self.session.flush()

        replay = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-stale-fingerprint-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(replay["binding_id"], first["binding_id"])
        self.assertEqual(replay["binding_status"], QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(replay["queue_readiness_bound"])
        self.assertTrue(replay["idempotent"])
        self.assertIn("queue_fingerprint_mismatch", replay["blocked_reasons"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        await self.assert_no_downstream_rows()

    async def test_queue_without_archive_or_library_source_blocks_without_binding(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-source-missing")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-source-missing-handoff")
        item = await self.create_queue_item(archive_id=None, library_file_id=None)

        payload = await bind_swapmod_queue_readiness(
            self.session,
            cycle,
            binding_key="binding-source-missing-key",
            queue_item_id=item.id,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["binding_status"], QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(payload["queue_readiness_bound"])
        self.assertIn("queue_source_missing", payload["blocked_reasons"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 0)
        await self.assert_no_downstream_rows()

    async def test_lost_insert_race_reuses_replay_checks_before_returning_ready(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("binding-race-stale")
        await self.record_ready_bed_cycle(cycle, handoff_key="binding-race-stale-handoff")
        item = await self.create_queue_item(archive_id=1001)
        original_flush = self.session.flush
        original_execute = self.session.execute
        inserted = False

        async def racing_flush(*args, **kwargs):
            nonlocal inserted
            if inserted:
                return await original_flush(*args, **kwargs)
            inserted = True
            async with self.sessionmaker() as other_session:
                other_session.add(
                    SwapmodQueueReadinessBinding(
                        binding_key="binding-race-stale-key",
                        queue_item_id=item.id,
                        printer_id=101,
                        source_cycle_key=cycle.cycle_key,
                        source_print_run_id=cycle.source_print_run_id,
                        bed_cycle_key="swapmod-bed-readiness:binding-race-stale",
                        queue_archive_id=item.archive_id,
                        queue_library_file_id=item.library_file_id,
                        queue_plate_id=item.plate_id,
                        queue_fingerprint=f"queue_item={item.id}:printer=101:archive=1001:library=:plate=1",
                    )
                )
                await other_session.commit()
            item.status = "printing"
            from sqlalchemy.exc import IntegrityError

            raise IntegrityError("insert race", {}, None)

        async def execute_with_stale_mutation(statement, *args, **kwargs):
            result = await original_execute(statement, *args, **kwargs)
            if inserted:
                item.status = "printing"
            return result

        with patch.object(self.session, "flush", racing_flush), patch.object(self.session, "execute", execute_with_stale_mutation):
            payload = await bind_swapmod_queue_readiness(
                self.session,
                cycle,
                binding_key="binding-race-stale-key",
                queue_item_id=item.id,
                printer_id=101,
                enabled=True,
                bed_automation_enabled=True,
            )

        self.assertEqual(payload["binding_status"], QUEUE_READINESS_BINDING_BLOCKED)
        self.assertFalse(payload["queue_readiness_bound"])
        self.assertTrue(payload["idempotent"])
        self.assertIn("queue_status_not_pending", payload["blocked_reasons"])
        self.assertEqual(await self.count_rows(SwapmodQueueReadinessBinding), 1)
        await self.assert_no_downstream_rows()


if __name__ == "__main__":
    unittest.main()
