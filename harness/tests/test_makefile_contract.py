from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"


def _target_body(text: str, target: str) -> str:
    match = re.search(rf"^{re.escape(target)}(?:[: ].*)?\n(?P<body>(?:\t.*\n)+)", text, re.MULTILINE)
    assert match is not None, f"missing Makefile target {target}"
    return match.group("body")


class MakefileContractTest(unittest.TestCase):
    def test_wp000_validation_targets_are_real_commands(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")

        for target in ("test-unit", "test-characterization", "verify-fast"):
            body = _target_body(text, target)
            self.assertNotIn("TODO WP-000", body)
            self.assertNotIn("exit 2", body)

    def test_harness_reset_is_guarded_to_farm_harness_project(self) -> None:
        body = _target_body(MAKEFILE.read_text(encoding="utf-8"), "harness-reset")

        self.assertIn("COMPOSE_PROJECT_NAME", body)
        self.assertIn("farm_harness", body)
        self.assertIn("down -v --remove-orphans", body)


if __name__ == "__main__":
    unittest.main()
