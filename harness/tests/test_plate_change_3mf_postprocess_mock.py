from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PlateChange3mfPostprocessHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_plate_change_3mf_postprocess_targets(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-plate-change-3mf-postprocess:", makefile)
        self.assertIn("test-plate-change-3mf-postprocess: harness-plate-change-3mf-postprocess", makefile)

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


if __name__ == "__main__":
    unittest.main()
