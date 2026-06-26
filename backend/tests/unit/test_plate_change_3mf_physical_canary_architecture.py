from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_FILES = [
    ROOT / "app/api/routes/plate_change_3mf_postprocess.py",
    ROOT / "app/services/plate_change_3mf_postprocess.py",
    ROOT / "app/schemas/plate_change_3mf_postprocess.py",
]
CONFIG_FILE = ROOT / "app/core/config.py"
MAKEFILE = ROOT.parent / "Makefile"


class PlateChange3mfPhysicalCanaryArchitectureTest(unittest.TestCase):
    def _combined_implementation_text(self) -> str:
        return "\n".join(path.read_text(encoding="utf-8") for path in IMPLEMENTATION_FILES if path.exists())

    def test_physical_canary_config_flags_are_default_blocked_and_single_start(self) -> None:
        text = CONFIG_FILE.read_text(encoding="utf-8")

        self.assertIn("farm_plate_change_3mf_physical_canary_enabled: bool = False", text)
        self.assertIn("farm_plate_change_3mf_allow_printer_upload: bool = False", text)
        self.assertIn("farm_plate_change_3mf_allow_print_start: bool = False", text)
        self.assertIn("farm_plate_change_3mf_canary_single_printer_only: bool = True", text)
        self.assertIn("farm_plate_change_3mf_canary_require_human_confirmation: bool = True", text)
        self.assertIn("farm_plate_change_3mf_canary_disable_auto_retry: bool = True", text)
        self.assertIn("farm_plate_change_3mf_canary_max_starts: int = 1", text)

    def test_only_allowed_canary_endpoint_names_are_exposed(self) -> None:
        route_text = (ROOT / "app/api/routes/plate_change_3mf_postprocess.py").read_text(encoding="utf-8")

        self.assertIn('@router.get("/canary-status"', route_text)
        self.assertIn('@router.post("/canary-upload"', route_text)
        self.assertIn('@router.post("/canary-start"', route_text)

        forbidden_endpoint_tokens = (
            "raw-command",
            "send-gcode",
            "execute-gcode",
            "bulk-start",
            "/schedule",
            "/queue",
            "/auto-run",
        )
        for token in forbidden_endpoint_tokens:
            with self.subTest(token=token):
                self.assertNotIn(token, route_text)

    def test_schema_accepts_only_reviewed_artifact_confirmation_and_checklist_fields(self) -> None:
        schema_text = (ROOT / "app/schemas/plate_change_3mf_postprocess.py").read_text(encoding="utf-8")

        self.assertIn("PlateChange3mfCanaryUploadRequest", schema_text)
        self.assertIn("PlateChange3mfCanaryStartRequest", schema_text)
        self.assertIn("PlateChange3mfCanaryStartChecklist", schema_text)
        self.assertIn("target_printer_ids", schema_text)
        self.assertIn("artifact_sha256", schema_text)
        self.assertIn("operator_confirmation_phrase", schema_text)
        for checklist_field in (
            "operator_present",
            "printer_visible",
            "emergency_stop_ready",
            "power_cutoff_ready",
            "bed_clear_confirmed",
            "correct_plate_confirmed",
            "no_other_job_running",
            "fire_risk_area_clear",
        ):
            with self.subTest(checklist_field=checklist_field):
                self.assertIn(checklist_field, schema_text)

        forbidden_schema_tokens = ("raw_gcode", "gcode_text", "command_text", "raw_command", "body")
        for token in forbidden_schema_tokens:
            with self.subTest(token=token):
                self.assertNotIn(token, schema_text)

    def test_implementation_uses_no_queue_scheduler_retry_or_raw_gcode_path(self) -> None:
        combined = self._combined_implementation_text()

        forbidden_tokens = (
            "from backend.app.services.print_scheduler",
            "from backend.app.services.background_dispatch",
            "from backend.app.models.print_queue",
            "DispatchEnqueueRejected",
            "background_dispatch",
            "print_scheduler",
            "send_gcode",
            "execute_gcode",
            "raw_command",
            "bulk_start",
            "auto_run",
            "retry_delay",
            "with_ftp_retry",
            "max_retries",
        )
        for token in forbidden_tokens:
            with self.subTest(token=token):
                self.assertNotIn(token, combined)

    def test_makefile_exposes_focused_physical_canary_targets(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")

        self.assertIn("harness-plate-change-3mf-physical-canary:", text)
        self.assertIn("test-plate-change-3mf-physical-canary: harness-plate-change-3mf-physical-canary", text)
        self.assertIn("backend.tests.unit.services.test_plate_change_3mf_physical_canary", text)
        self.assertIn("backend.tests.integration.test_plate_change_3mf_physical_canary_api", text)


if __name__ == "__main__":
    unittest.main()
