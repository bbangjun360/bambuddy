from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app/services/swapmod_canary_preflight.py"
ROUTE = ROOT / "app/api/routes/swapmod_canary_preflight.py"
SCHEMA = ROOT / "app/schemas/swapmod_canary_preflight.py"


class SwapmodCanaryPreflightArchitectureTest(unittest.TestCase):
    def test_boundary_does_not_import_live_printer_or_dispatch_modules(self) -> None:
        combined = "\n".join(path.read_text() for path in (SERVICE, ROUTE, SCHEMA))
        forbidden_imports = [
            "backend.app.services.printer_manager",
            "backend.app.services.bambu_mqtt",
            "backend.app.services.bambu_ftp",
            "backend.app.services.print_scheduler",
            "backend.app.api.routes.print_queue",
            "backend.app.services.erp",
            "backend.app.services.obico",
            "backend.app.models.bed_automation",
        ]
        for needle in forbidden_imports:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, combined)

    def test_boundary_has_no_raw_or_live_execution_endpoint_names(self) -> None:
        combined = "\n".join(path.read_text() for path in (ROUTE, SCHEMA))
        forbidden = [
            "raw-command",
            "send-gcode",
            "execute-gcode",
            "start-next-print",
            "auto-run",
        ]
        for needle in forbidden:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, combined)

    def test_service_never_calls_live_printer_methods(self) -> None:
        text = SERVICE.read_text()
        forbidden_calls = [
            ".send_gcode(",
            ".start_print(",
            "upload_file_async",
            "delete_file_async",
            "clear_plate",
            "PrintQueueItem(",
            "BedAutomationCycle(",
        ]
        for needle in forbidden_calls:
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
