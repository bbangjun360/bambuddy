from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class SwapmodSchedulerHandoffDiagnosticsGateStatusContractHarnessTest(unittest.TestCase):
    def test_makefile_exposes_scheduler_handoff_diagnostics_gate_status_contract_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-swapmod-scheduler-handoff-diagnostics-gate-status-contract:", makefile)
        self.assertIn(
            "test-swapmod-scheduler-handoff-diagnostics-gate-status-contract: "
            "harness-swapmod-scheduler-handoff-diagnostics-gate-status-contract",
            makefile,
        )
        target_body = makefile.split(
            "test-swapmod-scheduler-handoff-diagnostics-gate-status-contract:", 1
        )[1].split("\n\n", 1)[0]
        self.assertIn("--network none", target_body)
        self.assertIn("backend.tests.integration.test_swapmod_scheduler_handoff_diagnostics_api", target_body)
        self.assertIn("backend.tests.unit.test_swapmod_scheduler_handoff_diagnostics_architecture", target_body)

    def test_mock_services_do_not_expose_gate_status_contract_command_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")
        prefix = "/swapmod/v1/scheduler-handoff-diagnostics/gate-status-contract"
        forbidden_suffixes = [
            "/send-command",
            "/send-gcode",
            "/dispatch",
            "/printer-command",
            "/bed-action",
        ]
        for suffix in forbidden_suffixes:
            with self.subTest(suffix=suffix):
                self.assertNotIn(f"{prefix}{suffix}", text)


if __name__ == "__main__":
    unittest.main()
