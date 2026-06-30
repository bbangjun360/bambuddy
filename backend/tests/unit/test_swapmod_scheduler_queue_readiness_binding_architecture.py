from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app/services/swapmod_scheduler_queue_readiness_binding.py"
SCHEDULER = ROOT / "app/services/print_scheduler.py"
CONFIG = ROOT / "app/core/config.py"


class SwapmodSchedulerQueueReadinessBindingArchitectureTest(unittest.TestCase):
    def test_config_flag_is_default_off(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")

        self.assertIn("farm_swapmod_scheduler_queue_readiness_binding_enabled: bool = False", text)

    def test_service_exists_and_reuses_queue_binding_replay(self) -> None:
        self.assertTrue(SERVICE.exists(), f"missing {SERVICE}")
        text = SERVICE.read_text(encoding="utf-8")

        self.assertIn("SwapmodQueueReadinessBinding", text)
        self.assertIn("SwapmodStateMachineCycle", text)
        self.assertIn("evaluate_existing_swapmod_queue_readiness_binding", text)

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

    def test_scheduler_checks_binding_gate_before_upload_status_or_start(self) -> None:
        text = SCHEDULER.read_text(encoding="utf-8")

        gate_index = text.index("await evaluate_scheduler_queue_readiness_binding_gate(")
        upload_index = text.index("upload_file_async", gate_index)
        status_index = text.index('item.status = "printing"', gate_index)
        clear_index = text.index("set_awaiting_plate_clear", gate_index)
        start_index = text.index("printer_manager.start_print", gate_index)

        self.assertLess(gate_index, upload_index)
        self.assertLess(gate_index, status_index)
        self.assertLess(gate_index, clear_index)
        self.assertLess(gate_index, start_index)

    def test_scheduler_consumes_binding_only_after_start_print_accepts_command(self) -> None:
        text = SCHEDULER.read_text(encoding="utf-8")

        start_index = text.index("started = printer_manager.start_print(")
        started_branch_index = text.index("if started:", start_index)
        consume_index = text.index("await consume_scheduler_queue_readiness_binding(", started_branch_index)

        self.assertLess(start_index, consume_index)
        self.assertLess(started_branch_index, consume_index)


if __name__ == "__main__":
    unittest.main()
