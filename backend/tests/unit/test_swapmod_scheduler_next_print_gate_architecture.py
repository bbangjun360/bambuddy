from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app/services/swapmod_scheduler_next_print_gate.py"
SCHEDULER = ROOT / "app/services/print_scheduler.py"
CONFIG = ROOT / "app/core/config.py"


class SwapmodSchedulerNextPrintGateArchitectureTest(unittest.TestCase):
    def test_config_flag_is_default_off(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")

        self.assertIn("farm_swapmod_scheduler_next_print_gate_enabled: bool = False", text)

    def test_service_exists_and_uses_print_log_identity(self) -> None:
        self.assertTrue(SERVICE.exists(), f"missing {SERVICE}")
        text = SERVICE.read_text(encoding="utf-8")

        self.assertIn("scheduler_print_run_key", text)
        self.assertIn("PrintLogEntry", text)
        self.assertIn("SwapmodStateMachineCycle", text)
        self.assertIn("evaluate_swapmod_next_print_gate", text)

    def test_service_does_not_import_dispatch_or_external_clients(self) -> None:
        text = SERVICE.read_text(encoding="utf-8") if SERVICE.exists() else ""
        forbidden = (
            "printer_manager",
            "bambu_mqtt",
            "bambu_ftp",
            "upload_file_async",
            "delete_file_async",
            "with_ftp_retry",
            "background_dispatch",
            "erp_draft_write",
            "obico_shadow",
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
                self.assertNotIn(token, text)

    def test_scheduler_checks_gate_before_upload_status_or_start(self) -> None:
        text = SCHEDULER.read_text(encoding="utf-8")

        gate_index = text.index("await evaluate_scheduler_next_print_gate(")
        upload_index = text.index("upload_file_async", gate_index)
        status_index = text.index('item.status = "printing"', gate_index)
        clear_index = text.index("set_awaiting_plate_clear", gate_index)
        start_index = text.index("printer_manager.start_print", gate_index)

        self.assertLess(gate_index, upload_index)
        self.assertLess(gate_index, status_index)
        self.assertLess(gate_index, clear_index)
        self.assertLess(gate_index, start_index)


if __name__ == "__main__":
    unittest.main()
