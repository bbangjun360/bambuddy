from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import swapmod_a1mini_direct_canary as direct_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.printer import Printer
from backend.app.services.swapmod_a1mini_direct_canary import required_a1mini_direct_canary_phrase
from backend.app.services.swapmod_state_machine import RELEASE_PLATE, VERIFY_RELEASED
from backend.tests.integration.test_plate_change_3mf_postprocess_api import ASGITransport, AsyncClient


class FakeDirectTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    def get_status(self, printer_id: int) -> dict[str, object] | None:
        return {"state": "FINISH", "gcode_file": ""}

    def send_gcode(self, printer_id: int, gcode: str) -> bool:
        self.sent.append((printer_id, gcode))
        return True


class SwapmodA1MiniDirectCanaryApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
            group,
            printer,
            print_log,
            print_queue,
            settings,
            swapmod_state_machine,
            user,
        )

        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.release_text = "G91\nG4 P10\nG90\n"
        (self.root / "release.gcode").write_text(self.release_text, encoding="utf-8")
        (self.root / "load.gcode").write_text("G91\nG4 P20\nG90\n", encoding="utf-8")
        self.release_sha = hashlib.sha256(self.release_text.encode("utf-8")).hexdigest()
        self.load_sha = hashlib.sha256("G91\nG4 P20\nG90\n".encode("utf-8")).hexdigest()

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async with self.sessionmaker() as session:
            session.add(
                Printer(
                    id=101,
                    name="A1 Mini canary",
                    serial_number="redacted-test-serial",
                    ip_address="redacted.local",
                    access_code="redacted",
                    model="A1 mini",
                    location="test",
                )
            )
            await session.commit()

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
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        self.previous_values = {
            "farm_swapmod_state_machine_enabled": direct_route.settings.farm_swapmod_state_machine_enabled,
            "farm_swapmod_a1mini_direct_canary_enabled": direct_route.settings.farm_swapmod_a1mini_direct_canary_enabled,
            "farm_swapmod_a1mini_direct_canary_allow_real_commands": direct_route.settings.farm_swapmod_a1mini_direct_canary_allow_real_commands,
            "farm_swapmod_a1mini_direct_canary_sequence_root": direct_route.settings.farm_swapmod_a1mini_direct_canary_sequence_root,
            "farm_swapmod_a1mini_direct_canary_release_sequence_file": direct_route.settings.farm_swapmod_a1mini_direct_canary_release_sequence_file,
            "farm_swapmod_a1mini_direct_canary_release_sequence_sha256": direct_route.settings.farm_swapmod_a1mini_direct_canary_release_sequence_sha256,
            "farm_swapmod_a1mini_direct_canary_load_sequence_file": direct_route.settings.farm_swapmod_a1mini_direct_canary_load_sequence_file,
            "farm_swapmod_a1mini_direct_canary_load_sequence_sha256": direct_route.settings.farm_swapmod_a1mini_direct_canary_load_sequence_sha256,
        }
        direct_route.settings.farm_swapmod_state_machine_enabled = True
        direct_route.settings.farm_swapmod_a1mini_direct_canary_enabled = False
        direct_route.settings.farm_swapmod_a1mini_direct_canary_allow_real_commands = False
        direct_route.settings.farm_swapmod_a1mini_direct_canary_sequence_root = str(self.root)
        direct_route.settings.farm_swapmod_a1mini_direct_canary_release_sequence_file = "release.gcode"
        direct_route.settings.farm_swapmod_a1mini_direct_canary_release_sequence_sha256 = self.release_sha
        direct_route.settings.farm_swapmod_a1mini_direct_canary_load_sequence_file = "load.gcode"
        direct_route.settings.farm_swapmod_a1mini_direct_canary_load_sequence_sha256 = self.load_sha

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        for name, value in self.previous_values.items():
            setattr(direct_route.settings, name, value)
        for patcher in reversed(self.patches):
            patcher.stop()
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

    async def create_release_ready_cycle(self, cycle_key: str = "api-direct-cycle") -> None:
        response = await self.client.post(
            "/api/v1/swapmod-state-machine/operator-triggers",
            json={
                "trigger_key": f"{cycle_key}-trigger",
                "cycle_key": cycle_key,
                "printer_id": 101,
                "operator_intent": "START_SWAPMOD_PLATE_CHANGE",
            },
        )
        self.assertEqual(response.status_code, 202, response.text)

    async def test_status_reports_disabled_by_default(self) -> None:
        response = await self.client.get("/api/v1/swapmod-a1-mini-direct-canary/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["enabled"])
        self.assertFalse(body["allow_real_commands"])
        self.assertFalse(body["arbitrary_gcode_supported"])

    async def test_transport_step_is_disabled_by_default(self) -> None:
        await self.create_release_ready_cycle("api-direct-disabled")

        response = await self.client.post(
            "/api/v1/swapmod-a1-mini-direct-canary/cycles/api-direct-disabled/transport-steps",
            json={
                "canary_key": "api-direct-disabled",
                "printer_id": 101,
                "step": RELEASE_PLATE,
                "operator_approved": True,
                "operator_approval_phrase": "wrong",
                "checklist": self.complete_checklist(),
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())

    async def test_schema_rejects_raw_gcode_field(self) -> None:
        await self.create_release_ready_cycle("api-direct-schema")
        direct_route.settings.farm_swapmod_a1mini_direct_canary_enabled = True
        direct_route.settings.farm_swapmod_a1mini_direct_canary_allow_real_commands = True

        response = await self.client.post(
            "/api/v1/swapmod-a1-mini-direct-canary/cycles/api-direct-schema/transport-steps",
            json={
                "canary_key": "api-direct-schema",
                "printer_id": 101,
                "step": RELEASE_PLATE,
                "operator_approved": True,
                "operator_approval_phrase": "wrong",
                "raw_gcode": "G28",
                "checklist": self.complete_checklist(),
            },
        )

        self.assertEqual(response.status_code, 422)

    async def test_mocked_transport_sends_configured_sequence_only(self) -> None:
        await self.create_release_ready_cycle("api-direct-success")
        direct_route.settings.farm_swapmod_a1mini_direct_canary_enabled = True
        direct_route.settings.farm_swapmod_a1mini_direct_canary_allow_real_commands = True
        phrase = required_a1mini_direct_canary_phrase(
            printer_id=101,
            cycle_key="api-direct-success",
            step=RELEASE_PLATE,
            sequence_sha256=self.release_sha,
        )
        transport = FakeDirectTransport()

        with patch.object(direct_route, "get_a1mini_direct_transport", return_value=transport):
            response = await self.client.post(
                "/api/v1/swapmod-a1-mini-direct-canary/cycles/api-direct-success/transport-steps",
                json={
                    "canary_key": "api-direct-success",
                    "printer_id": 101,
                    "step": RELEASE_PLATE,
                    "operator_approved": True,
                    "operator_approval_phrase": phrase,
                    "checklist": self.complete_checklist(),
                },
            )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["direct_canary_status"], "COMMAND_SENT")
        self.assertEqual(body["state"], VERIFY_RELEASED)
        self.assertTrue(body["real_command_sent"])
        self.assertEqual(transport.sent, [(101, self.release_text)])
        self.assertNotIn("G4 P10", str(body))


if __name__ == "__main__":
    unittest.main()
