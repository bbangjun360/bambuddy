from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PlateChangeCommandHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_plate_change_command_targets(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-plate-change-command:", makefile)
        self.assertIn("test-plate-change-command: harness-plate-change-command", makefile)
        self.assertIn("harness-plate-change-transport:", makefile)
        self.assertIn("test-plate-change-transport: harness-plate-change-transport", makefile)

    def test_mock_services_do_not_expose_external_plate_change_command_server(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text(encoding="utf-8")

        forbidden = (
            "/plate-change/v1/commands",
            "/plate-change/v1/command",
            "/plate-change/v1/dispatch",
            "plate_change_command_sends",
            "plate_change_transport_sends",
            "/plate-change/v1/transport",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
