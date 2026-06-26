from __future__ import annotations

import unittest
from pathlib import Path

from backend.app.services.plate_change_3mf_postprocess import PlateChange3mfPhysicalCanaryService


ROOT = Path(__file__).resolve().parents[2]


class PlateChange3mfPhysicalCanaryHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_physical_canary_targets(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-plate-change-3mf-physical-canary:", makefile)
        self.assertIn(
            "test-plate-change-3mf-physical-canary: harness-plate-change-3mf-physical-canary",
            makefile,
        )

    def test_mock_services_do_not_expose_external_physical_canary_execution_server(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")

        forbidden = (
            "/plate-change-3mf/v1/canary-upload",
            "/plate-change-3mf/v1/canary-start",
            "/plate-change-3mf/v1/raw-command",
            "/plate-change-3mf/v1/send-gcode",
            "/plate-change-3mf/v1/execute-gcode",
            "plate_change_3mf_physical_canary_uploads",
            "plate_change_3mf_physical_canary_starts",
            "plate_change_3mf_physical_canary_commands",
            "BAMBU" + "_ACCESS_CODE",
            "PRINTER" + "_SERIAL",
            "MQTT" + "_PASSWORD",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, text)

    def test_status_snapshot_reports_default_blocked_zero_sentinels(self) -> None:
        body = PlateChange3mfPhysicalCanaryService().canary_status(
            physical_canary_enabled=False,
            allow_printer_upload=False,
            allow_print_start=False,
            single_printer_only=True,
            require_human_confirmation=True,
            disable_auto_retry=True,
            max_starts=1,
            output_roots=[],
        )

        self.assertFalse(body["physical_canary_enabled"])
        self.assertFalse(body["printer_upload_supported"])
        self.assertFalse(body["printer_start_supported"])
        self.assertFalse(body["queue_supported"])
        self.assertFalse(body["scheduler_supported"])
        self.assertFalse(body["auto_retry_supported"])
        self.assertEqual(body["start_attempts_used"], 0)
        sentinels = body["sentinels"]
        self.assertIsInstance(sentinels, dict)
        self.assertGreater(len(sentinels), 0)
        for effect, count in sentinels.items():
            with self.subTest(effect=effect):
                self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
