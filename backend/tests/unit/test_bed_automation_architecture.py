from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WP050_IMPLEMENTATION_FILES = [
    ROOT / "app/models/bed_automation.py",
    ROOT / "app/services/bed_automation.py",
]
CONFIG_FILE = ROOT / "app/core/config.py"


class BedAutomationArchitectureTest(unittest.TestCase):
    def _combined_implementation_text(self) -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in WP050_IMPLEMENTATION_FILES if path.exists())

    def test_feature_flags_are_default_off_and_dry_run(self) -> None:
        text = CONFIG_FILE.read_text(encoding="utf-8")

        self.assertIn("farm_bed_automation_enabled: bool = False", text)
        self.assertIn("farm_bed_automation_dry_run: bool = True", text)

    def test_bed_automation_module_has_no_printer_queue_or_log_side_effect_imports(self) -> None:
        combined = self._combined_implementation_text()
        forbidden = [
            "bambu_mqtt",
            "bambu_ftp",
            "printer_manager",
            "print_scheduler",
            "PrintQueueItem",
            "PrintLogEntry",
            "start_print",
            "send_gcode",
            "gcode",
        ]

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_bed_automation_module_has_no_real_hardware_or_network_client(self) -> None:
        combined = self._combined_implementation_text().lower()
        forbidden = [
            "httpx",
            "requests",
            "urllib",
            "socket",
            "serial",
            "gpio",
            "bluetooth",
            "ble_client",
            "bleak",
            "usb",
            "ftps",
            "mqtt",
        ]

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
