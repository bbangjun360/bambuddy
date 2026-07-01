from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app/services/swapmod_scheduler_handoff_diagnostics.py"
ROUTE = ROOT / "app/api/routes/swapmod_state_machine.py"
CONFIG = ROOT / "app/core/config.py"


class SwapmodSchedulerHandoffDiagnosticsArchitectureTest(unittest.TestCase):
    def test_existing_scheduler_gate_flags_remain_default_off(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")

        self.assertIn("farm_swapmod_scheduler_next_print_gate_enabled: bool = False", text)
        self.assertIn("farm_swapmod_queue_readiness_binding_enabled: bool = False", text)
        self.assertIn("farm_swapmod_scheduler_queue_readiness_binding_enabled: bool = False", text)
        self.assertIn("farm_bed_automation_enabled: bool = False", text)

    def test_service_exists_and_reuses_existing_scheduler_gates(self) -> None:
        self.assertTrue(SERVICE.exists(), f"missing {SERVICE}")
        text = SERVICE.read_text(encoding="utf-8")

        self.assertIn("evaluate_scheduler_next_print_gate", text)
        self.assertIn("evaluate_scheduler_queue_readiness_binding_gate", text)
        self.assertIn("scheduler_handoff_source_print_run_mismatch", text)
        self.assertIn("scheduler_handoff_source_cycle_mismatch", text)

    def test_service_does_not_import_scheduler_dispatch_or_external_clients(self) -> None:
        text = SERVICE.read_text(encoding="utf-8") if SERVICE.exists() else ""
        forbidden = (
            "print_scheduler",
            "PrintScheduler",
            "_start_print",
            "consume_scheduler_queue_readiness_binding",
            "printer_manager",
            "bambu_mqtt",
            "bambu_ftp",
            "upload_file_async",
            "delete_file_async",
            "with_ftp_retry",
            "cache_3mf_download",
            "spawn_background_task",
            "background_dispatch",
            "erp_draft_write",
            "obico_shadow",
            "send_gcode",
            "db.commit",
            "db.flush",
            "item.status",
            "started_at",
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


    def test_api_route_is_read_only_and_reuses_diagnostics_service(self) -> None:
        text = ROUTE.read_text(encoding="utf-8")

        self.assertIn("evaluate_swapmod_scheduler_handoff_diagnostics", text)
        self.assertIn("@router.get(\"/scheduler-handoff-diagnostics\")", text)
        handler = text.split("async def get_swapmod_scheduler_handoff_diagnostics(", 1)[1].split("\n\n@router", 1)[0]
        self.assertIn("Permission.PRINTERS_READ", handler)
        self.assertNotIn("Permission.PRINTERS_CONTROL", handler)
        self.assertNotIn("_require_enabled()", handler)
        self.assertNotIn("_require_next_print_gate_enabled()", handler)
        self.assertNotIn("_require_queue_readiness_binding_enabled()", handler)
        forbidden = (
            "_start_print",
            "consume_scheduler_queue_readiness_binding",
            "printer_manager",
            "bambu_mqtt",
            "bambu_ftp",
            "upload_file_async",
            "delete_file_async",
            "with_ftp_retry",
            "cache_3mf_download",
            "spawn_background_task",
            "background_dispatch",
            "erp_draft_write",
            "obico_shadow",
            "send_gcode",
            "db.commit",
            "db.flush",
            "item.status",
            "started_at",
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
                self.assertNotIn(token, handler)


    def test_status_api_route_is_read_only_and_does_not_open_handler_db_session(self) -> None:
        text = ROUTE.read_text(encoding="utf-8")

        self.assertIn("@router.get(\"/scheduler-handoff-diagnostics/status\")", text)
        handler = text.split("async def get_swapmod_scheduler_handoff_diagnostics_status", 1)[1].split(
            "\n\n@router", 1
        )[0]
        self.assertIn("Permission.PRINTERS_READ", handler)
        self.assertNotIn("Permission.PRINTERS_CONTROL", handler)
        self.assertNotIn("Depends(get_db)", handler)
        self.assertNotIn("AsyncSession", handler)
        self.assertNotIn("evaluate_swapmod_scheduler_handoff_diagnostics", handler)
        self.assertIn("required_query_parameters", handler)
        forbidden = (
            "_start_print",
            "consume_scheduler_queue_readiness_binding",
            "printer_manager",
            "bambu_mqtt",
            "bambu_ftp",
            "send_gcode",
            "db.commit",
            "db.flush",
            "item.status",
            "started_at",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, handler)


if __name__ == "__main__":
    unittest.main()
