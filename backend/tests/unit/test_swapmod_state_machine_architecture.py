from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_FILES = [
    ROOT / "app/api/routes/swapmod_state_machine.py",
    ROOT / "app/models/swapmod_state_machine.py",
    ROOT / "app/schemas/swapmod_state_machine.py",
    ROOT / "app/services/swapmod_state_machine.py",
]
CONFIG_FILE = ROOT / "app/core/config.py"


class SwapmodStateMachineArchitectureTest(unittest.TestCase):
    def _combined_implementation_text(self) -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES if path.exists())

    def test_config_flags_are_default_off_and_dry_run(self) -> None:
        text = CONFIG_FILE.read_text(encoding="utf-8")

        self.assertIn("farm_swapmod_state_machine_enabled: bool = False", text)
        self.assertIn("farm_swapmod_state_machine_dry_run: bool = True", text)
        self.assertIn("farm_swapmod_transport_enabled: bool = False", text)
        self.assertIn("farm_swapmod_transport_dry_run: bool = True", text)
        self.assertIn("farm_swapmod_allow_real_transport: bool = False", text)

    def test_implementation_files_exist_for_model_service_schema_and_route(self) -> None:
        for path in IMPLEMENTATION_FILES:
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"missing implementation file: {path}")

    def test_state_machine_imports_no_printer_command_queue_or_downstream_mutation_modules(self) -> None:
        combined = self._combined_implementation_text()
        forbidden = [
            "from backend.app.services.bambu_mqtt",
            "from backend.app.services.bambu_ftp",
            "from backend.app.services.printer_manager",
            "from backend.app.services.print_scheduler",
            "from backend.app.services.background_dispatch",
            "from backend.app.models.print_queue",
            "from backend.app.models.print_log",
            "from backend.app.models.bed_automation",
            "from backend.app.services.erp_draft_write",
            "from backend.app.services.obico_shadow",
            "PrintQueueItem",
            "PrintLogEntry",
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

    def test_route_exposes_only_status_cycle_and_event_paths(self) -> None:
        route_text = (ROOT / "app/api/routes/swapmod_state_machine.py").read_text(encoding="utf-8")
        main_text = (ROOT / "app/main.py").read_text(encoding="utf-8")

        self.assertIn('APIRouter(prefix="/swapmod-state-machine"', route_text)
        self.assertIn('@router.get("/status"', route_text)
        self.assertIn('@router.post("/cycles"', route_text)
        self.assertIn('@router.post("/operator-triggers"', route_text)
        self.assertIn('@router.post("/cycles/{cycle_key}/verifications"', route_text)
        self.assertIn('@router.post("/cycles/{cycle_key}/transport-steps"', route_text)
        self.assertIn('@router.post("/cycles/{cycle_key}/events"', route_text)
        self.assertIn("swapmod_state_machine", main_text)
        self.assertIn("app.include_router(swapmod_state_machine.router", main_text)
        forbidden_route_tokens = (
            "/queue",
            "/scheduler",
            "/dispatch",
            "/execute",
            "/live",
            "/send",
            "/raw",
            "/start-next-print",
        )
        for token in forbidden_route_tokens:
            with self.subTest(token=token):
                self.assertNotIn(token, route_text)

    def test_schemas_forbid_raw_command_fields(self) -> None:
        schema_text = (ROOT / "app/schemas/swapmod_state_machine.py").read_text(encoding="utf-8")

        self.assertIn('ConfigDict(extra="forbid")', schema_text)
        self.assertIn('Literal["START_SWAPMOD_PLATE_CHANGE"]', schema_text)
        self.assertIn('Literal["manual", "camera_mock"]', schema_text)
        self.assertIn('Literal["pass", "fail"]', schema_text)
        self.assertIn('Literal["RELEASE_PLATE", "LOAD_NEXT_PLATE"]', schema_text)
        self.assertIn('Literal["success", "failure", "timeout"]', schema_text)
        for forbidden in ("command_text", "raw_command", "raw_gcode", "gcode_line"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, schema_text)


if __name__ == "__main__":
    unittest.main()
