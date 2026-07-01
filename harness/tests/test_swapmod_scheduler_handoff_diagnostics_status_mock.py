from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SwapmodSchedulerHandoffDiagnosticsStatusHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_scheduler_handoff_diagnostics_status_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-swapmod-scheduler-handoff-diagnostics-status:", makefile)
        self.assertIn(
            "test-swapmod-scheduler-handoff-diagnostics-status: "
            "harness-swapmod-scheduler-handoff-diagnostics-status",
            makefile,
        )
        target_body = makefile.split("test-swapmod-scheduler-handoff-diagnostics-status:", 1)[1].split(
            "\n\n", 1
        )[0]
        self.assertIn("--network none", target_body)
        self.assertIn("backend.tests.integration.test_swapmod_scheduler_handoff_diagnostics_api", target_body)
        self.assertIn("backend.tests.unit.test_swapmod_scheduler_handoff_diagnostics_architecture", target_body)

    def test_mock_services_do_not_expose_status_command_or_dispatch_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")
        forbidden = [
            "/swapmod/v1/scheduler-handoff-diagnostics/status/start",
            "/swapmod/v1/scheduler-handoff-diagnostics/status/dispatch",
            "/swapmod/v1/scheduler-handoff-diagnostics/status/send-command",
            "/swapmod/v1/scheduler-handoff-diagnostics/status/send-gcode",
            "swapmod_scheduler_handoff_diagnostics_status_dispatches",
            "swapmod_scheduler_handoff_diagnostics_status_printer_commands",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
