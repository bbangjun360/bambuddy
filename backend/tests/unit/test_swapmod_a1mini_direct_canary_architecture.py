from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app/services/swapmod_a1mini_direct_canary.py"
ROUTE = ROOT / "app/api/routes/swapmod_a1mini_direct_canary.py"
SCHEMA = ROOT / "app/schemas/swapmod_a1mini_direct_canary.py"
CONFIG = ROOT / "app/core/config.py"


class SwapmodA1MiniDirectCanaryArchitectureTest(unittest.TestCase):
    def test_config_flags_are_default_off(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")

        self.assertIn("farm_swapmod_a1mini_direct_canary_enabled: bool = False", text)
        self.assertIn("farm_swapmod_a1mini_direct_canary_allow_real_commands: bool = False", text)
        self.assertIn("farm_swapmod_a1mini_direct_canary_require_human_confirmation: bool = True", text)

    def test_files_exist_and_route_is_explicit(self) -> None:
        for path in (SERVICE, ROUTE, SCHEMA):
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"missing {path}")
        route_text = ROUTE.read_text(encoding="utf-8")
        self.assertIn('APIRouter(prefix="/swapmod-a1-mini-direct-canary"', route_text)
        self.assertIn('@router.get("/status"', route_text)
        self.assertIn('@router.post("/cycles/{cycle_key}/transport-steps"', route_text)

    def test_schema_does_not_accept_raw_command_or_path_fields(self) -> None:
        text = SCHEMA.read_text(encoding="utf-8")

        self.assertIn('ConfigDict(extra="forbid")', text)
        self.assertIn('Literal["RELEASE_PLATE", "LOAD_NEXT_PLATE"]', text)
        for forbidden in (
            "raw_gcode",
            "gcode",
            "gcode_line",
            "command_text",
            "raw_command",
            "sequence_path",
            "file_path",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_direct_canary_does_not_import_queue_scheduler_or_downstream_mutations(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in (SERVICE, ROUTE, SCHEMA) if path.exists())
        forbidden = (
            "print_scheduler",
            "background_dispatch",
            "PrintQueueItem",
            "PrintLogEntry",
            "BedAutomationCycle",
            "erp_draft_write",
            "obico_shadow",
            "upload_file_async",
            "start_print",
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
