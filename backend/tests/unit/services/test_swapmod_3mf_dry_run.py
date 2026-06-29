from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.app.services.swapmod_3mf_dry_run import (
    Swapmod3mfDryRunError,
    Swapmod3mfDryRunService,
)


def write_3mf(root: Path, name: str, gcode: str) -> Path:
    path = root / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Metadata/plate_1.gcode", gcode)
        zf.writestr("3D/3dmodel.model", "<model />")
    return path


class Swapmod3mfDryRunServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.service = Swapmod3mfDryRunService()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_default_status_is_disabled_and_dry_run_only(self) -> None:
        status = self.service.status_snapshot(enabled=False, dry_run=True, allowed_roots=[self.root])

        self.assertFalse(status["enabled"])
        self.assertEqual(status["mode"], "DRY_RUN_ONLY")
        self.assertFalse(status["real_execution_supported"])
        self.assertFalse(status["printer_upload_supported"])
        self.assertFalse(status["printer_start_supported"])

    def test_exact_swapmod_pair_returns_three_redacted_candidates(self) -> None:
        original = "G28\n; print\nG1 X1\nM400\n"
        swapmod = "; load\nG1 Y1\n" + original + "; swap\nG1 Y2\nG4 P100\n" + original + "; final\nG1 Y3\n"
        original_path = write_3mf(self.root, "original.3mf", original)
        swapmod_path = write_3mf(self.root, "swapmod.3mf", swapmod)

        result = self.service.create_plan(
            original_path=original_path,
            swapmod_path=swapmod_path,
            enabled=True,
            dry_run=True,
            request_dry_run=True,
            allowed_roots=[self.root],
        )

        self.assertEqual(result["status"], "SWAPMOD_DRY_RUN_READY")
        self.assertEqual(
            [block["candidate_kind"] for block in result["candidate_blocks"]],
            ["plate_load_only", "inter_job_swap", "final_swap"],
        )
        self.assertTrue(all(block["raw_gcode_included"] is False for block in result["candidate_blocks"]))
        self.assertEqual(result["candidate_blocks"][1]["command_family_counts"]["G1"], 1)
        self.assertEqual(result["candidate_blocks"][1]["command_family_counts"]["G4"], 1)
        self.assertNotIn("G1 Y2", str(result))
        self.assertFalse(result["real_execution_supported"])
        self.assertFalse(result["printer_upload_supported"])
        self.assertFalse(result["printer_start_supported"])
        self.assertTrue(all(value == 0 for value in result["sentinels"].values()))

    def test_ambiguous_swapmod_pair_requires_review(self) -> None:
        original_path = write_3mf(self.root, "original.3mf", "G28\nG1 X1\n")
        swapmod_path = write_3mf(self.root, "swapmod.3mf", "G28\nG1 X1\n; only once\n")

        result = self.service.create_plan(
            original_path=original_path,
            swapmod_path=swapmod_path,
            enabled=True,
            dry_run=True,
            request_dry_run=True,
            allowed_roots=[self.root],
        )

        self.assertEqual(result["status"], "SWAPMOD_DRY_RUN_REVIEW_REQUIRED")
        self.assertEqual(result["candidate_blocks"], [])
        self.assertIn("expected_exactly_two_original_occurrences", result["review_reasons"])

    def test_repository_path_is_rejected(self) -> None:
        with self.assertRaises(Swapmod3mfDryRunError) as raised:
            self.service.create_plan(
                original_path=Path("repo.3mf"),
                swapmod_path=Path("repo-swap.3mf"),
                enabled=True,
                dry_run=True,
                request_dry_run=True,
                allowed_roots=[Path.cwd()],
                repository_root=Path.cwd(),
            )

        self.assertEqual(raised.exception.code, "source_path_not_allowed")

    def test_raw_gcode_source_is_rejected(self) -> None:
        original_path = self.root / "original.gcode"
        original_path.write_text("G28\n")
        swapmod_path = write_3mf(self.root, "swapmod.3mf", "G28\n")

        with self.assertRaises(Swapmod3mfDryRunError) as raised:
            self.service.create_plan(
                original_path=original_path,
                swapmod_path=swapmod_path,
                enabled=True,
                dry_run=True,
                request_dry_run=True,
                allowed_roots=[self.root],
            )

        self.assertEqual(raised.exception.code, "unsupported_source_file")

    def test_3mf_without_gcode_member_is_rejected(self) -> None:
        original_path = self.root / "original.3mf"
        swapmod_path = self.root / "swapmod.3mf"
        for path in (original_path, swapmod_path):
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("3D/3dmodel.model", "<model />")

        with self.assertRaises(Swapmod3mfDryRunError) as raised:
            self.service.create_plan(
                original_path=original_path,
                swapmod_path=swapmod_path,
                enabled=True,
                dry_run=True,
                request_dry_run=True,
                allowed_roots=[self.root],
            )

        self.assertEqual(raised.exception.code, "gcode_member_required")

    def test_workflow_trace_is_dry_run_only(self) -> None:
        original = "G28\nG1 X1\n"
        swapmod = "; load\n" + original + "; swap\nG1 Y2\n" + original + "; final\n"
        result = self.service.create_plan(
            original_path=write_3mf(self.root, "original.3mf", original),
            swapmod_path=write_3mf(self.root, "swapmod.3mf", swapmod),
            enabled=True,
            dry_run=True,
            request_dry_run=True,
            allowed_roots=[self.root],
        )

        self.assertEqual(
            [step["state"] for step in result["workflow_trace"]],
            [
                "WAIT_ORIGINAL_FINISH",
                "EXTRACT_REVIEWED_SWAP_BLOCK",
                "MANUAL_REVIEW_REQUIRED",
                "WOULD_SEND_ALLOWLISTED_SEQUENCE",
                "WOULD_START_NEXT_PRINT",
            ],
        )
        self.assertTrue(all(step["dry_run_only"] is True for step in result["workflow_trace"]))


if __name__ == "__main__":
    unittest.main()
