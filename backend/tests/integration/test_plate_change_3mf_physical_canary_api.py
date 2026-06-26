from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import plate_change_3mf_postprocess as canary_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.printer import Printer
from backend.tests.integration.test_plate_change_3mf_postprocess_api import ASGITransport, AsyncClient


CHECKLIST = {
    "operator_present": True,
    "printer_visible": True,
    "emergency_stop_ready": True,
    "power_cutoff_ready": True,
    "bed_clear_confirmed": True,
    "correct_plate_confirmed": True,
    "no_other_job_running": True,
    "fire_risk_area_clear": True,
}


class FakeCanaryPrinterOps:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, Path]] = []
        self.starts: list[tuple[str, str]] = []
        self.connected = True
        self.state = type("State", (), {"state": "IDLE", "gcode_file": None})()

    def is_connected(self, printer_id: str) -> bool:
        return self.connected

    def get_state(self, printer_id: str):
        return self.state

    async def upload_artifact(self, printer_id: str, artifact_path: Path) -> str:
        self.uploads.append((printer_id, artifact_path))
        return f"/cache/{artifact_path.name}"

    async def start_print(self, printer_id: str, remote_path: str) -> bool:
        self.starts.append((printer_id, remote_path))
        return True


def _write_reviewed_3mf(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("3D/3dmodel.model", b"<model/>")
        zf.writestr("Metadata/bambuddy_real_sample_output_review.json", b'{"reviewed": true}')
        zf.writestr("Metadata/plate_1.gcode", b"; mocked API canary fixture\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PlateChange3mfPhysicalCanaryApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
            group,
            printer,
            settings,
            user,
        )

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_get_db():
            async with self.sessionmaker() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.patches = [
            patch("backend.app.core.database.async_session", self.sessionmaker),
            patch("backend.app.core.auth.async_session", self.sessionmaker),
            patch("backend.app.main.async_session", self.sessionmaker),
        ]
        for patcher in self.patches:
            patcher.start()

        self.previous_settings = {
            "farm_plate_change_3mf_physical_canary_enabled": (
                canary_route.settings.farm_plate_change_3mf_physical_canary_enabled
            ),
            "farm_plate_change_3mf_allow_printer_upload": (
                canary_route.settings.farm_plate_change_3mf_allow_printer_upload
            ),
            "farm_plate_change_3mf_allow_print_start": (
                canary_route.settings.farm_plate_change_3mf_allow_print_start
            ),
            "farm_plate_change_3mf_canary_single_printer_only": (
                canary_route.settings.farm_plate_change_3mf_canary_single_printer_only
            ),
            "farm_plate_change_3mf_canary_require_human_confirmation": (
                canary_route.settings.farm_plate_change_3mf_canary_require_human_confirmation
            ),
            "farm_plate_change_3mf_canary_disable_auto_retry": (
                canary_route.settings.farm_plate_change_3mf_canary_disable_auto_retry
            ),
            "farm_plate_change_3mf_canary_max_starts": (
                canary_route.settings.farm_plate_change_3mf_canary_max_starts
            ),
            "farm_plate_change_3mf_output_root": canary_route.settings.farm_plate_change_3mf_output_root,
        }
        canary_route.settings.farm_plate_change_3mf_physical_canary_enabled = False
        canary_route.settings.farm_plate_change_3mf_allow_printer_upload = False
        canary_route.settings.farm_plate_change_3mf_allow_print_start = False
        canary_route.settings.farm_plate_change_3mf_canary_single_printer_only = True
        canary_route.settings.farm_plate_change_3mf_canary_require_human_confirmation = True
        canary_route.settings.farm_plate_change_3mf_canary_disable_auto_retry = True
        canary_route.settings.farm_plate_change_3mf_canary_max_starts = 1

        self.tmp = Path(tempfile.mkdtemp(prefix="wp064-api-physical-canary-"))
        self.output_root = self.tmp / "outputs"
        self.artifact = self.output_root / "reviewed-api-output.gcode.3mf"
        self.artifact_sha256 = _write_reviewed_3mf(self.artifact)
        canary_route.settings.farm_plate_change_3mf_output_root = str(self.output_root)

        self.fake_ops = FakeCanaryPrinterOps()
        self.ops_patch = patch.object(canary_route, "plate_change_3mf_physical_canary_ops", self.fake_ops)
        self.ops_patch.start()
        canary_route.plate_change_3mf_physical_canary_service.reset_for_tests()

        async with self.sessionmaker() as session:
            session.add(
                Printer(
                    id=101,
                    name="Mock Canary Printer",
                    serial_number="TEST-SERIAL-NOT-REAL",
                    ip_address="canary-printer.invalid",
                    access_code="TEST-NOT-A-SECRET",
                    model="A1 Mini",
                    location="test",
                )
            )
            await session.commit()

        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        self.ops_patch.stop()
        app.dependency_overrides.clear()
        for name, value in self.previous_settings.items():
            setattr(canary_route.settings, name, value)
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def enable_canary(self, *, upload: bool = True, start: bool = True) -> None:
        canary_route.settings.farm_plate_change_3mf_physical_canary_enabled = True
        canary_route.settings.farm_plate_change_3mf_allow_printer_upload = upload
        canary_route.settings.farm_plate_change_3mf_allow_print_start = start

    def upload_body(self, **overrides: object) -> dict[str, object]:
        printer_id = str(overrides.get("printer_id", 101))
        sha = str(overrides.get("artifact_sha256", self.artifact_sha256))
        body: dict[str, object] = {
            "target_printer_ids": [printer_id],
            "artifact_path": str(self.artifact),
            "artifact_sha256": sha,
            "operator_confirmation_phrase": f"CONFIRM_UPLOAD_REVIEWED_3MF {printer_id} {sha}",
        }
        body.update(overrides)
        body.pop("printer_id", None)
        return body

    def start_body(self, **overrides: object) -> dict[str, object]:
        printer_id = str(overrides.get("printer_id", 101))
        sha = str(overrides.get("artifact_sha256", self.artifact_sha256))
        body: dict[str, object] = {
            "target_printer_ids": [printer_id],
            "artifact_path": str(self.artifact),
            "artifact_sha256": sha,
            "operator_confirmation_phrase": f"CONFIRM_START_REVIEWED_3MF {printer_id} {sha}",
            "checklist": dict(CHECKLIST),
        }
        body.update(overrides)
        body.pop("printer_id", None)
        return body

    async def test_canary_status_reports_safe_defaults_without_secrets(self) -> None:
        response = await self.client.get("/api/v1/plate-change-3mf/canary-status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["physical_canary_enabled"])
        self.assertFalse(body["printer_upload_supported"])
        self.assertFalse(body["printer_start_supported"])
        self.assertFalse(body["queue_supported"])
        self.assertFalse(body["scheduler_supported"])
        self.assertFalse(body["auto_retry_supported"])
        self.assertEqual(body["start_attempts_used"], 0)
        rendered = json.dumps(body, sort_keys=True)
        self.assertNotIn("TEST-NOT-A-SECRET", rendered)
        self.assertNotIn("canary-printer.invalid", rendered)
        self.assertNotIn("TEST-SERIAL-NOT-REAL", rendered)

    async def test_upload_and_start_are_default_blocked_then_require_separate_exact_confirmations(self) -> None:
        blocked_upload = await self.client.post("/api/v1/plate-change-3mf/canary-upload", json=self.upload_body())
        self.assertEqual(blocked_upload.status_code, 404)
        self.assertEqual(self.fake_ops.uploads, [])

        blocked_start = await self.client.post("/api/v1/plate-change-3mf/canary-start", json=self.start_body())
        self.assertEqual(blocked_start.status_code, 404)
        self.assertEqual(self.fake_ops.starts, [])

        self.enable_canary()
        wrong_start_phrase = await self.client.post(
            "/api/v1/plate-change-3mf/canary-start",
            json=self.start_body(
                operator_confirmation_phrase=f"CONFIRM_UPLOAD_REVIEWED_3MF 101 {self.artifact_sha256}"
            ),
        )
        self.assertEqual(wrong_start_phrase.status_code, 400)
        self.assertEqual(wrong_start_phrase.json()["detail"]["code"], "prior_upload_required")

        upload = await self.client.post("/api/v1/plate-change-3mf/canary-upload", json=self.upload_body())
        self.assertEqual(upload.status_code, 202, upload.text)
        self.assertEqual(upload.json()["status"], "CANARY_UPLOAD_RECORDED")
        self.assertEqual(len(self.fake_ops.uploads), 1)

        start_with_upload_phrase = await self.client.post(
            "/api/v1/plate-change-3mf/canary-start",
            json=self.start_body(
                operator_confirmation_phrase=f"CONFIRM_UPLOAD_REVIEWED_3MF 101 {self.artifact_sha256}"
            ),
        )
        self.assertEqual(start_with_upload_phrase.status_code, 400)
        self.assertEqual(start_with_upload_phrase.json()["detail"]["code"], "confirmation_phrase_mismatch")
        self.assertEqual(self.fake_ops.starts, [])

        start = await self.client.post("/api/v1/plate-change-3mf/canary-start", json=self.start_body())
        self.assertEqual(start.status_code, 202, start.text)
        self.assertEqual(start.json()["status"], "CANARY_START_ATTEMPTED")
        self.assertEqual(len(self.fake_ops.starts), 1)

        second = await self.client.post("/api/v1/plate-change-3mf/canary-start", json=self.start_body())
        self.assertEqual(second.status_code, 400)
        self.assertEqual(second.json()["detail"]["code"], "max_start_attempts_reached")
        self.assertEqual(len(self.fake_ops.starts), 1)

    async def test_sha_outside_root_multi_printer_missing_checklist_and_uncertain_state_block(self) -> None:
        self.enable_canary()

        sha = await self.client.post(
            "/api/v1/plate-change-3mf/canary-upload",
            json=self.upload_body(artifact_sha256="0" * 64),
        )
        self.assertEqual(sha.status_code, 400)
        self.assertEqual(sha.json()["detail"]["code"], "artifact_sha256_mismatch")

        multi = await self.client.post(
            "/api/v1/plate-change-3mf/canary-upload",
            json=self.upload_body(
                target_printer_ids=["101", "102"],
                operator_confirmation_phrase=f"CONFIRM_UPLOAD_REVIEWED_3MF 101 {self.artifact_sha256}",
            ),
        )
        self.assertEqual(multi.status_code, 400)
        self.assertEqual(multi.json()["detail"]["code"], "single_printer_required")

        outside = self.tmp / "outside" / "outside.gcode.3mf"
        outside_sha = _write_reviewed_3mf(outside)
        outside_response = await self.client.post(
            "/api/v1/plate-change-3mf/canary-upload",
            json=self.upload_body(
                artifact_path=str(outside),
                artifact_sha256=outside_sha,
                operator_confirmation_phrase=f"CONFIRM_UPLOAD_REVIEWED_3MF 101 {outside_sha}",
            ),
        )
        self.assertEqual(outside_response.status_code, 400)
        self.assertEqual(outside_response.json()["detail"]["code"], "artifact_path_not_allowed")

        upload = await self.client.post("/api/v1/plate-change-3mf/canary-upload", json=self.upload_body())
        self.assertEqual(upload.status_code, 202, upload.text)

        checklist = dict(CHECKLIST)
        checklist["fire_risk_area_clear"] = False
        missing_checklist = await self.client.post(
            "/api/v1/plate-change-3mf/canary-start",
            json=self.start_body(checklist=checklist),
        )
        self.assertEqual(missing_checklist.status_code, 400)
        self.assertEqual(missing_checklist.json()["detail"]["code"], "canary_checklist_incomplete")

        self.fake_ops.state = None
        uncertain = await self.client.post("/api/v1/plate-change-3mf/canary-start", json=self.start_body())
        self.assertEqual(uncertain.status_code, 400)
        self.assertEqual(uncertain.json()["detail"]["code"], "printer_state_uncertain")
        self.assertEqual(self.fake_ops.starts, [])


if __name__ == "__main__":
    unittest.main()
