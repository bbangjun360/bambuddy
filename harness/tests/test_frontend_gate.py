from __future__ import annotations

import unittest

from harness.scripts import check_frontend_gate


class FrontendGateTest(unittest.TestCase):
    def test_frontend_paths_require_frontend_evidence(self) -> None:
        result = check_frontend_gate.evaluate_frontend_gate(
            ["frontend/src/pages/QueuePage.tsx", "docs/KNOWN_ISSUES.md"],
            frontend_tested=False,
        )

        self.assertFalse(result.allowed)
        self.assertIn("make test-frontend", result.message)

    def test_frontend_paths_pass_when_evidence_ack_is_present(self) -> None:
        result = check_frontend_gate.evaluate_frontend_gate(
            ["frontend/src/pages/QueuePage.tsx"],
            frontend_tested=True,
        )

        self.assertTrue(result.allowed)
        self.assertIn("frontend test evidence acknowledged", result.message)

    def test_non_frontend_paths_do_not_require_node_toolchain(self) -> None:
        result = check_frontend_gate.evaluate_frontend_gate(
            ["Makefile", "harness/scripts/smoke.py"],
            frontend_tested=False,
        )

        self.assertTrue(result.allowed)
        self.assertIn("no frontend changes", result.message)


if __name__ == "__main__":
    unittest.main()
