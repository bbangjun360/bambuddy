from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SwapmodSchedulerConsumedHandoffRetryHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_consumed_handoff_retry_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-swapmod-scheduler-consumed-handoff-retry:", makefile)
        self.assertIn(
            "test-swapmod-scheduler-consumed-handoff-retry: "
            "harness-swapmod-scheduler-consumed-handoff-retry",
            makefile,
        )
        target_body = makefile.split("test-swapmod-scheduler-consumed-handoff-retry:", 1)[1].split("\n\n", 1)[0]
        self.assertIn("--network none", target_body)
        self.assertIn("backend.tests.unit.services.test_swapmod_scheduler_consumed_handoff_retry", target_body)
        self.assertIn("backend.tests.unit.test_swapmod_scheduler_consumed_handoff_retry_architecture", target_body)

    def test_mock_services_do_not_expose_retry_dispatch_or_printer_control_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")
        forbidden = [
            "/swapmod/v1/scheduler-consumed-handoff-retry",
            "/swapmod/v1/retry-consumed-handoff",
            "/swapmod/v1/start-next-print",
            "/swapmod/v1/dispatch-next-print",
            "/swapmod/v1/send-command",
            "/swapmod/v1/send-gcode",
            "swapmod_consumed_handoff_retry_dispatches",
            "swapmod_consumed_handoff_retry_printer_commands",
            "swapmod_scheduler_dispatches",
            "swapmod_printer_commands",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
