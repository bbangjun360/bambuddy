from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.app.services.plate_change_3mf_postprocess import (
    PlateChange3mfPostprocessError,
    PlateChange3mfPostprocessService,
)


def _write_3mf(path: Path, entries: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries.items():
            zf.writestr(name, payload)


def _synthetic_3mf_entries() -> dict[str, bytes]:
    return {
        "3D/3dmodel.model": b"<model unit='millimeter'/>",
        "Metadata/project_settings.config": json.dumps({"printer_model": "Bambu Lab A1 Mini"}).encode("utf-8"),
        "Metadata/slice_info.config": b"<config><plate><metadata key='index' value='1'/></plate></config>",
        "Metadata/plate_1.gcode": (
            b"; synthetic fixture generated in test\n"
            b";LAYER_CHANGE\n"
            b"G1 X10 Y10 F3000\n"
            b"; stop printing object\n"
            b"M400\n"
            b";END gcode for filament\n"
        ),
    }


class PlateChange3mfPostprocessServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="wp064-3mf-postprocess-"))
        self.service = PlateChange3mfPostprocessService()
        self.source = self.tmp / "inputs" / "customer-secret-part.gcode.3mf"
        _write_3mf(self.source, _synthetic_3mf_entries())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def create_plan(self, **overrides: object) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "source_path": self.source,
            "enabled": True,
            "dry_run": True,
            "allow_output_artifact": False,
            "allowed_roots": [self.tmp],
        }
        kwargs.update(overrides)
        return self.service.create_plan(**kwargs)

    def assert_no_side_effects(self, payload: dict[str, object]) -> None:
        self.assertFalse(payload["printer_upload_supported"])
        self.assertFalse(payload["printer_start_supported"])
        self.assertFalse(payload["real_execution_supported"])
        self.assertFalse(payload["output_artifact_created"])
        sentinels = payload["sentinels"]
        self.assertIsInstance(sentinels, dict)
        for effect, count in sentinels.items():
            with self.subTest(effect=effect):
                self.assertEqual(count, 0)

    def test_redacted_plan_lists_internal_gcode_paths_without_output_artifact(self) -> None:
        result = self.create_plan()

        self.assertEqual(result["status"], "POSTPROCESS_PLAN_READY")
        self.assertTrue(result["prototype_only"])
        self.assertFalse(result["postprocess_supported"])
        self.assertEqual(result["source_file_name_redacted"], "redacted-gcode-3mf")
        self.assertIn("Metadata/plate_1.gcode", result["internal_file_listing"])
        self.assertEqual(result["internal_gcode_paths"], ["Metadata/plate_1.gcode"])
        self.assertEqual(result["detected_printer_model_family"], "A1 Mini")
        self.assertGreaterEqual(len(result["candidate_blocks"]), 1)
        self.assertGreaterEqual(len(result["insertion_points"]), 1)
        self.assertIn("WP-064-A does not upload, start, send MQTT, use FTPS, or execute G-code", result["safety_notes"])
        self.assert_no_side_effects(result)

        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("customer-secret-part", rendered)
        self.assertNotIn("G1 X10", rendered)
        self.assertNotIn("M400", rendered)
        self.assertNotIn("synthetic fixture generated in test", rendered)
        self.assertFalse((self.tmp / "postprocess-output").exists())

    def test_rejects_raw_gcode_source_path(self) -> None:
        raw_gcode = self.tmp / "inputs" / "raw-sample.gcode"
        raw_gcode.write_text("G1 X1 Y1\n", encoding="utf-8")

        with self.assertRaises(PlateChange3mfPostprocessError) as raised:
            self.create_plan(source_path=raw_gcode)

        self.assertEqual(raised.exception.code, "unsupported_source_file")

    def test_rejects_source_path_outside_controlled_roots(self) -> None:
        outside_dir = Path(tempfile.mkdtemp(prefix="wp064-outside-"))
        try:
            outside = outside_dir / "outside.gcode.3mf"
            _write_3mf(outside, _synthetic_3mf_entries())

            with self.assertRaises(PlateChange3mfPostprocessError) as raised:
                self.create_plan(source_path=outside)

            self.assertEqual(raised.exception.code, "source_path_not_allowed")
        finally:
            shutil.rmtree(outside_dir, ignore_errors=True)

    def test_requires_enabled_dry_run_runtime(self) -> None:
        with self.assertRaises(PlateChange3mfPostprocessError) as disabled:
            self.create_plan(enabled=False)
        self.assertEqual(disabled.exception.code, "feature_disabled")

        with self.assertRaises(PlateChange3mfPostprocessError) as not_dry_run:
            self.create_plan(dry_run=False)
        self.assertEqual(not_dry_run.exception.code, "dry_run_required")

    def test_rejects_invalid_3mf_zip(self) -> None:
        bad = self.tmp / "inputs" / "broken.gcode.3mf"
        bad.write_bytes(b"not a zip")

        with self.assertRaises(PlateChange3mfPostprocessError) as raised:
            self.create_plan(source_path=bad)

        self.assertEqual(raised.exception.code, "invalid_3mf")

    def test_output_artifact_requires_explicit_setting_and_stays_in_temp_root(self) -> None:
        with self.assertRaises(PlateChange3mfPostprocessError) as not_allowed:
            self.create_plan(create_output_artifact=True, output_dir=self.tmp / "postprocess-output")
        self.assertEqual(not_allowed.exception.code, "output_artifact_not_allowed")

        outside_output = Path(tempfile.mkdtemp(prefix="wp064-output-outside-"))
        try:
            with self.assertRaises(PlateChange3mfPostprocessError) as outside:
                self.create_plan(
                    allow_output_artifact=True,
                    create_output_artifact=True,
                    output_dir=outside_output,
                )
            self.assertEqual(outside.exception.code, "output_path_not_allowed")
        finally:
            shutil.rmtree(outside_output, ignore_errors=True)

        output_dir = self.tmp / "postprocess-output"
        result = self.create_plan(
            allow_output_artifact=True,
            create_output_artifact=True,
            output_dir=output_dir,
        )

        self.assertTrue(result["output_artifact_created"])
        self.assertEqual(result["output_artifact_root_redacted"], "controlled-temp-output")
        outputs = list(output_dir.glob("*.3mf"))
        self.assertEqual(len(outputs), 1)
        self.assertTrue(outputs[0].resolve().is_relative_to(self.tmp.resolve()))
        with zipfile.ZipFile(outputs[0], "r") as zf:
            self.assertIn("Metadata/bambuddy_plate_change_postprocess_plan.json", zf.namelist())
            self.assertEqual(zf.read("Metadata/plate_1.gcode"), _synthetic_3mf_entries()["Metadata/plate_1.gcode"])


if __name__ == "__main__":
    unittest.main()
