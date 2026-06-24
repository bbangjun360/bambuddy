from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env.harness"


def _read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


class HarnessEnvTest(unittest.TestCase):
    def test_harness_env_exists_and_uses_isolated_project(self) -> None:
        values = _read_env()

        self.assertEqual(values["COMPOSE_PROJECT_NAME"], "farm_harness")
        self.assertEqual(values["POSTGRES_DB"], "bambuddy_harness")
        self.assertEqual(values["POSTGRES_USER"], "bambuddy_harness")
        self.assertEqual(values["POSTGRES_PASSWORD"], "bambuddy_harness_password")

    def test_harness_env_pins_images_and_local_ports(self) -> None:
        values = _read_env()

        self.assertIn(":", values["POSTGRES_IMAGE"])
        self.assertIn(":", values["PYTHON_IMAGE"])
        self.assertTrue(values["BAMBUDDY_PORT"].startswith("18"))
        self.assertTrue(values["MOCK_PORT"].startswith("19"))


if __name__ == "__main__":
    unittest.main()
