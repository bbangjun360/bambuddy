from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "harness/scripts/physical_acceptance_evidence_validator.py"
RUNBOOK = ROOT / "docs/runbooks/WP104_PHYSICAL_ACCEPTANCE_EVIDENCE_VALIDATOR.md"
EVIDENCE = ROOT / "docs/releases/WP104_PHYSICAL_ACCEPTANCE_EVIDENCE_VALIDATION.md"
WORKPACK = ROOT / "workpacks/exec/WP-104_PHYSICAL_ACCEPTANCE_EVIDENCE_VALIDATOR.md"


class PhysicalAcceptanceEvidenceValidatorHarnessTest(unittest.TestCase):
    def load_validator(self):
        self.assertTrue(VALIDATOR.exists(), "physical acceptance evidence validator script is missing")
        spec = importlib.util.spec_from_file_location("physical_acceptance_evidence_validator", VALIDATOR)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def complete_ready_record(self) -> dict[str, str]:
        return {
            "canary_key": "wp103-physical-acceptance-20260702-1",
            "printer_id_redacted": "A1_MINI_CANARY_REDACTED",
            "release_tag": "farm-v0.1.0-acceptance",
            "release_commit": "9190b2fc6ac1e111234ad73d8d73e2a487d81be5",
            "operator_present": "true",
            "printer_visible": "true",
            "emergency_stop_ready": "true",
            "power_cutoff_ready": "true",
            "a1_mini_confirmed": "true",
            "swapmod_hardware_installed": "true",
            "bed_area_clear": "true",
            "plate_stack_ready": "true",
            "no_other_job_running": "true",
            "dry_run_gate_reviewed": "true",
            "release_sequence_sha256": "a" * 64,
            "load_sequence_sha256": "b" * 64,
            "release_verified": "true",
            "loaded_verified": "true",
            "final_state": "READY_FOR_NEXT_PRINT",
            "rollback_confirmed": "true",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED": "false",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS": "false",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION": "true",
            "timestamp_utc": "2026-07-02T03:45:00Z",
            "operator_initials": "REDACTED_OPERATOR",
            "log_bundle_ref": "REDACTED_LOG_BUNDLE",
        }

    def test_makefile_exposes_physical_acceptance_evidence_validator_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-physical-acceptance-evidence-validator:", makefile)
        self.assertIn(
            "test-physical-acceptance-evidence-validator: harness-physical-acceptance-evidence-validator",
            makefile,
        )
        target_body = makefile.split("test-physical-acceptance-evidence-validator:", 1)[1].split("\n\n", 1)[0]
        self.assertIn("check_workpack.py workpacks/exec/WP-104_PHYSICAL_ACCEPTANCE_EVIDENCE_VALIDATOR.md", target_body)

    def test_documents_define_human_gated_validator_scope(self) -> None:
        missing = [str(path.relative_to(ROOT)) for path in (RUNBOOK, EVIDENCE, WORKPACK) if not path.exists()]
        self.assertEqual([], missing)

        combined = "\n".join(path.read_text(encoding="utf-8") for path in (RUNBOOK, EVIDENCE, WORKPACK))
        required_tokens = [
            "# WP-104 Physical Acceptance Evidence Validator",
            "farm-v0.1.0-acceptance",
            "9190b2fc6ac1e111234ad73d8d73e2a487d81be5",
            "No physical printer action is executed by this validator",
            "Bambuddy remains the sole authority",
            "Evidence validation is not physical safety evidence",
            "Never automatically resume an uncertain physical bed action after restart",
            "READY_FOR_NEXT_PRINT",
            "MANUAL_REVIEW",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false",
            "canary_key=wp103-physical-acceptance-YYYYMMDD-N",
            "No additional evidence keys are accepted",
            "python3 harness/scripts/physical_acceptance_evidence_validator.py",
            "No runtime endpoint is added",
            "Bambuddy still starts",
            "Logs and metrics",
            "Migration and rollback",
            "Contract changes",
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_validator_accepts_complete_ready_record(self) -> None:
        validator = self.load_validator()

        result = validator.validate_record(self.complete_ready_record())

        self.assertTrue(result.valid, result.reasons)
        self.assertTrue(result.ready_for_next_print)
        self.assertEqual("READY_FOR_NEXT_PRINT", result.final_state)
        self.assertEqual((), result.reasons)

    def test_validator_rejects_missing_required_fields(self) -> None:
        validator = self.load_validator()
        record = self.complete_ready_record()
        del record["load_sequence_sha256"]

        result = validator.validate_record(record)

        self.assertFalse(result.valid)
        self.assertFalse(result.ready_for_next_print)
        self.assertIn("missing load_sequence_sha256", result.reasons)

    def test_validator_rejects_non_wp103_canary_key(self) -> None:
        validator = self.load_validator()
        bad_keys = ("wp104-physical-acceptance-20260702-1", "wp103-physical-acceptance-pending")

        for canary_key in bad_keys:
            with self.subTest(canary_key=canary_key):
                record = self.complete_ready_record()
                record["canary_key"] = canary_key
                result = validator.validate_record(record)

                self.assertFalse(result.valid)
                self.assertIn("canary_key must match wp103-physical-acceptance-YYYYMMDD-N", result.reasons)

    def test_validator_rejects_unexpected_evidence_fields(self) -> None:
        validator = self.load_validator()
        unexpected_fields = ("printer_serial", "access_code", "api_token", "operator_name", "notes")

        for field in unexpected_fields:
            with self.subTest(field=field):
                record = self.complete_ready_record()
                record[field] = "REAL_VALUE_REDACTED"
                result = validator.validate_record(record)
                self.assertFalse(result.valid)
                self.assertIn(f"unexpected field {field}", result.reasons)

    def test_validator_rejects_ready_state_without_verified_steps(self) -> None:
        validator = self.load_validator()
        record = self.complete_ready_record()
        record["release_verified"] = "false"

        result = validator.validate_record(record)

        self.assertFalse(result.valid)
        self.assertIn("release_verified must be true for READY_FOR_NEXT_PRINT", result.reasons)

    def test_validator_rejects_other_ready_state_safety_failures(self) -> None:
        validator = self.load_validator()
        cases = {
            "loaded_verified": ("false", "loaded_verified must be true for READY_FOR_NEXT_PRINT"),
            "rollback_confirmed": ("false", "rollback_confirmed must be true for READY_FOR_NEXT_PRINT"),
            "release_sequence_sha256": ("not-a-sha", "release_sequence_sha256 must be a lowercase SHA-256 hex digest"),
            "load_sequence_sha256": ("B" * 64, "load_sequence_sha256 must be a lowercase SHA-256 hex digest"),
            "final_state": ("MANUAL_REVIEW", "final_state must be READY_FOR_NEXT_PRINT"),
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED": ("true", "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED must be false"),
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION": ("false", "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION must be true"),
            "operator_present": ("false", "operator_present must be true"),
        }

        for field, (value, expected_reason) in cases.items():
            with self.subTest(field=field):
                record = self.complete_ready_record()
                record[field] = value
                result = validator.validate_record(record)
                self.assertFalse(result.valid)
                self.assertIn(expected_reason, result.reasons)

    def test_validator_rejects_unredacted_printer_identifier(self) -> None:
        validator = self.load_validator()
        record = self.complete_ready_record()
        record["printer_id_redacted"] = "A1-MINI-REAL-SERIAL-123"

        result = validator.validate_record(record)

        self.assertFalse(result.valid)
        self.assertIn("printer_id_redacted must be A1_MINI_CANARY_REDACTED", result.reasons)

    def test_validator_rejects_partially_redacted_sensitive_fields(self) -> None:
        validator = self.load_validator()
        cases = {
            "printer_id_redacted": ("REAL_SERIAL_123_REDACTED", "printer_id_redacted must be A1_MINI_CANARY_REDACTED"),
            "operator_initials": ("BJ_REDACTED", "operator_initials must be REDACTED_OPERATOR"),
            "log_bundle_ref": ("/tmp/real-log-path_REDACTED", "log_bundle_ref must be REDACTED_LOG_BUNDLE"),
        }

        for field, (value, expected_reason) in cases.items():
            with self.subTest(field=field):
                record = self.complete_ready_record()
                record[field] = value
                result = validator.validate_record(record)
                self.assertFalse(result.valid)
                self.assertIn(expected_reason, result.reasons)

    def test_validator_rejects_real_command_flag_enabled(self) -> None:
        validator = self.load_validator()
        record = self.complete_ready_record()
        record["FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS"] = "true"

        result = validator.validate_record(record)

        self.assertFalse(result.valid)
        self.assertIn("FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS must be false", result.reasons)

    def test_validator_cli_reports_manual_review_for_invalid_record(self) -> None:
        self.assertTrue(VALIDATOR.exists(), "physical acceptance evidence validator script is missing")
        record = self.complete_ready_record()
        del record["load_sequence_sha256"]
        body = "\n".join(f"{key}={value}" for key, value in record.items())

        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_path = Path(tmpdir) / "invalid-evidence.env"
            evidence_path.write_text(body, encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(VALIDATOR), str(evidence_path)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

        self.assertEqual(1, completed.returncode, completed.stdout)
        self.assertIn("MANUAL_REVIEW", completed.stdout)
        self.assertIn("missing load_sequence_sha256", completed.stdout)

    def test_physical_acceptance_validator_documents_do_not_contain_placeholders(self) -> None:
        placeholder_pattern = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|<[^>\n]+>")
        for path in (RUNBOOK, EVIDENCE, WORKPACK):
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"{path.relative_to(ROOT)} is missing")
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(placeholder_pattern.search(text))


if __name__ == "__main__":
    unittest.main()
