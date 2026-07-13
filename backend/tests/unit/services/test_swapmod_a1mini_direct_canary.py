from __future__ import annotations

import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.database import Base
from backend.app.services.swapmod_a1mini_direct_canary import (
    DIRECT_CANARY_ADVISORY_LOCK_NAMESPACE,
    SwapmodA1MiniDirectCanaryError,
    SwapmodA1MiniDirectCanaryService,
    _acquire_direct_canary_execution_lock,
    required_a1mini_direct_canary_phrase,
)
from backend.app.services.swapmod_state_machine import (
    LOAD_NEXT_PLATE,
    READY_FOR_NEXT_PRINT,
    RELEASE_PLATE,
    VERIFY_PLATE_RELEASED,
    VERIFY_RELEASED,
    WAITING_FOR_PRINT_FINISH,
    create_swapmod_operator_trigger,
    get_swapmod_cycle,
)


class FakeDirectTransport:
    def __init__(self, *, status: dict[str, object] | None = None, send_result: bool = True) -> None:
        self.status = status or {"state": "FINISH", "gcode_file": ""}
        self.send_result = send_result
        self.sent: list[tuple[int, str]] = []

    def get_status(self, printer_id: int) -> dict[str, object] | None:
        return self.status

    def send_gcode(self, printer_id: int, gcode: str) -> bool:
        self.sent.append((printer_id, gcode))
        return self.send_result


class TransactionInspectingTransport(FakeDirectTransport):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self.session = session
        self.in_transaction_at_send: bool | None = None

    def send_gcode(self, printer_id: int, gcode: str) -> bool:
        self.in_transaction_at_send = self.session.in_transaction()
        return super().send_gcode(printer_id, gcode)


class RaisingDirectTransport(FakeDirectTransport):
    def send_gcode(self, printer_id: int, gcode: str) -> bool:
        self.sent.append((printer_id, gcode))
        raise RuntimeError("synthetic transport failure")


def write_sequence(root: Path, name: str, text: str = "G91\nG4 P10\nG90\n") -> tuple[str, str]:
    path = root / name
    path.write_text(text, encoding="utf-8")
    return name, hashlib.sha256(text.encode("utf-8")).hexdigest()


class SwapmodA1MiniDirectCanaryServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
            group,
            print_log,
            print_queue,
            settings,
            swapmod_state_machine,
            user,
        )

        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.release_file, self.release_sha = write_sequence(self.root, "release.gcode")
        self.load_file, self.load_sha = write_sequence(self.root, "load.gcode", "G91\nG4 P20\nG90\n")
        self.service = SwapmodA1MiniDirectCanaryService()
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
        self.tmp.cleanup()

    def complete_checklist(self) -> dict[str, bool]:
        return {
            "operator_present": True,
            "printer_visible": True,
            "emergency_stop_ready": True,
            "power_cutoff_ready": True,
            "a1_mini_confirmed": True,
            "swapmod_hardware_installed": True,
            "bed_area_clear": True,
            "plate_stack_ready": True,
            "no_other_job_running": True,
            "dry_run_gate_reviewed": True,
        }

    async def create_release_ready_cycle(self, cycle_key: str = "direct-cycle"):
        cycle = await create_swapmod_operator_trigger(
            self.session,
            trigger_key=f"{cycle_key}-trigger",
            cycle_key=cycle_key,
            printer_id=101,
            operator_intent="START_SWAPMOD_PLATE_CHANGE",
        )
        await self.session.commit()
        return cycle

    async def execute_release(
        self,
        db: AsyncSession,
        cycle,
        *,
        canary_key: str,
        transport: FakeDirectTransport,
    ) -> dict[str, object]:
        phrase = required_a1mini_direct_canary_phrase(
            printer_id=101,
            cycle_key=cycle.cycle_key,
            step=RELEASE_PLATE,
            sequence_sha256=self.release_sha,
        )
        return await self.service.execute_transport_step(
            db,
            cycle,
            canary_key=canary_key,
            printer_id=101,
            printer_model="A1 mini",
            step=RELEASE_PLATE,
            operator_approved=True,
            operator_approval_phrase=phrase,
            checklist=self.complete_checklist(),
            enabled=True,
            allow_real_commands=True,
            target_printer_id=101,
            sequence_root=self.root,
            release_sequence_file=self.release_file,
            release_sequence_sha256=self.release_sha,
            load_sequence_file=self.load_file,
            load_sequence_sha256=self.load_sha,
            transport=transport,
        )

    async def test_status_is_default_off_and_reports_no_general_gcode_support(self) -> None:
        status = self.service.status_snapshot(
            enabled=False,
            allow_real_commands=False,
            target_printer_id=None,
            release_sequence_configured=False,
            load_sequence_configured=False,
        )

        self.assertEqual(status["mode"], "A1_MINI_DIRECT_CANARY")
        self.assertFalse(status["enabled"])
        self.assertFalse(status["allow_real_commands"])
        self.assertFalse(status["arbitrary_gcode_supported"])
        self.assertFalse(status["queue_supported"])
        self.assertFalse(status["scheduler_supported"])

    async def test_success_sends_configured_release_sequence_and_advances_to_verify_released(self) -> None:
        cycle = await self.create_release_ready_cycle()
        phrase = required_a1mini_direct_canary_phrase(
            printer_id=101,
            cycle_key="direct-cycle",
            step=RELEASE_PLATE,
            sequence_sha256=self.release_sha,
        )
        transport = FakeDirectTransport()

        result = await self.service.execute_transport_step(
            self.session,
            cycle,
            canary_key="direct-release",
            printer_id=101,
            printer_model="A1 mini",
            step=RELEASE_PLATE,
            operator_approved=True,
            operator_approval_phrase=phrase,
            checklist=self.complete_checklist(),
            enabled=True,
            allow_real_commands=True,
            target_printer_id=101,
            sequence_root=self.root,
            release_sequence_file=self.release_file,
            release_sequence_sha256=self.release_sha,
            load_sequence_file=self.load_file,
            load_sequence_sha256=self.load_sha,
            transport=transport,
        )

        self.assertEqual(result["direct_canary_status"], "COMMAND_SENT")
        self.assertEqual(result["state"], VERIFY_RELEASED)
        self.assertEqual(result["current_step"], VERIFY_PLATE_RELEASED)
        self.assertTrue(result["real_command_sent"])
        self.assertEqual(result["sequence_sha256"], self.release_sha)
        self.assertEqual(transport.sent, [(101, "G91\nG4 P10\nG90\n")])
        self.assertNotIn("G4 P10", str(result))

    async def test_sends_the_exact_bytes_that_passed_sequence_hash_validation(self) -> None:
        cycle = await self.create_release_ready_cycle()
        transport = FakeDirectTransport()
        sequence_path = self.root / self.release_file
        original_read_bytes = Path.read_bytes

        def replace_file_after_read(path: Path) -> bytes:
            content = original_read_bytes(path)
            if path == sequence_path:
                path.write_text("G91\nG4 P999\nG90\n", encoding="utf-8")
            return content

        with patch.object(Path, "read_bytes", new=replace_file_after_read):
            await self.execute_release(
                self.session,
                cycle,
                canary_key="direct-stable-sequence",
                transport=transport,
            )

        self.assertEqual(transport.sent, [(101, "G91\nG4 P10\nG90\n")])

    async def test_sequence_read_and_encoding_failures_send_nothing(self) -> None:
        cycle = await self.create_release_ready_cycle()
        transport = FakeDirectTransport()

        with (
            patch.object(Path, "read_bytes", side_effect=OSError("synthetic read failure")),
            self.assertRaises(SwapmodA1MiniDirectCanaryError) as read_failure,
        ):
            await self.execute_release(
                self.session,
                cycle,
                canary_key="direct-read-failure",
                transport=transport,
            )
        self.assertEqual(read_failure.exception.code, "sequence_read_failed")

        invalid_sequence = b"\xff\xfe"
        (self.root / self.release_file).write_bytes(invalid_sequence)
        self.release_sha = hashlib.sha256(invalid_sequence).hexdigest()
        with self.assertRaises(SwapmodA1MiniDirectCanaryError) as encoding_failure:
            await self.execute_release(
                self.session,
                cycle,
                canary_key="direct-encoding-failure",
                transport=transport,
            )

        self.assertEqual(encoding_failure.exception.code, "sequence_not_utf8")
        self.assertEqual(transport.sent, [])

    async def test_postgres_uses_transaction_advisory_lock_for_named_printer(self) -> None:
        db = MagicMock(spec=AsyncSession)
        db.get_bind.return_value.dialect.name = "postgresql"
        db.execute = AsyncMock()

        await _acquire_direct_canary_execution_lock(db, printer_id=101)

        statement, params = db.execute.await_args.args
        self.assertIn("pg_advisory_xact_lock", str(statement))
        self.assertEqual(
            params,
            {
                "namespace": DIRECT_CANARY_ADVISORY_LOCK_NAMESPACE,
                "printer_id": 101,
            },
        )

    async def test_commits_active_state_before_transport_send(self) -> None:
        cycle = await self.create_release_ready_cycle()
        transport = TransactionInspectingTransport(self.session)

        await self.execute_release(
            self.session,
            cycle,
            canary_key="direct-durable-intent",
            transport=transport,
        )

        self.assertFalse(transport.in_transaction_at_send)

    async def test_transport_exception_persists_manual_review_without_retry(self) -> None:
        cycle = await self.create_release_ready_cycle()
        transport = RaisingDirectTransport()

        result = await self.execute_release(
            self.session,
            cycle,
            canary_key="direct-transport-exception",
            transport=transport,
        )
        await self.session.rollback()
        persisted_cycle = await get_swapmod_cycle(self.session, cycle_key=cycle.cycle_key)

        self.assertEqual(result["direct_canary_status"], "COMMAND_FAILED")
        self.assertIsNotNone(persisted_cycle)
        self.assertTrue(persisted_cycle.manual_review_required)
        self.assertFalse(persisted_cycle.retry_available)

    async def test_concurrent_requests_send_only_one_command(self) -> None:
        db_path = self.root / "concurrent-direct-canary.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
        sessionmaker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with sessionmaker() as seed:
                await create_swapmod_operator_trigger(
                    seed,
                    trigger_key="concurrent-trigger",
                    cycle_key="concurrent-cycle",
                    printer_id=101,
                    operator_intent="START_SWAPMOD_PLATE_CHANGE",
                )
                await seed.commit()

            transport = FakeDirectTransport()
            async with sessionmaker() as first_db, sessionmaker() as second_db:
                first_cycle = await get_swapmod_cycle(first_db, cycle_key="concurrent-cycle")
                second_cycle = await get_swapmod_cycle(second_db, cycle_key="concurrent-cycle")
                self.assertIsNotNone(first_cycle)
                self.assertIsNotNone(second_cycle)

                async def invoke(db: AsyncSession, cycle, canary_key: str):
                    try:
                        result = await self.execute_release(
                            db,
                            cycle,
                            canary_key=canary_key,
                            transport=transport,
                        )
                        await db.commit()
                        return result
                    except Exception as exc:  # noqa: BLE001 - assertions inspect the safety result
                        await db.rollback()
                        return exc

                results = await asyncio.gather(
                    invoke(first_db, first_cycle, "concurrent-first"),
                    invoke(second_db, second_cycle, "concurrent-second"),
                )

            errors = [result for result in results if isinstance(result, SwapmodA1MiniDirectCanaryError)]
            self.assertEqual(len(transport.sent), 1)
            self.assertEqual([error.code for error in errors], ["cycle_state_not_ready_for_step"])
        finally:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            await engine.dispose()

    async def test_blocks_when_feature_or_allow_real_flags_are_disabled(self) -> None:
        cycle = await self.create_release_ready_cycle()
        phrase = required_a1mini_direct_canary_phrase(
            printer_id=101,
            cycle_key="direct-cycle",
            step=RELEASE_PLATE,
            sequence_sha256=self.release_sha,
        )
        transport = FakeDirectTransport()

        with self.assertRaises(SwapmodA1MiniDirectCanaryError) as raised:
            await self.service.execute_transport_step(
                self.session,
                cycle,
                canary_key="direct-disabled",
                printer_id=101,
                printer_model="A1 mini",
                step=RELEASE_PLATE,
                operator_approved=True,
                operator_approval_phrase=phrase,
                checklist=self.complete_checklist(),
                enabled=False,
                allow_real_commands=True,
                target_printer_id=101,
                sequence_root=self.root,
                release_sequence_file=self.release_file,
                release_sequence_sha256=self.release_sha,
                load_sequence_file=self.load_file,
                load_sequence_sha256=self.load_sha,
                transport=transport,
            )

        self.assertEqual(raised.exception.code, "direct_canary_disabled")
        self.assertEqual(transport.sent, [])

    async def test_blocks_on_phrase_or_sequence_hash_mismatch(self) -> None:
        cycle = await self.create_release_ready_cycle()
        transport = FakeDirectTransport()

        with self.assertRaises(SwapmodA1MiniDirectCanaryError) as raised:
            await self.service.execute_transport_step(
                self.session,
                cycle,
                canary_key="direct-bad-phrase",
                printer_id=101,
                printer_model="A1 mini",
                step=RELEASE_PLATE,
                operator_approved=True,
                operator_approval_phrase="wrong",
                checklist=self.complete_checklist(),
                enabled=True,
                allow_real_commands=True,
                target_printer_id=101,
                sequence_root=self.root,
                release_sequence_file=self.release_file,
                release_sequence_sha256=self.release_sha,
                load_sequence_file=self.load_file,
                load_sequence_sha256=self.load_sha,
                transport=transport,
            )

        self.assertEqual(raised.exception.code, "operator_phrase_mismatch")
        self.assertEqual(transport.sent, [])

        with self.assertRaises(SwapmodA1MiniDirectCanaryError) as raised_hash:
            await self.service.execute_transport_step(
                self.session,
                cycle,
                canary_key="direct-bad-hash",
                printer_id=101,
                printer_model="A1 mini",
                step=RELEASE_PLATE,
                operator_approved=True,
                operator_approval_phrase=required_a1mini_direct_canary_phrase(
                    printer_id=101,
                    cycle_key="direct-cycle",
                    step=RELEASE_PLATE,
                    sequence_sha256="0" * 64,
                ),
                checklist=self.complete_checklist(),
                enabled=True,
                allow_real_commands=True,
                target_printer_id=101,
                sequence_root=self.root,
                release_sequence_file=self.release_file,
                release_sequence_sha256="0" * 64,
                load_sequence_file=self.load_file,
                load_sequence_sha256=self.load_sha,
                transport=transport,
            )

        self.assertEqual(raised_hash.exception.code, "sequence_sha256_mismatch")
        self.assertEqual(transport.sent, [])

    async def test_send_failure_blocks_without_retry(self) -> None:
        cycle = await self.create_release_ready_cycle()
        phrase = required_a1mini_direct_canary_phrase(
            printer_id=101,
            cycle_key="direct-cycle",
            step=RELEASE_PLATE,
            sequence_sha256=self.release_sha,
        )
        transport = FakeDirectTransport(send_result=False)

        result = await self.service.execute_transport_step(
            self.session,
            cycle,
            canary_key="direct-send-failure",
            printer_id=101,
            printer_model="A1 mini",
            step=RELEASE_PLATE,
            operator_approved=True,
            operator_approval_phrase=phrase,
            checklist=self.complete_checklist(),
            enabled=True,
            allow_real_commands=True,
            target_printer_id=101,
            sequence_root=self.root,
            release_sequence_file=self.release_file,
            release_sequence_sha256=self.release_sha,
            load_sequence_file=self.load_file,
            load_sequence_sha256=self.load_sha,
            transport=transport,
        )

        cycle = await get_swapmod_cycle(self.session, cycle_key="direct-cycle")
        self.assertIsNotNone(cycle)
        self.assertEqual(result["direct_canary_status"], "COMMAND_FAILED")
        self.assertFalse(result["real_command_sent"])
        self.assertTrue(result["manual_review_required"])
        self.assertFalse(result["retry_available"])
        self.assertTrue(cycle.manual_review_required)
        self.assertFalse(cycle.retry_available)

    async def test_blocks_if_cycle_state_or_printer_state_is_not_safe(self) -> None:
        cycle = await self.create_release_ready_cycle()
        phrase = required_a1mini_direct_canary_phrase(
            printer_id=101,
            cycle_key="direct-cycle",
            step=LOAD_NEXT_PLATE,
            sequence_sha256=self.load_sha,
        )

        with self.assertRaises(SwapmodA1MiniDirectCanaryError) as raised_step:
            await self.service.execute_transport_step(
                self.session,
                cycle,
                canary_key="direct-wrong-state",
                printer_id=101,
                printer_model="A1 mini",
                step=LOAD_NEXT_PLATE,
                operator_approved=True,
                operator_approval_phrase=phrase,
                checklist=self.complete_checklist(),
                enabled=True,
                allow_real_commands=True,
                target_printer_id=101,
                sequence_root=self.root,
                release_sequence_file=self.release_file,
                release_sequence_sha256=self.release_sha,
                load_sequence_file=self.load_file,
                load_sequence_sha256=self.load_sha,
                transport=FakeDirectTransport(),
            )
        self.assertEqual(raised_step.exception.code, "cycle_state_not_ready_for_step")

        with self.assertRaises(SwapmodA1MiniDirectCanaryError) as raised_printer:
            await self.service.execute_transport_step(
                self.session,
                cycle,
                canary_key="direct-active-printer",
                printer_id=101,
                printer_model="A1 mini",
                step=RELEASE_PLATE,
                operator_approved=True,
                operator_approval_phrase=required_a1mini_direct_canary_phrase(
                    printer_id=101,
                    cycle_key="direct-cycle",
                    step=RELEASE_PLATE,
                    sequence_sha256=self.release_sha,
                ),
                checklist=self.complete_checklist(),
                enabled=True,
                allow_real_commands=True,
                target_printer_id=101,
                sequence_root=self.root,
                release_sequence_file=self.release_file,
                release_sequence_sha256=self.release_sha,
                load_sequence_file=self.load_file,
                load_sequence_sha256=self.load_sha,
                transport=FakeDirectTransport(status={"state": "RUNNING", "gcode_file": "active.3mf"}),
            )
        self.assertEqual(raised_printer.exception.code, "printer_not_known_idle")

    async def test_blocks_a_printer_other_than_the_named_canary(self) -> None:
        cycle = await self.create_release_ready_cycle()
        transport = FakeDirectTransport()

        with self.assertRaises(SwapmodA1MiniDirectCanaryError) as raised:
            await self.service.execute_transport_step(
                self.session,
                cycle,
                canary_key="direct-wrong-target",
                printer_id=101,
                printer_model="A1 mini",
                step=RELEASE_PLATE,
                operator_approved=True,
                operator_approval_phrase="not-used",
                checklist=self.complete_checklist(),
                enabled=True,
                allow_real_commands=True,
                target_printer_id=202,
                sequence_root=self.root,
                release_sequence_file=self.release_file,
                release_sequence_sha256=self.release_sha,
                load_sequence_file=self.load_file,
                load_sequence_sha256=self.load_sha,
                transport=transport,
            )

        self.assertEqual(raised.exception.code, "target_printer_mismatch")
        self.assertEqual(transport.sent, [])

    async def test_blocks_when_another_recent_cycle_is_unresolved(self) -> None:
        cycle = await self.create_release_ready_cycle()
        await self.create_release_ready_cycle("other-direct-cycle")
        transport = FakeDirectTransport()

        with self.assertRaises(SwapmodA1MiniDirectCanaryError) as raised:
            await self.service.execute_transport_step(
                self.session,
                cycle,
                canary_key="direct-competing-cycle",
                printer_id=101,
                printer_model="A1 mini",
                step=RELEASE_PLATE,
                operator_approved=True,
                operator_approval_phrase="not-used",
                checklist=self.complete_checklist(),
                enabled=True,
                allow_real_commands=True,
                target_printer_id=101,
                sequence_root=self.root,
                release_sequence_file=self.release_file,
                release_sequence_sha256=self.release_sha,
                load_sequence_file=self.load_file,
                load_sequence_sha256=self.load_sha,
                transport=transport,
            )

        self.assertEqual(raised.exception.code, "another_unresolved_cycle")
        self.assertEqual(transport.sent, [])

    async def test_blocks_a_cycle_older_than_the_latest_completed_cycle(self) -> None:
        stale_cycle = await self.create_release_ready_cycle("stale-direct-cycle")
        completed_cycle = await self.create_release_ready_cycle("completed-direct-cycle")
        completed_cycle.state = READY_FOR_NEXT_PRINT
        await self.session.commit()
        transport = FakeDirectTransport()

        with self.assertRaises(SwapmodA1MiniDirectCanaryError) as raised:
            await self.service.execute_transport_step(
                self.session,
                stale_cycle,
                canary_key="direct-stale-cycle",
                printer_id=101,
                printer_model="A1 mini",
                step=RELEASE_PLATE,
                operator_approved=True,
                operator_approval_phrase="not-used",
                checklist=self.complete_checklist(),
                enabled=True,
                allow_real_commands=True,
                target_printer_id=101,
                sequence_root=self.root,
                release_sequence_file=self.release_file,
                release_sequence_sha256=self.release_sha,
                load_sequence_file=self.load_file,
                load_sequence_sha256=self.load_sha,
                transport=transport,
            )

        self.assertEqual(raised.exception.code, "stale_cycle")
        self.assertEqual(transport.sent, [])


if __name__ == "__main__":
    unittest.main()
