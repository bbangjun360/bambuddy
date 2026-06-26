from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_FILES = [
    ROOT / "app/api/routes/printflow_canary.py",
    ROOT / "app/services/printflow_canary.py",
    ROOT / "app/schemas/printflow_canary.py",
]
CONFIG_FILE = ROOT / "app/core/config.py"


class PrintFlowCanaryArchitectureTest(unittest.TestCase):
    def _combined_implementation_text(self) -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES if path.exists())

    def test_config_flags_are_default_off_dry_run_and_human_gated(self) -> None:
        text = CONFIG_FILE.read_text(encoding="utf-8")

        self.assertIn("farm_printflow_canary_readiness_enabled: bool = False", text)
        self.assertIn("farm_printflow_real_adapter_enabled: bool = False", text)
        self.assertIn("farm_printflow_canary_dry_run: bool = True", text)
        self.assertIn("farm_printflow_canary_human_approval_required: bool = True", text)
        self.assertIn("farm_printflow_canary_single_printer_only: bool = True", text)
        self.assertIn("farm_printflow_base_url: str | None = None", text)
        self.assertIn("farm_printflow_api_token: str | None = None", text)

    def test_external_server_adapter_is_pending_redesign_not_live_http_client(self) -> None:
        combined = self._combined_implementation_text()

        self.assertIn("external_adapter_pending_redesign", combined)
        forbidden = [
            "import http.client",
            "HTTPConnection",
            "HTTPSConnection",
            "/printflow/v1/canary/runs",
            "_split_printflow_base_url",
        ]

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_wp060_files_have_no_real_control_plane_or_external_client_imports(self) -> None:
        combined = self._combined_implementation_text()
        forbidden = [
            "BambuMQTTClient",
            "bambu_mqtt",
            "bambu_ftp",
            "printer_manager",
            "print_scheduler",
            "background_dispatch",
            "PrintQueueItem",
            "PrintLogEntry",
            "BedAutomationCycle",
            "ErpDraftWriteClient",
            "obico_actions",
            "start_print",
            "stop_print",
            "pause_print",
            "resume_print",
            "send_gcode",
            "gcode",
            "httpx",
            "requests",
            "urllib",
            "socket",
            "serial",
            "gpio",
            "usb",
            "mqtt",
            "ftps",
        ]

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_wp060_files_do_not_submit_or_post_erp_or_obico_changes(self) -> None:
        combined = self._combined_implementation_text()
        forbidden = [
            "Stock Entry",
            "Sales Invoice",
            "GL Entry",
            "Payment Entry",
            "/submit",
            "docstatus = 1",
            'docstatus": 1',
            "execute_action",
        ]

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
