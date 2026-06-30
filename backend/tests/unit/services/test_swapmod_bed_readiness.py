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
from backend.app.services import swapmod_bed_readiness as bed_readiness_service
from backend.app.services.bed_automation import MANUAL_REVIEW_REQUIRED, READY_FOR_NEXT_PRINT
from backend.app.services.swapmod_bed_readiness import (
    HANDOFF_MANUAL_REVIEW_REQUIRED,
    HANDOFF_READY_RECORDED,
    SwapmodBedReadinessError,
    record_swapmod_bed_readiness,
)
from backend.app.services.swapmod_state_machine import (
    LOAD_NEXT_PLATE,
    PRINT_FINISHED,
    READY_TO_LOAD,
    RELEASE_PLATE,
    START_STEP,
    STEP_MOCK_SUCCEEDED,
    VERIFY_FAILED,
    VERIFY_PASSED,
    VERIFY_PLATE_READY,
    VERIFY_PLATE_RELEASED,
    apply_swapmod_event,
    create_swapmod_cycle,
)


class SwapmodBedReadinessServiceTest(unittest.IsolatedAsyncioTestCase):
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
        self.session = self.sessionmaker()

    async def asyncTearDown(self) -> None:
        await self.session.close()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def count_rows(self, model) -> int:
        result = await self.session.execute(select(func.count()).select_from(model))
        return int(result.scalar_one())

    async def create_ready_swapmod_cycle(self, cycle_key: str = "swapmod-bed-ready"):
        cycle = await create_swapmod_cycle(
            self.session,
            cycle_key=cycle_key,
            printer_id=101,
            source_print_run_id="print-run-077",
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

    async def create_manual_review_swapmod_cycle(self, cycle_key: str = "swapmod-bed-review"):
        cycle = await create_swapmod_cycle(self.session, cycle_key=cycle_key, printer_id=101)
        for event, event_id, step, verification_source, verification_result in (
            (PRINT_FINISHED, "event-1", None, None, None),
            (START_STEP, "event-2", RELEASE_PLATE, None, None),
            (STEP_MOCK_SUCCEEDED, "event-3", RELEASE_PLATE, None, None),
            (VERIFY_FAILED, "event-4", VERIFY_PLATE_RELEASED, "manual", "fail"),
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

    async def assert_no_dispatch_or_downstream_rows(self) -> None:
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 0)

    async def test_ready_swapmod_cycle_records_bed_ready_without_dispatch(self) -> None:
        cycle = await self.create_ready_swapmod_cycle()

        payload = await record_swapmod_bed_readiness(
            self.session,
            cycle,
            handoff_key="handoff-ready-001",
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
            bed_automation_dry_run=True,
        )

        self.assertEqual(payload["handoff_status"], HANDOFF_READY_RECORDED)
        self.assertEqual(payload["source_cycle_key"], "swapmod-bed-ready")
        self.assertEqual(payload["bed_cycle_key"], "swapmod-bed-readiness:swapmod-bed-ready")
        self.assertTrue(payload["ready_for_next_print"])
        self.assertFalse(payload["manual_review_required"])
        self.assertFalse(payload["real_command_sent"])
        self.assertFalse(payload["printer_command_sent"])
        self.assertFalse(payload["queue_dispatch_supported"])
        self.assertFalse(payload["scheduler_dispatch_supported"])

        result = await self.session.execute(
            select(BedAutomationCycle).where(BedAutomationCycle.cycle_key == payload["bed_cycle_key"])
        )
        bed_cycle = result.scalar_one()
        self.assertEqual(bed_cycle.state, READY_FOR_NEXT_PRINT)
        self.assertTrue(bed_cycle.ready_for_next_print)
        self.assertFalse(bed_cycle.manual_review_required)
        self.assertTrue(bed_cycle.dry_run)
        self.assertEqual(bed_cycle.source_print_run_id, "print-run-077")
        self.assertEqual(bed_cycle.transition_count, 1)
        self.assertEqual(bed_cycle.transition_log[-1]["event"], "SWAPMOD_READY_FOR_NEXT_PRINT_HANDOFF")
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_handoff_is_idempotent_by_source_cycle(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("swapmod-bed-idempotent")

        first = await record_swapmod_bed_readiness(
            self.session,
            cycle,
            handoff_key="handoff-duplicate",
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
            bed_automation_dry_run=True,
        )
        second = await record_swapmod_bed_readiness(
            self.session,
            cycle,
            handoff_key="handoff-duplicate",
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
            bed_automation_dry_run=True,
        )

        self.assertEqual(first["bed_cycle_id"], second["bed_cycle_id"])
        self.assertEqual(await self.count_rows(BedAutomationCycle), 1)
        result = await self.session.execute(select(BedAutomationCycle))
        self.assertEqual(result.scalar_one().transition_count, 1)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_unique_constraint_race_returns_existing_bed_record(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("swapmod-bed-race")
        bed_cycle_key = bed_readiness_service.swapmod_bed_cycle_key(source_cycle_key=cycle.cycle_key)
        existing = BedAutomationCycle(
            cycle_key=bed_cycle_key,
            printer_id=101,
            source_print_run_id="print-run-077",
            state=READY_FOR_NEXT_PRINT,
            dry_run=True,
            ready_for_next_print=True,
            manual_review_required=False,
            blocked_reason=None,
            seen_event_ids=["swapmod-bed-readiness:already-created"],
            transition_log=[
                {
                    "event": "SWAPMOD_READY_FOR_NEXT_PRINT_HANDOFF",
                    "event_id": "swapmod-bed-readiness:already-created",
                    "from_state": None,
                    "to_state": READY_FOR_NEXT_PRINT,
                    "source_cycle_key": cycle.cycle_key,
                    "source_state": cycle.state,
                    "reason": None,
                }
            ],
            transition_count=1,
        )
        self.session.add(existing)
        await self.session.flush()
        await self.session.refresh(existing)
        real_get_bed_cycle = bed_readiness_service._get_bed_cycle
        calls = 0

        async def miss_then_find(db, *, bed_cycle_key: str):
            nonlocal calls
            calls += 1
            if calls == 1:
                return None
            return await real_get_bed_cycle(db, bed_cycle_key=bed_cycle_key)

        with patch.object(bed_readiness_service, "_get_bed_cycle", new=miss_then_find):
            payload = await record_swapmod_bed_readiness(
                self.session,
                cycle,
                handoff_key="handoff-race",
                printer_id=101,
                enabled=True,
                bed_automation_enabled=True,
                bed_automation_dry_run=True,
            )

        self.assertEqual(payload["bed_cycle_id"], existing.id)
        self.assertEqual(payload["bed_cycle_key"], bed_cycle_key)
        self.assertTrue(payload["ready_for_next_print"])
        self.assertEqual(await self.count_rows(BedAutomationCycle), 1)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_non_ready_swapmod_cycle_blocks_without_bed_record(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-bed-not-ready", printer_id=101)
        cycle = await apply_swapmod_event(self.session, cycle, PRINT_FINISHED, event_id="not-ready:event-1")
        cycle = await apply_swapmod_event(
            self.session,
            cycle,
            START_STEP,
            event_id="not-ready:event-2",
            step=RELEASE_PLATE,
        )
        cycle = await apply_swapmod_event(
            self.session,
            cycle,
            STEP_MOCK_SUCCEEDED,
            event_id="not-ready:event-3",
            step=RELEASE_PLATE,
        )
        cycle = await apply_swapmod_event(
            self.session,
            cycle,
            VERIFY_PASSED,
            event_id="not-ready:event-4",
            step=VERIFY_PLATE_RELEASED,
            verification_source="manual",
            verification_result="pass",
        )
        self.assertEqual(cycle.state, READY_TO_LOAD)

        with self.assertRaises(SwapmodBedReadinessError) as captured:
            await record_swapmod_bed_readiness(
                self.session,
                cycle,
                handoff_key="handoff-not-ready",
                printer_id=101,
                enabled=True,
                bed_automation_enabled=True,
                bed_automation_dry_run=True,
            )

        self.assertEqual(captured.exception.code, "swapmod_cycle_not_ready")
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_manual_review_source_records_bed_manual_review_not_ready(self) -> None:
        cycle = await self.create_manual_review_swapmod_cycle()

        payload = await record_swapmod_bed_readiness(
            self.session,
            cycle,
            handoff_key="handoff-review",
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
            bed_automation_dry_run=True,
        )

        self.assertEqual(payload["handoff_status"], HANDOFF_MANUAL_REVIEW_REQUIRED)
        self.assertFalse(payload["ready_for_next_print"])
        self.assertTrue(payload["manual_review_required"])
        self.assertIn("manual review", payload["blocked_reason"])
        result = await self.session.execute(select(BedAutomationCycle))
        bed_cycle = result.scalar_one()
        self.assertEqual(bed_cycle.state, MANUAL_REVIEW_REQUIRED)
        self.assertFalse(bed_cycle.ready_for_next_print)
        self.assertTrue(bed_cycle.manual_review_required)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_printer_mismatch_blocks_without_record(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("swapmod-bed-wrong-printer")

        with self.assertRaises(SwapmodBedReadinessError) as captured:
            await record_swapmod_bed_readiness(
                self.session,
                cycle,
                handoff_key="handoff-printer-mismatch",
                printer_id=202,
                enabled=True,
                bed_automation_enabled=True,
                bed_automation_dry_run=True,
            )

        self.assertEqual(captured.exception.code, "printer_mismatch")
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)

    async def test_missing_source_printer_blocks_without_record(self) -> None:
        cycle = await create_swapmod_cycle(self.session, cycle_key="swapmod-bed-missing-printer")
        for event, event_id, step, verification_source, verification_result in (
            (PRINT_FINISHED, "event-1", None, None, None),
            (START_STEP, "event-2", RELEASE_PLATE, None, None),
            (STEP_MOCK_SUCCEEDED, "event-3", RELEASE_PLATE, None, None),
            (VERIFY_PASSED, "event-4", VERIFY_PLATE_RELEASED, "manual", "pass"),
            (START_STEP, "event-5", LOAD_NEXT_PLATE, None, None),
            (STEP_MOCK_SUCCEEDED, "event-6", LOAD_NEXT_PLATE, None, None),
            (VERIFY_PASSED, "event-7", VERIFY_PLATE_READY, "manual", "pass"),
        ):
            cycle = await apply_swapmod_event(
                self.session,
                cycle,
                event,
                event_id=f"missing-printer:{event_id}",
                step=step,
                verification_source=verification_source,
                verification_result=verification_result,
            )

        with self.assertRaises(SwapmodBedReadinessError) as captured:
            await record_swapmod_bed_readiness(
                self.session,
                cycle,
                handoff_key="handoff-missing-printer",
                printer_id=101,
                enabled=True,
                bed_automation_enabled=True,
                bed_automation_dry_run=True,
            )

        self.assertEqual(captured.exception.code, "printer_missing")
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)


if __name__ == "__main__":
    unittest.main()
