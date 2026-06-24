from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHADOW_FILES = [
    ROOT / "app/services/obico_shadow.py",
    ROOT / "app/api/routes/obico_shadow.py",
]


class ObicoShadowArchitectureTest(unittest.TestCase):
    def test_shadow_mode_files_exist(self) -> None:
        missing = [str(path.relative_to(ROOT)) for path in SHADOW_FILES if not path.exists()]
        self.assertEqual(missing, [])

    def test_shadow_mode_has_no_control_plane_references(self) -> None:
        forbidden = [
            "obico_actions",
            "execute_action",
            "printer_manager",
            "bambu_mqtt",
            "bambu_ftp",
            "print_scheduler",
            "background_dispatch",
            "PrintQueueItem",
            "PrintLogEntry",
            "gcode",
            "Stock Entry",
            "erp_readonly",
            "smart_plug",
            "pause_print",
            "start_print",
            "cancel_print",
            "printflow",
            "bed_automation",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in SHADOW_FILES if path.exists())

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
