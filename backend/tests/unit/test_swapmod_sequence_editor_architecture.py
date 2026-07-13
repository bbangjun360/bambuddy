from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "app/core/config.py"
HARNESS_COMPOSE = ROOT.parent / "harness/docker-compose.harness.yml"
ROUTE = ROOT / "app/api/routes/swapmod_a1mini_direct_canary.py"
SCHEMA = ROOT / "app/schemas/swapmod_sequence_editor.py"
SERVICE = ROOT / "app/services/swapmod_sequence_editor.py"


class SwapmodSequenceEditorArchitectureTest(unittest.TestCase):
    def test_editor_flag_is_default_off(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")
        self.assertIn("farm_swapmod_a1mini_sequence_editor_enabled: bool = False", text)

    def test_harness_passes_editor_flag_default_off(self) -> None:
        text = HARNESS_COMPOSE.read_text(encoding="utf-8")
        self.assertIn(
            "FARM_SWAPMOD_A1MINI_SEQUENCE_EDITOR_ENABLED: ${FARM_SWAPMOD_A1MINI_SEQUENCE_EDITOR_ENABLED:-false}",
            text,
        )

    def test_write_route_requires_settings_admin_and_printer_control(self) -> None:
        text = ROUTE.read_text(encoding="utf-8")
        self.assertIn('@router.post("/sequence-versions", status_code=201)', text)
        self.assertIn(
            "RequirePermissionIfAuthEnabled(Permission.SETTINGS_UPDATE, Permission.PRINTERS_CONTROL)",
            text,
        )

    def test_request_schema_has_no_raw_content_path_or_activation_fields(self) -> None:
        tree = ast.parse(SCHEMA.read_text(encoding="utf-8"))
        request_fields: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "SwapmodSequenceCandidateRequest":
                request_fields = {
                    child.target.id
                    for child in node.body
                    if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name)
                }
        self.assertEqual(request_fields, {"step", "base_sha256", "actions"})

    def test_editor_service_cannot_send_or_activate_a_sequence(self) -> None:
        text = SERVICE.read_text(encoding="utf-8")
        for forbidden in (
            "printer_manager",
            "send_gcode",
            "start_print",
            "upload_file",
            "mqtt",
            "ftps",
            "requests",
            "httpx",
            "socket",
            "serial",
            "gpio",
            "usb",
            "activate_candidate",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text.lower())

    def test_route_has_no_candidate_activation_endpoint(self) -> None:
        text = ROUTE.read_text(encoding="utf-8").lower()
        self.assertNotIn("/sequence-versions/{version_id}/activate", text)


if __name__ == "__main__":
    unittest.main()
