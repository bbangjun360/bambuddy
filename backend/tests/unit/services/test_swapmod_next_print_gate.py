from __future__ import annotations

import unittest

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.database import Base
from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.erp_draft_write import ErpDraftWriteRecord
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.services.bed_automation import MANUAL_REVIEW_REQUIRED, READY_FOR_NEXT_PRINT
from backend.app.services.swapmod_bed_readiness import record_swapmod_bed_readiness, swapmod_bed_cycle_key
from backend.app.services.swapmod_next_print_gate import (
    NEXT_PRINT_GATE_BLOCKED,
    NEXT_PRINT_GATE_READY,
    SwapmodNextPrintGateError,
    evaluate_swapmod_next_print_gate,
)
from backend.app.services.swapmod_state_machine import (
    LOAD_NEXT_PLATE,
    PRINT_FINISHED,
    READY_TO_LOAD,
    RELEASE_PLATE,
    START_STEP,
    STEP_MOCK_SUCCEEDED,
    VERIFY_PASSED,
    VERIFY_PLATE_READY,
    VERIFY_PLATE_RELEASED,
    apply_swapmod_event,
    create_swapmod_cycle,
)


class SwapmodNextPrintGateServiceTest(unittest.IsolatedAsyncioTestCase):
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

    async def create_ready_swapmod_cycle(self, cycle_key: str = "swapmod-next-ready"):
        cycle = await create_swapmod_cycle(
            self.session,
            cycle_key=cycle_key,
            printer_id=101,
            source_print_run_id="print-run-078",
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

    async def create_partially_ready_swapmod_cycle(self, cycle_key: str = "swapmod-next-not-ready"):
        cycle = await create_swapmod_cycle(self.session, cycle_key=cycle_key, printer_id=101)
        for event, event_id, step, verification_source, verification_result in (
            (PRINT_FINISHED, "event-1", None, None, None),
            (START_STEP, "event-2", RELEASE_PLATE, None, None),
            (STEP_MOCK_SUCCEEDED, "event-3", RELEASE_PLATE, None, None),
            (VERIFY_PASSED, "event-4", VERIFY_PLATE_RELEASED, "manual", "pass"),
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
        self.assertEqual(cycle.state, READY_TO_LOAD)
        return cycle

    async def record_ready_bed_cycle(self, cycle, *, handoff_key: str = "handoff-ready") -> None:
        await record_swapmod_bed_readiness(
            self.session,
            cycle,
            handoff_key=handoff_key,
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
            bed_automation_dry_run=True,
        )

    async def record_manual_review_bed_cycle(self, cycle) -> None:
        self.session.add(
            BedAutomationCycle(
                cycle_key=swapmod_bed_cycle_key(source_cycle_key=cycle.cycle_key),
                printer_id=101,
                source_print_run_id=cycle.source_print_run_id,
                state=MANUAL_REVIEW_REQUIRED,
                dry_run=True,
                ready_for_next_print=False,
                manual_review_required=True,
                blocked_reason="operator review required",
                seen_event_ids=["manual-review"],
                transition_log=[],
                transition_count=1,
            )
        )
        await self.session.flush()

    async def assert_no_dispatch_or_downstream_rows(self) -> None:
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 0)

    async def test_ready_swapmod_and_bed_record_marks_gate_ready_without_dispatch(self) -> None:
        cycle = await self.create_ready_swapmod_cycle()
        await self.record_ready_bed_cycle(cycle)

        payload = await evaluate_swapmod_next_print_gate(
            self.session,
            cycle,
            gate_key="gate-ready-001",
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], NEXT_PRINT_GATE_READY)
        self.assertTrue(payload["next_print_allowed"])
        self.assertEqual(payload["blocked_reasons"], [])
        self.assertEqual(payload["bed_state"], READY_FOR_NEXT_PRINT)
        self.assertTrue(payload["bed_ready_for_next_print"])
        self.assertFalse(payload["real_command_sent"])
        self.assertFalse(payload["printer_command_sent"])
        self.assertFalse(payload["queue_dispatch_supported"])
        self.assertFalse(payload["scheduler_dispatch_supported"])
        self.assertEqual(await self.count_rows(BedAutomationCycle), 1)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_printer_mismatch_blocks_next_print_without_dispatch(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("swapmod-next-printer-mismatch")
        await self.record_ready_bed_cycle(cycle, handoff_key="handoff-printer-mismatch")

        payload = await evaluate_swapmod_next_print_gate(
            self.session,
            cycle,
            gate_key="gate-printer-mismatch",
            printer_id=202,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], NEXT_PRINT_GATE_BLOCKED)
        self.assertFalse(payload["next_print_allowed"])
        self.assertIn("printer_mismatch", payload["blocked_reasons"])
        self.assertIn("bed_printer_mismatch", payload["blocked_reasons"])
        self.assertEqual(await self.count_rows(BedAutomationCycle), 1)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_missing_bed_record_blocks_without_creating_record(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("swapmod-next-missing-bed")

        payload = await evaluate_swapmod_next_print_gate(
            self.session,
            cycle,
            gate_key="gate-missing-bed",
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], NEXT_PRINT_GATE_BLOCKED)
        self.assertFalse(payload["next_print_allowed"])
        self.assertIn("bed_readiness_record_missing", payload["blocked_reasons"])
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_manual_review_bed_record_blocks_next_print(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("swapmod-next-bed-review")
        await self.record_manual_review_bed_cycle(cycle)

        payload = await evaluate_swapmod_next_print_gate(
            self.session,
            cycle,
            gate_key="gate-review",
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], NEXT_PRINT_GATE_BLOCKED)
        self.assertFalse(payload["next_print_allowed"])
        self.assertIn("bed_manual_review_required", payload["blocked_reasons"])
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_bed_record_without_printer_blocks_next_print(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("swapmod-next-bed-printer-missing")
        self.session.add(
            BedAutomationCycle(
                cycle_key=swapmod_bed_cycle_key(source_cycle_key=cycle.cycle_key),
                printer_id=None,
                source_print_run_id=cycle.source_print_run_id,
                state=READY_FOR_NEXT_PRINT,
                dry_run=True,
                ready_for_next_print=True,
                manual_review_required=False,
                blocked_reason=None,
                seen_event_ids=["bed-ready"],
                transition_log=[],
                transition_count=1,
            )
        )
        await self.session.flush()

        payload = await evaluate_swapmod_next_print_gate(
            self.session,
            cycle,
            gate_key="gate-bed-printer-missing",
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], NEXT_PRINT_GATE_BLOCKED)
        self.assertIn("bed_printer_missing", payload["blocked_reasons"])
        self.assertFalse(payload["next_print_allowed"])
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_not_ready_swapmod_cycle_blocks_even_if_bed_ready_record_exists(self) -> None:
        cycle = await self.create_partially_ready_swapmod_cycle()
        self.session.add(
            BedAutomationCycle(
                cycle_key=swapmod_bed_cycle_key(source_cycle_key=cycle.cycle_key),
                printer_id=101,
                source_print_run_id=cycle.source_print_run_id,
                state=READY_FOR_NEXT_PRINT,
                dry_run=True,
                ready_for_next_print=True,
                manual_review_required=False,
                blocked_reason=None,
                seen_event_ids=["bed-ready"],
                transition_log=[],
                transition_count=1,
            )
        )
        await self.session.flush()

        payload = await evaluate_swapmod_next_print_gate(
            self.session,
            cycle,
            gate_key="gate-swapmod-not-ready",
            printer_id=101,
            enabled=True,
            bed_automation_enabled=True,
        )

        self.assertEqual(payload["gate_status"], NEXT_PRINT_GATE_BLOCKED)
        self.assertIn("swapmod_cycle_not_ready", payload["blocked_reasons"])
        self.assertFalse(payload["next_print_allowed"])
        await self.assert_no_dispatch_or_downstream_rows()

    async def test_disabled_gate_raises_without_readiness_mutation(self) -> None:
        cycle = await self.create_ready_swapmod_cycle("swapmod-next-disabled")

        with self.assertRaises(SwapmodNextPrintGateError) as captured:
            await evaluate_swapmod_next_print_gate(
                self.session,
                cycle,
                gate_key="gate-disabled",
                printer_id=101,
                enabled=False,
                bed_automation_enabled=True,
            )

        self.assertEqual(captured.exception.code, "next_print_gate_disabled")
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)
        await self.assert_no_dispatch_or_downstream_rows()


if __name__ == "__main__":
    unittest.main()
