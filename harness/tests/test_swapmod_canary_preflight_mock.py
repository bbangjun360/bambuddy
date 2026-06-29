from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SwapmodCanaryPreflightHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_swapmod_canary_preflight_targets(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("harness-swapmod-canary-preflight:", makefile)
        self.assertIn("test-swapmod-canary-preflight: harness-swapmod-canary-preflight", makefile)

    def test_mock_services_do_not_expose_swapmod_canary_hardware_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text()
        forbidden = [
            "/swapmod/v1/send-gcode",
            "/swapmod/v1/raw-command",
            "/swapmod/v1/start-next-print",
            "/swapmod-canary/v1/upload",
            "/swapmod-canary/v1/start",
            "swapmod_canary_printer_commands",
            "swapmod_canary_queue_dispatches",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
