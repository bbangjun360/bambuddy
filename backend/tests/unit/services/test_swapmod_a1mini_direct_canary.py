from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.core.database import Base
from backend.app.services.swapmod_a1mini_direct_canary import (
    SwapmodA1MiniDirectCanaryError,
    SwapmodA1MiniDirectCanaryService,
    required_a1mini_direct_canary_phrase,
)
from backend.app.services.swapmod_state_machine import (
    LOAD_NEXT_PLATE,
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

    async def create_release_ready_cycle(self):
        return await create_swapmod_operator_trigger(
            self.session,
            trigger_key="direct-trigger",
            cycle_key="direct-cycle",
            printer_id=101,
            operator_intent="START_SWAPMOD_PLATE_CHANGE",
        )

    async def test_status_is_default_off_and_reports_no_general_gcode_support(self) -> None:
        status = self.service.status_snapshot(
            enabled=False,
            allow_real_commands=False,
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
                sequence_root=self.root,
                release_sequence_file=self.release_file,
                release_sequence_sha256=self.release_sha,
                load_sequence_file=self.load_file,
                load_sequence_sha256=self.load_sha,
                transport=FakeDirectTransport(status={"state": "RUNNING", "gcode_file": "active.3mf"}),
            )
        self.assertEqual(raised_printer.exception.code, "printer_not_known_idle")


if __name__ == "__main__":
    unittest.main()
