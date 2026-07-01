from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SwapmodSchedulerHandoffDiagnosticsAuthHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_scheduler_handoff_diagnostics_auth_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-swapmod-scheduler-handoff-diagnostics-auth:", makefile)
        self.assertIn(
            "test-swapmod-scheduler-handoff-diagnostics-auth: "
            "harness-swapmod-scheduler-handoff-diagnostics-auth",
            makefile,
        )
        target_body = makefile.split("test-swapmod-scheduler-handoff-diagnostics-auth:", 1)[1].split(
            "\n\n", 1
        )[0]
        self.assertIn("--network none", target_body)
        self.assertIn("backend.tests.integration.test_swapmod_scheduler_handoff_diagnostics_api", target_body)
        self.assertIn("backend.tests.unit.test_swapmod_scheduler_handoff_diagnostics_architecture", target_body)

    def test_mock_services_do_not_expose_auth_bypass_or_command_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")
        forbidden = [
            "/swapmod/v1/scheduler-handoff-diagnostics/auth-bypass",
            "/swapmod/v1/scheduler-handoff-diagnostics/send-command",
            "/swapmod/v1/scheduler-handoff-diagnostics/send-gcode",
            "swapmod_scheduler_handoff_diagnostics_auth_bypasses",
            "swapmod_scheduler_handoff_diagnostics_auth_dispatches",
            "swapmod_scheduler_handoff_diagnostics_auth_printer_commands",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
