from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / "docs/runbooks/WP103_PHYSICAL_ACCEPTANCE_CANARY.md"
EVIDENCE = ROOT / "docs/releases/WP103_PHYSICAL_ACCEPTANCE_EVIDENCE.md"
WORKPACK = ROOT / "workpacks/exec/WP-103_PHYSICAL_ACCEPTANCE_CANARY.md"


class PhysicalAcceptanceCanaryHarnessTest(unittest.TestCase):
    def test_makefile_exposes_physical_acceptance_canary_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-physical-acceptance-canary:", makefile)
        self.assertIn(
            "test-physical-acceptance-canary: harness-physical-acceptance-canary",
            makefile,
        )
        target_body = makefile.split("test-physical-acceptance-canary:", 1)[1].split("\n\n", 1)[0]
        self.assertIn("check_workpack.py workpacks/exec/WP-103_PHYSICAL_ACCEPTANCE_CANARY.md", target_body)

    def test_runbook_covers_human_gated_physical_acceptance(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")

        required_tokens = [
            "# WP-103 Physical Acceptance Canary",
            "farm-v0.1.0-acceptance",
            "9190b2fc6ac1e111234ad73d8d73e2a487d81be5",
            "A1 Mini",
            "Bambuddy remains the sole authority",
            "No physical printer action is executed by CI",
            "Simulation success is not physical safety evidence",
            "Never automatically resume an uncertain physical bed action after restart",
            "CONFIRM_WP103_PHYSICAL_ACCEPTANCE_CANARY",
            "CONFIRM_A1_MINI_DIRECT_PLATE_CHANGE",
            "operator_present",
            "printer_visible",
            "emergency_stop_ready",
            "power_cutoff_ready",
            "bed_area_clear",
            "plate_stack_ready",
            "dry_run_gate_reviewed",
            "READY_FOR_NEXT_PRINT",
            "MANUAL_REVIEW",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false",
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_runbook_does_not_predeclare_post_action_verification(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        checklist = text.split("## Human Checklist", 1)[1].split("## Confirmation Phrases", 1)[0]

        self.assertNotIn("release_verified=true", checklist)
        self.assertNotIn("loaded_verified=true", checklist)
        self.assertIn("release_verified=true", text)
        self.assertIn("loaded_verified=true", text)

    def test_evidence_template_captures_release_and_physical_results(self) -> None:
        text = EVIDENCE.read_text(encoding="utf-8")

        required_tokens = [
            "# WP-103 Physical Acceptance Evidence",
            "Release Gate Evidence",
            "farm-v0.1.0-acceptance",
            "28562025959",
            "28562152131",
            "Physical Canary Record",
            "No physical execution has been recorded by WP-103",
            "canary_key",
            "printer_id_redacted",
            "a1_mini_confirmed",
            "swapmod_hardware_installed",
            "no_other_job_running",
            "release_sequence_sha256",
            "load_sequence_sha256",
            "final_state",
            "rollback_confirmed",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false",
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_workpack_covers_validation_contract_and_safety(self) -> None:
        text = WORKPACK.read_text(encoding="utf-8")

        required_tokens = [
            "# WP-103 Physical Acceptance Canary",
            "Contract changes",
            "make test-physical-acceptance-canary",
            "Feature flags",
            "Migration and rollback",
            "Logs and metrics",
            "No runtime endpoint is added",
            "No physical printer action is executed by this PR",
            "Bambuddy still starts",
            "post-tag Security Audit",
            "manual Security Audit",
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_physical_acceptance_documents_do_not_contain_placeholders(self) -> None:
        placeholder_pattern = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|<[^>\n]+>")
        for path in (RUNBOOK, EVIDENCE, WORKPACK):
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(placeholder_pattern.search(text))


if __name__ == "__main__":
    unittest.main()
