from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class Swapmod3mfDryRunHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_swapmod_dry_run_targets(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("harness-swapmod-3mf-dry-run:", makefile)
        self.assertIn("test-swapmod-3mf-dry-run: harness-swapmod-3mf-dry-run", makefile)

    def test_mock_services_do_not_expose_swapmod_hardware_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text()
        forbidden = [
            "/swapmod/v1/send-gcode",
            "/swapmod/v1/raw-command",
            "/swapmod/v1/start-next-print",
            "swapmod_printer_commands",
            "swapmod_queue_dispatches",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
