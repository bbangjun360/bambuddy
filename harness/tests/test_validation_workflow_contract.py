from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATION_WORKFLOW = ROOT / ".github/workflows/validation.yml"


class ValidationWorkflowContractTest(unittest.TestCase):
    def test_pull_requests_to_farm_and_stacked_workpack_bases_run_validation(
        self,
    ) -> None:
        text = VALIDATION_WORKFLOW.read_text(encoding="utf-8")
        trigger_block = text.split("\npermissions:", maxsplit=1)[0]

        self.assertIn("  pull_request:\n", trigger_block)
        self.assertIn(
            '    branches: [farm-main, "feature/wp-*"]',
            trigger_block,
        )
        self.assertIn("  workflow_dispatch:\n", trigger_block)


if __name__ == "__main__":
    unittest.main()
