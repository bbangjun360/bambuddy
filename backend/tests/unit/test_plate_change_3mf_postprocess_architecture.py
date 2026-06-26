from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
IMPLEMENTATION_FILES = [
    ROOT / "app/api/routes/plate_change_3mf_postprocess.py",
    ROOT / "app/services/plate_change_3mf_postprocess.py",
    ROOT / "app/schemas/plate_change_3mf_postprocess.py",
]
CONFIG_FILE = ROOT / "app/core/config.py"


class PlateChange3mfPostprocessArchitectureTest(unittest.TestCase):
    def _combined_implementation_text(self) -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES if path.exists())

    def test_config_flags_are_default_disabled_dry_run_and_output_blocked(self) -> None:
        text = CONFIG_FILE.read_text(encoding="utf-8")

        self.assertIn("farm_plate_change_3mf_postprocess_enabled: bool = False", text)
        self.assertIn("farm_plate_change_3mf_postprocess_dry_run: bool = True", text)
        self.assertIn("farm_plate_change_3mf_allow_output_artifact: bool = False", text)
        self.assertIn("farm_plate_change_3mf_real_sample_root: str | None = None", text)
        self.assertIn("farm_plate_change_3mf_output_root: str | None = None", text)
        self.assertIn("farm_plate_change_3mf_allow_real_sample_output: bool = False", text)

    def test_wp064_implementation_imports_no_live_control_or_downstream_mutation_modules(self) -> None:
        combined = self._combined_implementation_text()
        forbidden = [
            "BambuMQTTClient",
            "from backend.app.services.bambu_mqtt",
            "from backend.app.services.print_scheduler",
            "from backend.app.services.background_dispatch",
            "from backend.app.models.print_queue",
            "from backend.app.models.bed_automation",
            "from backend.app.services.erp_draft_write",
            "from backend.app.services.obico_shadow",
            "background_dispatch.",
            "print_scheduler.",
            "BedAutomationCycle",
            "ErpDraftWriteRecord",
            "send_gcode",
            "stop_print",
            "pause_print",
            "resume_print",
            "download_file_async",
            "delete_file_async",
            "HTTPConnection",
            "HTTPSConnection",
            "httpx",
            "requests",
            "socket",
            "ftplib",
            "serial",
            "gpio",
            "usb",
        ]

        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_wp064_schema_and_route_do_not_expose_raw_gcode_or_execution_endpoint(self) -> None:
        schema_text = (ROOT / "app/schemas/plate_change_3mf_postprocess.py").read_text(encoding="utf-8")
        route_text = (ROOT / "app/api/routes/plate_change_3mf_postprocess.py").read_text(encoding="utf-8")
        main_text = (ROOT / "app/main.py").read_text(encoding="utf-8")

        self.assertIn('APIRouter(prefix="/plate-change-3mf"', route_text)
        self.assertIn('@router.post("/postprocess-plans"', route_text)
        self.assertIn('@router.get("/status"', route_text)
        self.assertIn('@router.get("/canary-status"', route_text)
        self.assertIn('@router.post("/canary-upload"', route_text)
        self.assertIn('@router.post("/canary-start"', route_text)
        self.assertIn("real_sample_output_review", schema_text)
        self.assertIn("output_dir", schema_text)
        self.assertIn("plate_change_3mf_postprocess", main_text)
        self.assertIn("app.include_router(plate_change_3mf_postprocess.router", main_text)

        forbidden_schema_tokens = ("raw_gcode", "gcode_text", "command_text", "raw_command", "body")
        for token in forbidden_schema_tokens:
            with self.subTest(token=token):
                self.assertNotIn(token, schema_text)

        forbidden_route_tokens = (
            "/queue",
            "/scheduler",
            "/dispatch",
            "/execute",
            "/live",
            "/live-run",
            "/send",
            "/raw",
            "raw-command",
            "send-gcode",
            "execute-gcode",
            "bulk-start",
            "auto-run",
            "/command",
        )
        for token in forbidden_route_tokens:
            with self.subTest(token=token):
                self.assertNotIn(token, route_text)

    def test_symbolic_inserted_block_contains_no_real_executable_gcode(self) -> None:
        service_text = (ROOT / "app/services/plate_change_3mf_postprocess.py").read_text(encoding="utf-8")

        self.assertIn("; BAMBUDDY_PLATE_CHANGE_BLOCK_START", service_text)
        self.assertIn("; symbolic_step: PLATE_CHANGE_REVIEW_REQUIRED", service_text)
        self.assertIn("; symbolic_step: NO_REAL_GCODE_IN_WP_064_B", service_text)
        self.assertIn("; BAMBUDDY_PLATE_CHANGE_BLOCK_END", service_text)
        block_match = re.search(
            r'PLATE_CHANGE_SYMBOLIC_BLOCK = \(\n(?P<block>.*?)\n\)',
            service_text,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(block_match)
        self.assertNotRegex(block_match.group("block"), re.compile(r"(?m)^\s*[GMT]\d+"))

    def test_no_raw_3mf_or_gcode_sample_files_are_tracked(self) -> None:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        forbidden = [
            path
            for path in result.stdout.splitlines()
            if path.lower().endswith((".3mf", ".gcode", ".gcode.3mf"))
        ]

        self.assertEqual(forbidden, [])


if __name__ == "__main__":
    unittest.main()
