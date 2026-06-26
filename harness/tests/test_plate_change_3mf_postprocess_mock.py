from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from backend.app.services.plate_change_3mf_postprocess import PlateChange3mfPostprocessService

ROOT = Path(__file__).resolve().parents[2]


class PlateChange3mfPostprocessHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_plate_change_3mf_postprocess_targets(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-plate-change-3mf-postprocess:", makefile)
        self.assertIn("test-plate-change-3mf-postprocess: harness-plate-change-3mf-postprocess", makefile)
        self.assertIn("test-plate-change-3mf-insertion:", makefile)

    def test_mock_services_do_not_expose_external_postprocess_execution_server(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")

        forbidden = (
            "/plate-change-3mf/v1/postprocess",
            "/plate-change-3mf/v1/upload",
            "/plate-change-3mf/v1/start",
            "/plate-change-3mf/v1/execute",
            "plate_change_3mf_uploads",
            "plate_change_3mf_starts",
            "plate_change_3mf_commands",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, text)

    def test_status_snapshot_reports_zero_sentinels_and_no_printer_execution_support(self) -> None:
        body = PlateChange3mfPostprocessService().status_snapshot(
            enabled=False,
            dry_run=True,
            allow_output_artifact=False,
        )

        self.assertFalse(body["printer_upload_supported"])
        self.assertFalse(body["printer_start_supported"])
        self.assertFalse(body["real_execution_supported"])
        self.assertFalse(body["real_gcode_inserted"])
        self.assertFalse(body["output_artifact_created"])
        sentinels = body["sentinels"]
        self.assertIsInstance(sentinels, dict)
        self.assertGreater(len(sentinels), 0)
        for effect, count in sentinels.items():
            with self.subTest(effect=effect):
                self.assertEqual(count, 0)

    def test_tests_do_not_reference_raw_local_sample_directory(self) -> None:
        checked_files = (
            ROOT / "backend/tests/unit/services/test_plate_change_3mf_postprocess.py",
            ROOT / "backend/tests/integration/test_plate_change_3mf_postprocess_api.py",
            ROOT / "harness/tests/test_plate_change_3mf_postprocess_mock.py",
        )
        for path in checked_files:
            with self.subTest(path=path.relative_to(ROOT)):
                sample_dir_token = "plate-change" + "-samples"
                self.assertNotIn(sample_dir_token, path.read_text(encoding="utf-8"))

    def test_no_tracked_or_worktree_generated_3mf_or_gcode_artifacts(self) -> None:
        tracked = subprocess.run(
            ["git", "ls-files", "--", "*.3mf", "*.gcode", "*.gcode.3mf"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(tracked.returncode, 0, tracked.stderr)
        self.assertEqual(tracked.stdout.splitlines(), [])

        worktree = subprocess.run(
            ["git", "status", "--short", "--", "*.3mf", "*.gcode", "*.gcode.3mf"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(worktree.returncode, 0, worktree.stderr)
        self.assertEqual(worktree.stdout.splitlines(), [])


if __name__ == "__main__":
    unittest.main()
