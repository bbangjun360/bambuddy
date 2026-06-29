from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SwapmodStateMachineHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_swapmod_state_machine_targets(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-swapmod-state-machine:", makefile)
        self.assertIn("test-swapmod-state-machine: harness-swapmod-state-machine", makefile)
        self.assertIn("harness-swapmod-operator-trigger:", makefile)
        self.assertIn("test-swapmod-operator-trigger: harness-swapmod-operator-trigger", makefile)
        self.assertIn("harness-swapmod-verification-adapter:", makefile)
        self.assertIn("test-swapmod-verification-adapter: harness-swapmod-verification-adapter", makefile)
        self.assertIn("harness-swapmod-transport-boundary:", makefile)
        self.assertIn("test-swapmod-transport-boundary: harness-swapmod-transport-boundary", makefile)

    def test_mock_services_do_not_expose_swapmod_hardware_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")
        forbidden = [
            "/swapmod/v1/send-command",
            "/swapmod/v1/send-gcode",
            "/swapmod/v1/raw-command",
            "/swapmod/v1/start-next-print",
            "swapmod_printer_commands",
            "swapmod_queue_dispatches",
            "swapmod_bed_mutations",
            "/swapmod/v1/real-transport",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
