from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = ROOT / "docs" / "reference" / "print-farm-os"
PHASE0_FIXTURES = ROOT / "harness" / "fixtures" / "phase0"


class PrintFarmOsReferencePolicyTest(unittest.TestCase):
    def test_phase0_fixture_directory_contains_only_policy_readme(self) -> None:
        self.assertTrue(PHASE0_FIXTURES.is_dir())

        tracked_files = sorted(
            path.relative_to(PHASE0_FIXTURES).as_posix()
            for path in PHASE0_FIXTURES.rglob("*")
            if path.is_file()
        )
        self.assertEqual(tracked_files, ["README.md"])

        readme = (PHASE0_FIXTURES / "README.md").read_text(encoding="utf-8")
        self.assertIn("No Print Farm OS raw sample artifacts", readme)
        self.assertNotIn("Safe example fixtures copied", readme)
        self.assertNotIn("for harness and planning use only", readme)

    def test_reference_policy_forbids_raw_artifacts_and_sensitive_values(self) -> None:
        readme = (REFERENCE_ROOT / "README.md").read_text(encoding="utf-8")

        required_policy = [
            "Do not merge the branch",
            "cherry-pick it",
            "raw 3MF",
            "raw G-code",
            "generated artifacts",
            "logs",
            "access codes",
            "serial numbers",
            "IP addresses",
            "tokens",
            "customer data",
        ]
        for phrase in required_policy:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, readme)

        stale_policy = [
            "Preserve lab evidence when useful",
            "Safe example fixtures copied",
            "lab context is allowed",
        ]
        for phrase in stale_policy:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, readme)

    def test_reference_tree_contains_policy_markdown_only(self) -> None:
        self.assertTrue(REFERENCE_ROOT.is_dir())

        forbidden_suffixes = {
            ".3mf",
            ".gcode",
            ".stl",
            ".log",
            ".env",
            ".json",
        }
        for path in REFERENCE_ROOT.rglob("*"):
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertFalse(path.is_file() and path.suffix.lower() in forbidden_suffixes)


if __name__ == "__main__":
    unittest.main()
