from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SwapmodNextPrintGateHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_swapmod_next_print_gate_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-swapmod-next-print-gate:", makefile)
        self.assertIn("test-swapmod-next-print-gate: harness-swapmod-next-print-gate", makefile)

    def test_mock_services_do_not_expose_next_print_or_printer_control_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")
        forbidden = [
            "/swapmod/v1/next-print",
            "/swapmod/v1/start-next-print",
            "/swapmod/v1/dispatch-next-print",
            "/swapmod/v1/send-command",
            "/swapmod/v1/send-gcode",
            "swapmod_next_print_dispatches",
            "swapmod_queue_dispatches",
            "swapmod_printer_commands",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
