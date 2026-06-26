from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

DEFAULT_HARNESS_ENV = "\n".join(
    [
        "# Synthetic isolated fixture. Do not read repo-local .env.harness here.",
        "COMPOSE_PROJECT_NAME=farm_wp030",
        "POSTGRES_IMAGE=postgres:16.4-alpine@sha256:" + "a" * 64,
        "PYTHON_IMAGE=python:3.13-slim@sha256:" + "b" * 64,
        "ORCA_IMAGE=ghcr.io/bbangjun360/orca-slicer-api:qualified@sha256:" + "c" * 64,
        "POSTGRES_DB=bambuddy",
        "POSTGRES_USER=bambuddy",
        "POSTGRES_PASSWORD=local-harness-only",
        "BAMBUDDY_PORT=18130",
        "MOCK_PORT=19130",
        "ORCA_API_PORT=13130",
    ]
)


def _write_env_fixture(directory: str, body: str = DEFAULT_HARNESS_ENV) -> Path:
    env_file = Path(directory) / ".env.harness"
    env_file.write_text(body, encoding="utf-8")
    return env_file


def _read_env(env_file: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


class HarnessEnvTest(unittest.TestCase):
    def test_selected_harness_env_fixture_uses_isolated_project(self) -> None:
        with TemporaryDirectory() as tmpdir:
            values = _read_env(_write_env_fixture(tmpdir))

        self.assertEqual(values["COMPOSE_PROJECT_NAME"], "farm_wp030")
        self.assertEqual(values["POSTGRES_DB"], "bambuddy")
        self.assertEqual(values["POSTGRES_USER"], "bambuddy")
        self.assertEqual(values["POSTGRES_PASSWORD"], "local-harness-only")

    def test_selected_harness_env_fixture_pins_images_and_default_ports(self) -> None:
        with TemporaryDirectory() as tmpdir:
            values = _read_env(_write_env_fixture(tmpdir))

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
