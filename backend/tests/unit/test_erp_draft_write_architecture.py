from __future__ import annotations

import re
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
WP040_IMPLEMENTATION_FILES = [
    BACKEND_ROOT / "app/api/routes/erp_draft_write.py",
    BACKEND_ROOT / "app/services/erp_draft_write.py",
    BACKEND_ROOT / "app/models/erp_draft_write.py",
    BACKEND_ROOT / "app/schemas/erp_draft_write.py",
]
CONFIG_FILE = BACKEND_ROOT / "app/core/config.py"
WP040_TEXT_FILES = [
    *WP040_IMPLEMENTATION_FILES,
    REPO_ROOT / "harness/tests/test_erp_draft_write_mock.py",
    BACKEND_ROOT / "tests/unit/services/test_erp_draft_write.py",
    BACKEND_ROOT / "tests/integration/test_erp_draft_write_api.py",
]


class ErpDraftWriteArchitectureTest(unittest.TestCase):
    def _combined_implementation_text(self) -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in WP040_IMPLEMENTATION_FILES if path.exists())

    def test_feature_flag_is_default_off(self) -> None:
        text = CONFIG_FILE.read_text(encoding="utf-8")
        self.assertIn("farm_erp_draft_posting_enabled: bool = False", text)

    def test_module_has_no_printer_queue_bed_obico_or_scheduler_imports(self) -> None:
        combined = self._combined_implementation_text()
        forbidden = [
            "bambu_mqtt",
            "bambu_ftp",
            "printer_manager",
            "print_scheduler",
            "PrintQueueItem",
            "PrintLogEntry",
            "BedAutomationCycle",
            "obico",
            "start_print",
            "send_gcode",
            "gcode",
        ]

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_module_has_no_submit_inventory_or_accounting_behavior(self) -> None:
        combined = self._combined_implementation_text()
        forbidden = [
            "Stock Entry",
            "Sales Invoice",
            "GL Entry",
            "Payment Entry",
            "/submit",
            "docstatus = 1",
            'docstatus": 1',
        ]

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_wp040_fixtures_contain_no_real_erp_or_printer_data(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in WP040_TEXT_FILES if path.exists())
        forbidden_literals = [
            "serial_number",
            "erp.farm.lan",
            "erpnext.local",
            "customer@example.com",
            "real-token",
            "api_secret",
        ]
        ip_pattern = re.compile(r"\b(?:10|172\.(?:1[6-9]|2\d|3[0-1])|192\.168)\.\d{1,3}\.\d{1,3}\b")

        for token in forbidden_literals:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)
        self.assertIsNone(ip_pattern.search(combined))


if __name__ == "__main__":
    unittest.main()
