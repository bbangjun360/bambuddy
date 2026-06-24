from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ERP_FILES = [
    ROOT / "app/api/routes/erp_readonly.py",
    ROOT / "app/services/erp_readonly.py",
    ROOT / "app/models/erp_readonly.py",
    ROOT / "app/schemas/erp_readonly.py",
]


class ErpReadOnlyArchitectureTest(unittest.TestCase):
    def test_erp_readonly_module_has_no_printer_or_queue_command_imports(self) -> None:
        forbidden = [
            "bambu_mqtt",
            "bambu_ftp",
            "printer_manager",
            "print_scheduler",
            "PrintQueueItem",
            "PrintLogEntry",
            "gcode",
            "Stock Entry",
        ]

        combined = "\n".join(path.read_text(encoding="utf-8") for path in ERP_FILES if path.exists())

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
