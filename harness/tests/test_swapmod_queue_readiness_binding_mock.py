from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SwapmodQueueReadinessBindingHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_swapmod_queue_readiness_binding_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-swapmod-queue-readiness-binding:", makefile)
        self.assertIn(
            "test-swapmod-queue-readiness-binding: harness-swapmod-queue-readiness-binding",
            makefile,
        )

    def test_mock_services_do_not_expose_binding_dispatch_or_printer_control_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")
        forbidden = [
            "/swapmod/v1/queue-readiness-binding",
            "/swapmod/v1/start-next-print",
            "/swapmod/v1/dispatch-next-print",
            "/swapmod/v1/send-command",
            "/swapmod/v1/send-gcode",
            "swapmod_queue_readiness_dispatches",
            "swapmod_queue_binding_printer_commands",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
