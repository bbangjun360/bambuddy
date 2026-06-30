from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app/services/swapmod_queue_readiness_binding.py"
MODEL = ROOT / "app/models/swapmod_queue_readiness_binding.py"
ROUTE = ROOT / "app/api/routes/swapmod_state_machine.py"
SCHEMA = ROOT / "app/schemas/swapmod_state_machine.py"
CONFIG = ROOT / "app/core/config.py"


class SwapmodQueueReadinessBindingArchitectureTest(unittest.TestCase):
    def test_config_flag_is_default_off(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")

        self.assertIn("farm_swapmod_queue_readiness_binding_enabled: bool = False", text)

    def test_binding_model_is_durable_and_uniquely_tied_to_queue_item(self) -> None:
        self.assertTrue(MODEL.exists(), f"missing {MODEL}")
        text = MODEL.read_text(encoding="utf-8")

        self.assertIn('__tablename__ = "swapmod_queue_readiness_bindings"', text)
        self.assertIn('UniqueConstraint("binding_key"', text)
        self.assertIn('UniqueConstraint("queue_item_id"', text)
        self.assertIn('UniqueConstraint("bed_cycle_key"', text)
        self.assertIn("queue_fingerprint", text)
        self.assertIn("consumed_at", text)

    def test_route_records_binding_under_swapmod_state_machine_without_scheduler_start(self) -> None:
        self.assertTrue(SERVICE.exists(), f"missing {SERVICE}")
        route_text = ROUTE.read_text(encoding="utf-8")

        self.assertIn('@router.get("/queue-readiness-bindings/status"', route_text)
        self.assertIn('@router.post("/cycles/{cycle_key}/queue-readiness-bindings"', route_text)
        self.assertIn("bind_swapmod_queue_readiness", route_text)

    def test_schema_rejects_raw_command_dispatch_and_scheduler_fields(self) -> None:
        text = SCHEMA.read_text(encoding="utf-8")

        self.assertIn("class SwapmodQueueReadinessBindingRequest", text)
        self.assertIn('ConfigDict(extra="forbid")', text)
        for forbidden in (
            "raw_gcode",
            "gcode",
            "command_text",
            "raw_command",
            "sequence_path",
            "file_path",
            "dispatch",
            "start_print",
            "scheduler",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_binding_does_not_import_printer_command_scheduler_or_downstream_clients(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in (SERVICE, ROUTE, SCHEMA) if path.exists())
        forbidden = (
            "printer_manager",
            "bambu_mqtt",
            "bambu_ftp",
            "print_scheduler",
            "background_dispatch",
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
