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

        self.assertEqual(values["COMPOSE_PROJECT_NAME"], "farm_wp030")
        self.assertEqual(values["POSTGRES_DB"], "bambuddy")
        self.assertEqual(values["POSTGRES_USER"], "bambuddy")
        self.assertEqual(values["POSTGRES_PASSWORD"], "local-harness-only")

    def test_harness_env_pins_images_and_local_ports(self) -> None:
        values = _read_env()

        for key in ("POSTGRES_IMAGE", "PYTHON_IMAGE", "ORCA_IMAGE"):
            with self.subTest(key=key):
                image = values[key]
                self.assertIn(":", image)
                self.assertIn("@sha256:", image)
                self.assertNotIn("REPLACE", image)
                self.assertNotIn(":latest", image)

        self.assertEqual(values["BAMBUDDY_PORT"], "18130")
        self.assertEqual(values["MOCK_PORT"], "19130")
        self.assertEqual(values["ORCA_API_PORT"], "13130")


if __name__ == "__main__":
    unittest.main()
