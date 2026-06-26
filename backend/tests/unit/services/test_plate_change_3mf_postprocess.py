from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.app.services.plate_change_3mf_postprocess import (
    PlateChange3mfPostprocessError,
    PlateChange3mfPostprocessService,
)

SYMBOLIC_PLATE_CHANGE_BLOCK = (
    "; BAMBUDDY_PLATE_CHANGE_BLOCK_START\n"
    "; symbolic_step: PLATE_CHANGE_REVIEW_REQUIRED\n"
    "; symbolic_step: NO_REAL_GCODE_IN_WP_064_B\n"
    "; BAMBUDDY_PLATE_CHANGE_BLOCK_END\n"
)
SYNTHETIC_INSERTION_POINT = "; BAMBUDDY_SYNTHETIC_PLATE_CHANGE_INSERTION_POINT"
TARGET_GCODE_PATH = "Metadata/plate_1.gcode"
REAL_SAMPLE_TARGET_GCODE_PATH = "Metadata/plate_real_sample.gcode"
REVIEW_MANIFEST_PATH = "Metadata/bambuddy_real_sample_output_review.json"


def _write_3mf(path: Path, entries: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries.items():
            zf.writestr(name, payload)


def _read_3mf(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist() if not name.endswith("/")}


def _synthetic_3mf_entries() -> dict[str, bytes]:
    return {
        "3D/3dmodel.model": b"<model unit='millimeter'/>",
        "Metadata/project_settings.config": json.dumps({"printer_model": "Bambu Lab A1 Mini"}).encode("utf-8"),
        "Metadata/slice_info.config": b"<config><plate><metadata key='index' value='1'/></plate></config>",
        TARGET_GCODE_PATH: (
            b"; synthetic fixture generated in test\n"
            b";LAYER_CHANGE\n"
            b"; symbolic travel placeholder redacted\n"
            b"; BAMBUDDY_SYNTHETIC_PLATE_CHANGE_INSERTION_POINT\n"
            b"; stop printing object\n"
            b";END gcode for filament\n"
        ),
        "Metadata/plate_2.gcode": (
            b"; unrelated synthetic internal gcode member\n"
            b";LAYER_CHANGE\n"
            b"; symbolic content remains byte-preserved\n"
        ),
    }


def _unsupported_3mf_entries() -> dict[str, bytes]:
    entries = _synthetic_3mf_entries()
    entries[TARGET_GCODE_PATH] = (
        b"; synthetic fixture without deterministic insertion marker\n"
        b";LAYER_CHANGE\n"
        b"; stop printing object\n"
        b";END gcode for filament\n"
    )
    return entries


def _real_sample_review_entries() -> dict[str, bytes]:
    return {
        "3D/3dmodel.model": b"<model unit='millimeter'/>",
        "Metadata/project_settings.config": json.dumps({"printer_model": "Bambu Lab A1 Mini"}).encode("utf-8"),
        REAL_SAMPLE_TARGET_GCODE_PATH: (
            b"; synthetic local review fixture\n"
            b"; private operator note must not be returned\n"
            b";LAYER_CHANGE\n"
            b"; stop printing object\n"
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
        self.assertTrue(payload["human_review_required"])
        self.assertTrue(payload["not_approved_for_printing"])
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
        self.assertIn(TARGET_GCODE_PATH, result["internal_file_listing"])
        self.assertEqual(result["internal_gcode_paths"], [TARGET_GCODE_PATH, "Metadata/plate_2.gcode"])
        self.assertEqual(result["detected_printer_model_family"], "A1 Mini")
        self.assertGreaterEqual(len(result["candidate_blocks"]), 1)
        self.assertGreaterEqual(len(result["insertion_points"]), 1)
        self.assertFalse(result["insertion_performed"])
        self.assertTrue(result["insertion_marker_present"])
        self.assertIsNone(result["inserted_block_kind"])
        self.assertEqual(result["modified_member_paths"], [])
        self.assertFalse(result["real_gcode_inserted"])
        self.assertIn("WP-064-A does not upload, start, send MQTT, use FTPS, or execute G-code", result["safety_notes"])
        self.assert_no_side_effects(result)

        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("customer-secret-part", rendered)
        self.assertNotIn("synthetic fixture generated in test", rendered)
        self.assertNotIn(SYNTHETIC_INSERTION_POINT, rendered)
        self.assertFalse((self.tmp / "postprocess-output").exists())

    def test_rejects_raw_gcode_source_path(self) -> None:
        raw_gcode = self.tmp / "inputs" / "raw-sample.gcode"
        raw_gcode.write_text("; raw gcode fixture placeholder\n", encoding="utf-8")

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

    def test_output_artifact_blocked_by_default(self) -> None:
        with self.assertRaises(PlateChange3mfPostprocessError) as not_allowed:
            self.create_plan(create_output_artifact=True, output_dir=self.tmp / "postprocess-output")
        self.assertEqual(not_allowed.exception.code, "output_artifact_not_allowed")

    def test_output_artifact_allowed_only_in_controlled_temp_root(self) -> None:
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
        self.assertTrue(result["insertion_performed"])
        self.assertEqual(result["output_artifact_root_redacted"], "controlled-temp-output")
        outputs = list(output_dir.glob("*.3mf"))
        self.assertEqual(len(outputs), 1)
        self.assertTrue(outputs[0].resolve().is_relative_to(self.tmp.resolve()))

    def test_deterministic_insertion_produces_same_output_hash_for_same_input(self) -> None:
        first = self.create_plan(
            allow_output_artifact=True,
            create_output_artifact=True,
            output_dir=self.tmp / "first-output",
        )
        second = self.create_plan(
            allow_output_artifact=True,
            create_output_artifact=True,
            output_dir=self.tmp / "second-output",
        )

        self.assertTrue(first["insertion_performed"])
        self.assertTrue(second["insertion_performed"])
        self.assertEqual(first["source_sha256"], second["source_sha256"])
        self.assertEqual(first["output_sha256"], second["output_sha256"])
        self.assertNotEqual(first["source_sha256"], first["output_sha256"])
        self.assertEqual(first["inserted_block_kind"], "SYMBOLIC_PLATE_CHANGE_REVIEW_ONLY")
        self.assertEqual(first["modified_member_paths"], [TARGET_GCODE_PATH])
        self.assertEqual(first["preserved_member_count"], len(_synthetic_3mf_entries()) - 1)
        self.assertFalse(first["real_gcode_inserted"])
        self.assertEqual(
            first["deterministic_diff_summary"],
            {
                "summary": "Inserted one symbolic WP-064-B marker block into one synthetic internal G-code member",
                "target_internal_gcode_path": TARGET_GCODE_PATH,
                "inserted_block_count": 1,
                "modified_member_count": 1,
                "preserved_member_count": len(_synthetic_3mf_entries()) - 1,
                "zip_member_count_before": len(_synthetic_3mf_entries()),
                "zip_member_count_after": len(_synthetic_3mf_entries()),
                "raw_gcode_included": False,
                "requires_human_diff_review": True,
            },
        )

        first_output = next((self.tmp / "first-output").glob("*.3mf"))
        second_output = next((self.tmp / "second-output").glob("*.3mf"))
        self.assertEqual(first_output.read_bytes(), second_output.read_bytes())

    def test_insertion_marker_appears_exactly_once(self) -> None:
        output_dir = self.tmp / "marker-output"
        self.create_plan(
            allow_output_artifact=True,
            create_output_artifact=True,
            output_dir=output_dir,
        )

        output = next(output_dir.glob("*.3mf"))
        modified_gcode = _read_3mf(output)[TARGET_GCODE_PATH].decode("utf-8")
        self.assertEqual(modified_gcode.count("; BAMBUDDY_PLATE_CHANGE_BLOCK_START"), 1)
        self.assertEqual(modified_gcode.count("; BAMBUDDY_PLATE_CHANGE_BLOCK_END"), 1)
        self.assertIn(SYMBOLIC_PLATE_CHANGE_BLOCK + SYNTHETIC_INSERTION_POINT, modified_gcode)
        self.assertNotRegex(SYMBOLIC_PLATE_CHANGE_BLOCK, re.compile(r"(?m)^\s*[GMT]\d+"))

    def test_only_target_internal_gcode_member_changes_and_others_are_byte_preserved(self) -> None:
        output_dir = self.tmp / "preserve-output"
        self.create_plan(
            allow_output_artifact=True,
            create_output_artifact=True,
            output_dir=output_dir,
        )

        source_entries = _read_3mf(self.source)
        output_entries = _read_3mf(next(output_dir.glob("*.3mf")))
        self.assertEqual(sorted(output_entries), sorted(source_entries))
        for name, payload in source_entries.items():
            with self.subTest(name=name):
                if name == TARGET_GCODE_PATH:
                    self.assertNotEqual(output_entries[name], payload)
                else:
                    self.assertEqual(output_entries[name], payload)

    def test_unknown_or_unsupported_3mf_structure_returns_safe_blocked_result(self) -> None:
        unsupported = self.tmp / "inputs" / "unsupported.gcode.3mf"
        _write_3mf(unsupported, _unsupported_3mf_entries())
        output_dir = self.tmp / "unsupported-output"

        result = self.create_plan(
            source_path=unsupported,
            allow_output_artifact=True,
            create_output_artifact=True,
            output_dir=output_dir,
        )

        self.assertEqual(result["status"], "POSTPROCESS_UNSUPPORTED")
        self.assertFalse(result["output_artifact_created"])
        self.assertFalse(result["insertion_performed"])
        self.assertFalse(result["insertion_marker_present"])
        self.assertIsNone(result["inserted_block_kind"])
        self.assertIsNone(result["output_sha256"])
        self.assertEqual(result["modified_member_paths"], [])
        self.assertFalse(result["real_gcode_inserted"])
        self.assertFalse(output_dir.exists())

    def test_inserted_output_preserves_zip_structure_without_manifest_side_channel(self) -> None:
        output_dir = self.tmp / "postprocess-output"
        result = self.create_plan(
            allow_output_artifact=True,
            create_output_artifact=True,
            output_dir=output_dir,
        )

        self.assertTrue(result["output_artifact_created"])
        outputs = list(output_dir.glob("*.3mf"))
        self.assertEqual(len(outputs), 1)
        with zipfile.ZipFile(outputs[0], "r") as zf:
            self.assertNotIn("Metadata/bambuddy_plate_change_postprocess_plan.json", zf.namelist())
            self.assertEqual(sorted(zf.namelist()), sorted(_synthetic_3mf_entries()))


    def test_real_sample_output_review_blocked_by_default_config(self) -> None:
        sample_root = self.tmp / "sample-root"
        output_root = self.tmp / "output-root"
        source = sample_root / "inputs" / "private-local-sample.gcode.3mf"
        _write_3mf(source, _real_sample_review_entries())

        with self.assertRaises(PlateChange3mfPostprocessError) as raised:
            self.create_plan(
                source_path=source,
                allow_output_artifact=True,
                create_output_artifact=True,
                real_sample_output_review=True,
                real_sample_roots=[sample_root],
                output_roots=[output_root],
                output_dir=output_root,
            )

        self.assertEqual(raised.exception.code, "real_sample_output_not_allowed")
        self.assertFalse(output_root.exists())

    def test_real_sample_output_review_requires_all_explicit_flags(self) -> None:
        sample_root = self.tmp / "sample-root"
        output_root = self.tmp / "output-root"
        source = sample_root / "inputs" / "private-local-sample.gcode.3mf"
        _write_3mf(source, _real_sample_review_entries())

        base_kwargs = {
            "source_path": source,
            "allow_output_artifact": True,
            "allow_real_sample_output": True,
            "real_sample_output_review": True,
            "real_sample_roots": [sample_root],
            "output_roots": [output_root],
            "output_dir": output_root,
        }

        with self.assertRaises(PlateChange3mfPostprocessError) as missing_output_request:
            self.create_plan(**{**base_kwargs, "create_output_artifact": False})
        self.assertEqual(missing_output_request.exception.code, "output_artifact_required")

        with self.assertRaises(PlateChange3mfPostprocessError) as missing_output_config:
            self.create_plan(**{**base_kwargs, "allow_output_artifact": False, "create_output_artifact": True})
        self.assertEqual(missing_output_config.exception.code, "output_artifact_not_allowed")

        with self.assertRaises(PlateChange3mfPostprocessError) as missing_real_sample_config:
            self.create_plan(**{**base_kwargs, "allow_real_sample_output": False, "create_output_artifact": True})
        self.assertEqual(missing_real_sample_config.exception.code, "real_sample_output_not_allowed")

        with self.assertRaises(PlateChange3mfPostprocessError) as missing_request_flag:
            self.create_plan(
                source_path=source,
                allow_output_artifact=True,
                allow_real_sample_output=True,
                create_output_artifact=True,
                real_sample_output_review=False,
                real_sample_roots=[sample_root],
                output_roots=[output_root],
                output_dir=output_root,
            )
        self.assertEqual(missing_request_flag.exception.code, "real_sample_output_review_required")

    def test_real_sample_input_must_be_under_sample_root(self) -> None:
        sample_root = self.tmp / "sample-root"
        output_root = self.tmp / "output-root"
        outside_source = self.tmp / "outside" / "private-local-sample.gcode.3mf"
        _write_3mf(outside_source, _real_sample_review_entries())

        with self.assertRaises(PlateChange3mfPostprocessError) as raised:
            self.create_plan(
                source_path=outside_source,
                allow_output_artifact=True,
                allow_real_sample_output=True,
                create_output_artifact=True,
                real_sample_output_review=True,
                real_sample_roots=[sample_root],
                output_roots=[output_root],
                output_dir=output_root,
            )

        self.assertEqual(raised.exception.code, "source_path_not_allowed")

    def test_real_sample_output_must_be_under_output_root(self) -> None:
        sample_root = self.tmp / "sample-root"
        output_root = self.tmp / "output-root"
        outside_output = self.tmp / "outside-output"
        source = sample_root / "inputs" / "private-local-sample.gcode.3mf"
        _write_3mf(source, _real_sample_review_entries())

        with self.assertRaises(PlateChange3mfPostprocessError) as raised:
            self.create_plan(
                source_path=source,
                allow_output_artifact=True,
                allow_real_sample_output=True,
                create_output_artifact=True,
                real_sample_output_review=True,
                real_sample_roots=[sample_root],
                output_roots=[output_root],
                output_dir=outside_output,
            )

        self.assertEqual(raised.exception.code, "output_path_not_allowed")
        self.assertFalse(outside_output.exists())

    def test_real_sample_output_blocks_repo_path_output(self) -> None:
        repo_root = Path(__file__).resolve().parents[4]
        sample_root = self.tmp / "sample-root"
        source = sample_root / "inputs" / "private-local-sample.gcode.3mf"
        _write_3mf(source, _real_sample_review_entries())

        with self.assertRaises(PlateChange3mfPostprocessError) as raised:
            self.create_plan(
                source_path=source,
                allow_output_artifact=True,
                allow_real_sample_output=True,
                create_output_artifact=True,
                real_sample_output_review=True,
                real_sample_roots=[sample_root],
                output_roots=[repo_root],
                output_dir=repo_root / "tmp-review-output",
            )

        self.assertEqual(raised.exception.code, "repo_output_path_not_allowed")

    def test_real_sample_output_review_manifest_only_returns_required_metadata(self) -> None:
        sample_root = self.tmp / "sample-root"
        output_root = self.tmp / "output-root"
        source = sample_root / "inputs" / "private-local-sample.gcode.3mf"
        entries = _real_sample_review_entries()
        _write_3mf(source, entries)

        result = self.create_plan(
            source_path=source,
            allow_output_artifact=True,
            allow_real_sample_output=True,
            create_output_artifact=True,
            real_sample_output_review=True,
            real_sample_roots=[sample_root],
            output_roots=[output_root],
            output_dir=output_root / "reviews",
        )

        self.assertEqual(result["status"], "POSTPROCESS_PLAN_READY")
        self.assertTrue(result["output_artifact_created"])
        self.assertFalse(result["insertion_performed"])
        self.assertIsNone(result["inserted_block_kind"])
        self.assertEqual(result["source_file_name_redacted"], "redacted-gcode-3mf")
        self.assertEqual(result["output_artifact_root_redacted"], "configured-real-sample-output")
        self.assertEqual(result["output_file_name_redacted"], result["output_artifact_file_name_redacted"])
        self.assertRegex(result["source_sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(result["output_sha256"], r"^[a-f0-9]{64}$")
        self.assertNotEqual(result["source_sha256"], result["output_sha256"])
        self.assertEqual(result["internal_gcode_paths"], [REAL_SAMPLE_TARGET_GCODE_PATH])
        self.assertEqual(result["modified_internal_paths"], [REVIEW_MANIFEST_PATH])
        self.assertEqual(result["modified_member_paths"], [REVIEW_MANIFEST_PATH])
        self.assertEqual(result["preserved_member_count"], len(entries))
        self.assertTrue(result["human_review_required"])
        self.assertTrue(result["not_approved_for_printing"])
        self.assertFalse(result["real_gcode_inserted"])
        self.assertFalse(result["printer_upload_supported"])
        self.assertFalse(result["printer_start_supported"])
        self.assertFalse(result["real_execution_supported"])
        self.assertEqual(
            result["deterministic_diff_summary"],
            {
                "summary": "Added deterministic review manifest only; no internal G-code was modified",
                "target_internal_gcode_path": None,
                "added_internal_paths": [REVIEW_MANIFEST_PATH],
                "modified_internal_paths": [REVIEW_MANIFEST_PATH],
                "inserted_block_count": 0,
                "modified_member_count": 0,
                "added_member_count": 1,
                "preserved_member_count": len(entries),
                "zip_member_count_before": len(entries),
                "zip_member_count_after": len(entries) + 1,
                "raw_gcode_included": False,
                "human_review_required": True,
                "not_approved_for_printing": True,
            },
        )

        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("private-local-sample", rendered)
        self.assertNotIn("private operator note", rendered)
        self.assertNotIn("synthetic local review fixture", rendered)

        outputs = list((output_root / "reviews").glob("*.3mf"))
        self.assertEqual(len(outputs), 1)
        output_entries = _read_3mf(outputs[0])
        self.assertEqual(sorted(output_entries), sorted([*entries.keys(), REVIEW_MANIFEST_PATH]))
        for name, payload in entries.items():
            with self.subTest(name=name):
                self.assertEqual(output_entries[name], payload)
        manifest = json.loads(output_entries[REVIEW_MANIFEST_PATH].decode("utf-8"))
        self.assertEqual(manifest["mode"], "REAL_SAMPLE_OUTPUT_REVIEW_ONLY")
        self.assertTrue(manifest["human_review_required"])
        self.assertTrue(manifest["not_approved_for_printing"])
        self.assertFalse(manifest["raw_gcode_included"])


if __name__ == "__main__":
    unittest.main()
