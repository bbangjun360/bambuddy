from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app/services/swapmod_next_print_gate.py"
ROUTE = ROOT / "app/api/routes/swapmod_state_machine.py"
SCHEMA = ROOT / "app/schemas/swapmod_state_machine.py"
CONFIG = ROOT / "app/core/config.py"


class SwapmodNextPrintGateArchitectureTest(unittest.TestCase):
    def test_config_flag_is_default_off(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")

        self.assertIn("farm_swapmod_next_print_gate_enabled: bool = False", text)

    def test_route_is_evaluate_only_under_swapmod_state_machine(self) -> None:
        self.assertTrue(SERVICE.exists(), f"missing {SERVICE}")
        route_text = ROUTE.read_text(encoding="utf-8")

        self.assertIn('@router.get("/next-print-gates/status"', route_text)
        self.assertIn('@router.post("/cycles/{cycle_key}/next-print-gates"', route_text)
        self.assertIn("evaluate_swapmod_next_print_gate", route_text)

    def test_schema_does_not_accept_raw_command_or_dispatch_fields(self) -> None:
        text = SCHEMA.read_text(encoding="utf-8")

        self.assertIn("class SwapmodNextPrintGateRequest", text)
        self.assertIn('ConfigDict(extra="forbid")', text)
        for forbidden in (
            "raw_gcode",
            "gcode",
            "command_text",
            "raw_command",
            "sequence_path",
            "file_path",
            "queue_item_id",
            "dispatch",
            "start_print",
            "scheduler",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_gate_does_not_import_printer_command_queue_or_downstream_clients(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in (SERVICE, ROUTE, SCHEMA) if path.exists())
        forbidden = (
            "printer_manager",
            "bambu_mqtt",
            "bambu_ftp",
            "print_scheduler",
            "background_dispatch",
            "PrintQueueItem",
            "PrintLogEntry",
            "ErpDraftWriteRecord",
            "erp_draft_write",
            "obico_shadow",
            "upload_file_async",
            "start_print",
            "send_gcode",
            "HTTPConnection",
            "HTTPSConnection",
            "httpx",
            "requests",
            "socket",
            "serial",
            "gpio",
            "usb",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
