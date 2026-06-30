from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SwapmodBedReadinessHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_swapmod_bed_readiness_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-swapmod-bed-readiness:", makefile)
        self.assertIn("test-swapmod-bed-readiness: harness-swapmod-bed-readiness", makefile)

    def test_mock_services_do_not_expose_swapmod_bed_or_printer_control_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")
        forbidden = [
            "/swapmod/v1/bed-ready",
            "/swapmod/v1/mark-bed-ready",
            "/swapmod/v1/start-next-print",
            "/swapmod/v1/send-command",
            "/swapmod/v1/send-gcode",
            "swapmod_bed_mutations",
            "swapmod_queue_dispatches",
            "swapmod_printer_commands",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
