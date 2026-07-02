from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "harness/scripts/physical_acceptance_evidence_template.py"
VALIDATOR = ROOT / "harness/scripts/physical_acceptance_evidence_validator.py"
RUNBOOK = ROOT / "docs/runbooks/WP105_PHYSICAL_ACCEPTANCE_EVIDENCE_TEMPLATE.md"
EVIDENCE = ROOT / "docs/releases/WP105_PHYSICAL_ACCEPTANCE_EVIDENCE_TEMPLATE.md"
WORKPACK = ROOT / "workpacks/exec/WP-105_PHYSICAL_ACCEPTANCE_EVIDENCE_TEMPLATE.md"


class PhysicalAcceptanceEvidenceTemplateHarnessTest(unittest.TestCase):
    def load_module(self, path: Path, name: str):
        self.assertTrue(path.exists(), f"{path.relative_to(ROOT)} is missing")
        spec = importlib.util.spec_from_file_location(name, path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def load_template(self):
        return self.load_module(TEMPLATE, "physical_acceptance_evidence_template")

    def load_validator(self):
        return self.load_module(VALIDATOR, "physical_acceptance_evidence_validator")

    def test_makefile_exposes_physical_acceptance_evidence_template_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-physical-acceptance-evidence-template:", makefile)
        self.assertIn(
            "test-physical-acceptance-evidence-template: harness-physical-acceptance-evidence-template",
            makefile,
        )
        target_body = makefile.split("test-physical-acceptance-evidence-template:", 1)[1].split("\n\n", 1)[0]
        self.assertIn("check_workpack.py workpacks/exec/WP-105_PHYSICAL_ACCEPTANCE_EVIDENCE_TEMPLATE.md", target_body)

    def test_documents_define_template_scope_and_safety_contract(self) -> None:
        missing = [str(path.relative_to(ROOT)) for path in (RUNBOOK, EVIDENCE, WORKPACK) if not path.exists()]
        self.assertEqual([], missing)

        combined = "\n".join(path.read_text(encoding="utf-8") for path in (RUNBOOK, EVIDENCE, WORKPACK))
        required_tokens = [
            "# WP-105 Physical Acceptance Evidence Template",
            "No physical printer action is executed by this template generator",
            "Bambuddy remains the sole authority",
            "Evidence template generation is not physical safety evidence",
            "Never automatically resume an uncertain physical bed action after restart",
            "MANUAL_REVIEW",
            "READY_FOR_NEXT_PRINT",
            "canary_key=wp103-physical-acceptance-YYYYMMDD-N",
            "No additional evidence keys are emitted",
            "operator_present=false",
            "release_verified=false",
            "loaded_verified=false",
            "final_state=MANUAL_REVIEW",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false",
            "python3 harness/scripts/physical_acceptance_evidence_template.py",
            "No runtime endpoint is added",
            "Bambuddy still starts",
            "Logs and metrics",
            "Migration and rollback",
            "Contract changes",
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, combined)

    def test_template_emits_exact_validator_field_set(self) -> None:
        template = self.load_template()
        validator = self.load_validator()

        record = template.build_template_record(
            canary_key="wp103-physical-acceptance-20260702-1",
            timestamp_utc="2026-07-02T06:10:00Z",
        )

        self.assertEqual(tuple(validator.REQUIRED_FIELDS), tuple(record.keys()))
        self.assertEqual(set(validator.REQUIRED_FIELDS), set(template.TEMPLATE_FIELDS))

    def test_template_defaults_to_manual_review_and_false_human_claims(self) -> None:
        template = self.load_template()
        validator = self.load_validator()

        record = template.build_template_record(
            canary_key="wp103-physical-acceptance-20260702-1",
            timestamp_utc="2026-07-02T06:10:00Z",
        )

        for field in validator.REQUIRED_TRUE_FIELDS:
            with self.subTest(field=field):
                self.assertEqual("false", record[field])
        self.assertEqual("false", record["release_verified"])
        self.assertEqual("false", record["loaded_verified"])
        self.assertEqual("MANUAL_REVIEW", record["final_state"])
        self.assertEqual("false", record["rollback_confirmed"])
        self.assertEqual("false", record["FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED"])
        self.assertEqual("false", record["FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS"])
        self.assertEqual("true", record["FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION"])
        self.assertEqual("A1_MINI_CANARY_REDACTED", record["printer_id_redacted"])
        self.assertEqual("REDACTED_OPERATOR", record["operator_initials"])
        self.assertEqual("REDACTED_LOG_BUNDLE", record["log_bundle_ref"])

        result = validator.validate_record(record)

        self.assertFalse(result.valid)
        self.assertFalse(result.ready_for_next_print)
        self.assertEqual("MANUAL_REVIEW", result.final_state)

    def test_template_can_be_completed_into_validator_ready_record(self) -> None:
        template = self.load_template()
        validator = self.load_validator()
        record = template.build_template_record(
            canary_key="wp103-physical-acceptance-20260702-1",
            timestamp_utc="2026-07-02T06:10:00Z",
        )

        for field in validator.REQUIRED_TRUE_FIELDS:
            record[field] = "true"
        record["release_sequence_sha256"] = "a" * 64
        record["load_sequence_sha256"] = "b" * 64
        record["release_verified"] = "true"
        record["loaded_verified"] = "true"
        record["final_state"] = "READY_FOR_NEXT_PRINT"
        record["rollback_confirmed"] = "true"

        result = validator.validate_record(record)

        self.assertTrue(result.valid, result.reasons)
        self.assertTrue(result.ready_for_next_print)

    def test_cli_stdout_is_parseable_by_validator(self) -> None:
        self.assertTrue(TEMPLATE.exists(), "physical acceptance evidence template script is missing")
        validator = self.load_validator()
        completed = subprocess.run(
            [
                sys.executable,
                str(TEMPLATE),
                "--canary-key",
                "wp103-physical-acceptance-20260702-1",
                "--timestamp-utc",
                "2026-07-02T06:10:00Z",
            ],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

        self.assertEqual(0, completed.returncode, completed.stdout)
        records = validator.parse_records(completed.stdout)
        self.assertEqual(1, len(records))
        self.assertEqual(set(validator.REQUIRED_FIELDS), set(records[0]))
        self.assertEqual("MANUAL_REVIEW", records[0]["final_state"])

    def test_cli_can_write_template_file_and_rejects_bad_canary_key(self) -> None:
        self.assertTrue(TEMPLATE.exists(), "physical acceptance evidence template script is missing")

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "evidence.env"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TEMPLATE),
                    "--canary-key",
                    "wp103-physical-acceptance-20260702-1",
                    "--timestamp-utc",
                    "2026-07-02T06:10:00Z",
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stdout)
            self.assertIn("wrote ", completed.stdout)
            self.assertIn("final_state=MANUAL_REVIEW", output_path.read_text(encoding="utf-8"))

        rejected = subprocess.run(
            [sys.executable, str(TEMPLATE), "--canary-key", "wp104-physical-acceptance-20260702-1"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

        self.assertEqual(1, rejected.returncode, rejected.stdout)
        self.assertIn("canary_key must match wp103-physical-acceptance-YYYYMMDD-N", rejected.stdout)

    def test_cli_rejects_malformed_or_injectable_timestamp(self) -> None:
        self.assertTrue(TEMPLATE.exists(), "physical acceptance evidence template script is missing")
        bad_timestamps = (
            "notTvalidZ",
            "2026-07-02T06:10:00",
            "2026-07-02 06:10:00Z",
            "2026-07-02T06:10:00Z\nunexpected_field=not_evidenceZ",
        )

        for timestamp in bad_timestamps:
            with self.subTest(timestamp=timestamp):
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(TEMPLATE),
                        "--canary-key",
                        "wp103-physical-acceptance-20260702-1",
                        "--timestamp-utc",
                        timestamp,
                    ],
                    cwd=ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                self.assertEqual(1, completed.returncode, completed.stdout)
                self.assertIn("timestamp_utc must be strict UTC ISO-8601 seconds ending in Z", completed.stdout)

    def test_physical_acceptance_template_documents_do_not_contain_placeholders(self) -> None:
        placeholder_pattern = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|<[^>\n]+>")
        for path in (RUNBOOK, EVIDENCE, WORKPACK):
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"{path.relative_to(ROOT)} is missing")
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(placeholder_pattern.search(text))


if __name__ == "__main__":
    unittest.main()
