from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_FILES = [
    ROOT / "app/api/routes/plate_change_command.py",
    ROOT / "app/services/plate_change_command.py",
    ROOT / "app/schemas/plate_change_command.py",
]
CONFIG_FILE = ROOT / "app/core/config.py"


class PlateChangeCommandArchitectureTest(unittest.TestCase):
    def _combined_implementation_text(self) -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES if path.exists())

    def test_config_flags_are_default_disabled_dry_run_human_gated_single_printer_and_no_real_commands(self) -> None:
        text = CONFIG_FILE.read_text(encoding="utf-8")

        self.assertIn("farm_plate_change_command_enabled: bool = False", text)
        self.assertIn("farm_plate_change_command_dry_run: bool = True", text)
        self.assertIn("farm_plate_change_human_approval_required: bool = True", text)
        self.assertIn("farm_plate_change_single_printer_only: bool = True", text)
        self.assertIn("farm_plate_change_allow_real_commands: bool = False", text)

    def test_wp063_implementation_imports_no_printer_command_queue_or_downstream_mutation_modules(self) -> None:
        combined = self._combined_implementation_text()
        forbidden = [
            "BambuMQTTClient",
            "from backend.app.services.bambu_mqtt",
            "from backend.app.services.bambu_ftp",
            "from backend.app.services.printer_manager",
            "from backend.app.services.print_scheduler",
            "from backend.app.services.background_dispatch",
            "from backend.app.models.print_queue",
            "from backend.app.models.bed_automation",
            "from backend.app.services.erp_draft_write",
            "from backend.app.services.obico_shadow",
            "send_gcode",
            "start_print",
            "stop_print",
            "pause_print",
            "resume_print",
            "upload_file_async",
            "download_file_async",
            "delete_file_async",
            "HTTPConnection",
            "HTTPSConnection",
            "httpx",
            "requests",
            "socket",
            "serial",
            "gpio",
            "usb",
        ]

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_wp063_route_exposes_only_dry_run_and_status_paths(self) -> None:
        route_text = (ROOT / "app/api/routes/plate_change_command.py").read_text(encoding="utf-8")
        main_text = (ROOT / "app/main.py").read_text(encoding="utf-8")

        self.assertIn('APIRouter(prefix="/plate-change"', route_text)
        self.assertIn('@router.post("/dry-run-commands"', route_text)
        self.assertIn('@router.get("/status"', route_text)
        self.assertIn("plate_change_command", main_text)
        self.assertIn("app.include_router(plate_change_command.router", main_text)
        forbidden_route_tokens = ("/queue", "/scheduler", "/dispatch")
        for token in forbidden_route_tokens:
            with self.subTest(token=token):
                self.assertNotIn(token, route_text)


if __name__ == "__main__":
    unittest.main()
