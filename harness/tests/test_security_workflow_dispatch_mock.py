from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECURITY_WORKFLOW = ROOT / ".github/workflows/security.yml"


class SecurityWorkflowDispatchTest(unittest.TestCase):
    def test_manual_dispatch_does_not_create_or_close_security_issues(self) -> None:
        text = SECURITY_WORKFLOW.read_text(encoding="utf-8")

        issue_step_pattern = re.compile(
            r"- name: Create or close (?P<kind>pip|npm) security issue\n"
            r"\s+if: (?P<condition>[^\n]+)"
        )
        conditions = {
            match.group("kind"): match.group("condition")
            for match in issue_step_pattern.finditer(text)
        }

        self.assertEqual({"pip", "npm"}, set(conditions))
        for kind, condition in conditions.items():
            with self.subTest(kind=kind):
                self.assertEqual("always() && github.event_name == 'schedule'", condition)
                self.assertNotIn("workflow_dispatch", condition)


    def test_manual_dispatch_preserves_audit_artifact_uploads(self) -> None:
        text = SECURITY_WORKFLOW.read_text(encoding="utf-8")

        for artifact_name in ("pip-audit-results", "npm-audit-results"):
            with self.subTest(artifact_name=artifact_name):
                artifact_index = text.index(f"name: {artifact_name}")
                step_start = text.rfind("- name: Upload audit results", 0, artifact_index)
                self.assertNotEqual(-1, step_start)
                step_body = text[step_start:artifact_index]
                self.assertIn("if: always()", step_body)
                self.assertNotIn("github.event_name == 'schedule'", step_body)


if __name__ == "__main__":
    unittest.main()
