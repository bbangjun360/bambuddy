from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from backend.app.services.plate_change_3mf_postprocess import (
    PlateChange3mfPhysicalCanaryService,
    PlateChange3mfPostprocessError,
)


_UNSET = object()


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
    def __init__(self, *, upload_ok: bool = True, start_ok: bool = True) -> None:
        self.upload_ok = upload_ok
        self.start_ok = start_ok
        self.uploads: list[tuple[str, Path]] = []
        self.starts: list[tuple[str, str]] = []

    async def upload_artifact(self, printer_id: str, artifact_path: Path) -> str:
        self.uploads.append((printer_id, artifact_path))
        if not self.upload_ok:
            raise PlateChange3mfPostprocessError("printer_upload_failed", "Canary printer upload failed")
        return f"/cache/{artifact_path.name}"

    async def start_print(self, printer_id: str, remote_path: str) -> bool:
        self.starts.append((printer_id, remote_path))
        return self.start_ok


def _write_reviewed_3mf(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("3D/3dmodel.model", b"<model/>")
        zf.writestr("Metadata/project_settings.config", b'{"printer_model": "Bambu Lab A1 Mini"}')
        zf.writestr(
            "Metadata/bambuddy_real_sample_output_review.json",
            json.dumps({"not_approved_for_printing": False, "human_reviewed": True}).encode("utf-8"),
        )
        zf.writestr("Metadata/plate_1.gcode", b"; reviewed synthetic fixture only\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PlateChange3mfPhysicalCanaryServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="wp064-physical-canary-"))
        self.output_root = self.tmp / "outputs"
        self.artifact = self.output_root / "reviewed-output.gcode.3mf"
        self.artifact_sha256 = _write_reviewed_3mf(self.artifact)
        self.service = PlateChange3mfPhysicalCanaryService()
        self.ops = FakeCanaryPrinterOps()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def flags(self, **overrides: object) -> dict[str, object]:
        result: dict[str, object] = {
            "physical_canary_enabled": True,
            "allow_printer_upload": True,
            "allow_print_start": True,
            "single_printer_only": True,
            "require_human_confirmation": True,
            "disable_auto_retry": True,
            "max_starts": 1,
            "output_roots": [self.output_root],
        }
        result.update(overrides)
        return result

    def upload_request(self, **overrides: object) -> dict[str, object]:
        printer_id = str(overrides.get("printer_id", "canary-printer-001"))
        sha = str(overrides.get("artifact_sha256", self.artifact_sha256))
        request: dict[str, object] = {
            "target_printer_ids": [printer_id],
            "artifact_path": str(self.artifact),
            "artifact_sha256": sha,
            "operator_confirmation_phrase": f"CONFIRM_UPLOAD_REVIEWED_3MF {printer_id} {sha}",
        }
        request.update(overrides)
        request.pop("printer_id", None)
        return request

    def start_request(self, **overrides: object) -> dict[str, object]:
        printer_id = str(overrides.get("printer_id", "canary-printer-001"))
        sha = str(overrides.get("artifact_sha256", self.artifact_sha256))
        request: dict[str, object] = {
            "target_printer_ids": [printer_id],
            "artifact_path": str(self.artifact),
            "artifact_sha256": sha,
            "operator_confirmation_phrase": f"CONFIRM_START_REVIEWED_3MF {printer_id} {sha}",
            "checklist": dict(CHECKLIST),
        }
        request.update(overrides)
        request.pop("printer_id", None)
        return request

    async def upload(self, request: dict[str, object] | None = None, **flags: object) -> dict[str, object]:
        return await self.service.canary_upload(
            request or self.upload_request(),
            printer_ops=self.ops,
            **self.flags(**flags),
        )

    async def start(
        self,
        request: dict[str, object] | None = None,
        *,
        printer_state: object = _UNSET,
        **flags: object,
    ) -> dict[str, object]:
        effective_state = SimpleNamespace(state="IDLE", gcode_file=None) if printer_state is _UNSET else printer_state
        return await self.service.canary_start(
            request or self.start_request(),
            printer_ops=self.ops,
            printer_state=effective_state,
            **self.flags(**flags),
        )

    def assert_forbidden_sentinels_zero(self, payload: dict[str, object]) -> None:
        sentinels = payload["sentinels"]
        self.assertIsInstance(sentinels, dict)
        for key, value in sentinels.items():
            with self.subTest(key=key):
                self.assertEqual(value, 0)

    async def test_default_config_blocks_upload_and_start_without_side_effects(self) -> None:
        with self.assertRaises(PlateChange3mfPostprocessError) as upload_error:
            await self.upload(physical_canary_enabled=False)
        self.assertEqual(upload_error.exception.code, "physical_canary_disabled")

        with self.assertRaises(PlateChange3mfPostprocessError) as start_error:
            await self.start(physical_canary_enabled=False)
        self.assertEqual(start_error.exception.code, "physical_canary_disabled")

        self.assertEqual(self.ops.uploads, [])
        self.assertEqual(self.ops.starts, [])
        status = self.service.canary_status(
            **self.flags(physical_canary_enabled=False, allow_printer_upload=False, allow_print_start=False)
        )
        self.assertFalse(status["physical_canary_enabled"])
        self.assertFalse(status["printer_upload_supported"])
        self.assertFalse(status["printer_start_supported"])
        self.assertEqual(status["start_attempts_used"], 0)
        self.assert_forbidden_sentinels_zero(status)

    async def test_upload_requires_all_flags_and_exact_phrase(self) -> None:
        for flag in (
            "physical_canary_enabled",
            "allow_printer_upload",
            "allow_print_start",
            "single_printer_only",
            "require_human_confirmation",
            "disable_auto_retry",
        ):
            with self.subTest(flag=flag):
                with self.assertRaises(PlateChange3mfPostprocessError):
                    await self.upload(**{flag: False})

        with self.assertRaises(PlateChange3mfPostprocessError) as wrong_phrase:
            await self.upload(self.upload_request(operator_confirmation_phrase="CONFIRM_UPLOAD_REVIEWED_3MF wrong"))
        self.assertEqual(wrong_phrase.exception.code, "confirmation_phrase_mismatch")
        self.assertEqual(self.ops.uploads, [])

        result = await self.upload()
        self.assertEqual(result["status"], "CANARY_UPLOAD_RECORDED")
        self.assertEqual(result["printer_id"], "canary-printer-001")
        self.assertEqual(result["artifact_sha256"], self.artifact_sha256)
        self.assertEqual(result["remote_path_redacted"], "redacted-printer-path")
        self.assertEqual(len(self.ops.uploads), 1)

    async def test_start_requires_flags_prior_upload_exact_phrase_and_checklist(self) -> None:
        with self.assertRaises(PlateChange3mfPostprocessError) as no_upload:
            await self.start()
        self.assertEqual(no_upload.exception.code, "prior_upload_required")

        await self.upload()

        for flag in (
            "physical_canary_enabled",
            "allow_printer_upload",
            "allow_print_start",
            "single_printer_only",
            "require_human_confirmation",
            "disable_auto_retry",
        ):
            with self.subTest(flag=flag):
                with self.assertRaises(PlateChange3mfPostprocessError):
                    await self.start(**{flag: False})

        with self.assertRaises(PlateChange3mfPostprocessError) as wrong_phrase:
            await self.start(self.start_request(operator_confirmation_phrase="CONFIRM_START_REVIEWED_3MF wrong"))
        self.assertEqual(wrong_phrase.exception.code, "confirmation_phrase_mismatch")

        missing_checklist = dict(CHECKLIST)
        missing_checklist["power_cutoff_ready"] = False
        with self.assertRaises(PlateChange3mfPostprocessError) as checklist_error:
            await self.start(self.start_request(checklist=missing_checklist))
        self.assertEqual(checklist_error.exception.code, "canary_checklist_incomplete")

        result = await self.start()
        self.assertEqual(result["status"], "CANARY_START_ATTEMPTED")
        self.assertEqual(result["start_attempts_used"], 1)
        self.assertEqual(len(self.ops.starts), 1)

    async def test_upload_phrase_cannot_start_print(self) -> None:
        await self.upload()

        with self.assertRaises(PlateChange3mfPostprocessError) as raised:
            await self.start(
                self.start_request(
                    operator_confirmation_phrase=(
                        f"CONFIRM_UPLOAD_REVIEWED_3MF canary-printer-001 {self.artifact_sha256}"
                    )
                )
            )

        self.assertEqual(raised.exception.code, "confirmation_phrase_mismatch")
        self.assertEqual(self.ops.starts, [])

    async def test_sha_mismatch_outside_output_root_repo_path_multi_printer_and_second_start_block(self) -> None:
        with self.assertRaises(PlateChange3mfPostprocessError) as sha_mismatch:
            await self.upload(self.upload_request(artifact_sha256="0" * 64))
        self.assertEqual(sha_mismatch.exception.code, "artifact_sha256_mismatch")

        outside = self.tmp / "outside" / "reviewed.gcode.3mf"
        outside_sha = _write_reviewed_3mf(outside)
        with self.assertRaises(PlateChange3mfPostprocessError) as outside_error:
            await self.upload(
                self.upload_request(
                    artifact_path=str(outside),
                    artifact_sha256=outside_sha,
                    operator_confirmation_phrase=f"CONFIRM_UPLOAD_REVIEWED_3MF canary-printer-001 {outside_sha}",
                )
            )
        self.assertEqual(outside_error.exception.code, "artifact_path_not_allowed")

        repo_path = Path(__file__).resolve()
        repo_sha = hashlib.sha256(repo_path.read_bytes()).hexdigest()
        with self.assertRaises(PlateChange3mfPostprocessError) as repo_error:
            await self.upload(
                self.upload_request(
                    artifact_path=str(repo_path),
                    artifact_sha256=repo_sha,
                    operator_confirmation_phrase=f"CONFIRM_UPLOAD_REVIEWED_3MF canary-printer-001 {repo_sha}",
                ),
                output_roots=[repo_path.parent],
            )
        self.assertEqual(repo_error.exception.code, "repo_artifact_path_not_allowed")

        with self.assertRaises(PlateChange3mfPostprocessError) as multi_printer:
            await self.upload(
                self.upload_request(
                    target_printer_ids=["canary-printer-001", "canary-printer-002"],
                    operator_confirmation_phrase=f"CONFIRM_UPLOAD_REVIEWED_3MF canary-printer-001 {self.artifact_sha256}",
                )
            )
        self.assertEqual(multi_printer.exception.code, "single_printer_required")

        await self.upload()
        await self.start()
        with self.assertRaises(PlateChange3mfPostprocessError) as second_start:
            await self.start()
        self.assertEqual(second_start.exception.code, "max_start_attempts_reached")
        self.assertEqual(len(self.ops.starts), 1)

    async def test_uncertain_printer_state_blocks_without_consuming_start(self) -> None:
        await self.upload()

        for state in (None, SimpleNamespace(state="RUNNING", gcode_file="active.3mf")):
            with self.subTest(state=state):
                with self.assertRaises(PlateChange3mfPostprocessError) as raised:
                    await self.start(printer_state=state)
                self.assertEqual(raised.exception.code, "printer_state_uncertain")

        self.assertEqual(self.service.canary_status(**self.flags())["start_attempts_used"], 0)
        self.assertEqual(self.ops.starts, [])

    async def test_no_queue_scheduler_retry_raw_gcode_or_secret_fields_in_responses(self) -> None:
        await self.upload()
        result = await self.start()
        status = self.service.canary_status(**self.flags())
        rendered = json.dumps({"start": result, "status": status}, sort_keys=True)

        for token in (
            "retry_scheduled",
            "raw_command",
            "send_gcode",
            "execute_gcode",
            "access_code",
            "serial",
            "token",
            str(self.artifact),
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, rendered)
        self.assertFalse(status["auto_retry_supported"])
        self.assertFalse(status["queue_supported"])
        self.assertFalse(status["scheduler_supported"])
        self.assert_forbidden_sentinels_zero(status)


if __name__ == "__main__":
    unittest.main()
