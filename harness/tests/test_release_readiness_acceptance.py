from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = ROOT / "docs/runbooks/RELEASE_READINESS_ACCEPTANCE.md"
RELEASE_NOTES = ROOT / "docs/releases/WP101_RELEASE_NOTES_DRAFT.md"
WORKPACK = ROOT / "workpacks/exec/WP-101_RELEASE_READINESS_AND_ACCEPTANCE.md"


class ReleaseReadinessAcceptanceHarnessTest(unittest.TestCase):
    def test_makefile_exposes_release_readiness_acceptance_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-release-readiness-acceptance:", makefile)
        self.assertIn(
            "test-release-readiness-acceptance: harness-release-readiness-acceptance",
            makefile,
        )
        target_body = makefile.split("test-release-readiness-acceptance:", 1)[1].split("\n\n", 1)[0]
        self.assertIn("check_workpack.py workpacks/exec/WP-101_RELEASE_READINESS_AND_ACCEPTANCE.md", target_body)

    def test_release_readiness_runbook_covers_required_acceptance_gates(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")

        required_tokens = [
            "# Release Readiness Acceptance",
            "Release Candidate Identity",
            "Code And CI Acceptance",
            "Contract Acceptance",
            "Safety And Data Acceptance",
            "Hardware Canary Acceptance",
            "Release Tagging",
            "Rollback",
            "Post-Release Monitoring",
            "Bambuddy remains the sole authority",
            "No physical printer action is executed by this checklist",
            "Simulation success is not physical safety evidence",
            "Never automatically resume an uncertain physical bed action after restart",
            "make verify-fast",
            "make verify-full",
            "GitHub Actions",
            "Security Audit",
            "Validation",
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_release_notes_draft_covers_release_artifacts_and_risk(self) -> None:
        text = RELEASE_NOTES.read_text(encoding="utf-8")

        required_tokens = [
            "# WP-101 Release Notes Draft",
            "Release Scope",
            "Release Candidate",
            "Validation Evidence",
            "Changed Contracts",
            "Feature Flags",
            "Migration And Rollback",
            "Hardware Test Position",
            "Known Risks",
            "WP-000 through WP-100",
            "d20e5f94b5c7f87ca3bed84501e39fd6f3849685",
            "FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false",
            "FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false",
            "FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false",
            "FARM_BED_AUTOMATION_ENABLED=false",
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_workpack_covers_release_acceptance_requirements(self) -> None:
        text = WORKPACK.read_text(encoding="utf-8")

        required_tokens = [
            "# WP-101 Release Readiness And Acceptance",
            "Validation commands",
            "Evidence from this branch",
            "Contract changes",
            "Migration and rollback",
            "Logs and metrics",
            "Existing default-off settings remain unchanged",
            "FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false",
            "FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false",
            "FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false",
            "FARM_BED_AUTOMATION_ENABLED=false",
            "Docker no-network Bambuddy app import smoke",
            "bambuddy_app_import_ok True",
            "make verify-full COMPOSE_PROJECT_NAME=farm_wp030",
            "post-merge security audit",
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_acceptance_documents_do_not_contain_placeholders(self) -> None:
        placeholder_pattern = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|<[^>\n]+>")
        for path in (RUNBOOK, RELEASE_NOTES, WORKPACK):
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(placeholder_pattern.search(text))


if __name__ == "__main__":
    unittest.main()
