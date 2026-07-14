from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
RUNTIME_ENV_CONSUMERS = {
    "harness/scripts/backup_restore.py": "ENV_FILE",
    "harness/scripts/obico_shadow.py": "HARNESS_ENV_FILE",
    "harness/scripts/observability_health.py": "HARNESS_ENV_FILE",
    "harness/scripts/orca_direct_slice.py": "HARNESS_ENV_FILE",
    "harness/scripts/orca_health.py": "HARNESS_ENV_FILE",
    "harness/scripts/persistence.py": "ENV_FILE",
    "harness/scripts/smoke.py": "HARNESS_ENV_FILE",
}

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


class HarnessEnvSelectionContractTest(unittest.TestCase):
    def _selected_path(self, script: str, constant: str, selected: str) -> Path:
        env = os.environ.copy()
        env["HARNESS_ENV"] = selected
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import runpy, sys; print(runpy.run_path(sys.argv[1])[sys.argv[2]])",
                script,
                constant,
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(result.stdout.strip())

    def test_runtime_scripts_honor_absolute_harness_env_selection(self) -> None:
        with TemporaryDirectory() as tmpdir:
            selected = Path(tmpdir) / "selected.env"
            selected.write_text("COMPOSE_PROJECT_NAME=farm_harness\n", encoding="utf-8")

            for script, constant in RUNTIME_ENV_CONSUMERS.items():
                with self.subTest(script=script):
                    self.assertEqual(
                        self._selected_path(script, constant, str(selected)),
                        selected,
                    )

    def test_runtime_scripts_anchor_relative_selection_at_repository_root(self) -> None:
        selected = Path("harness/fixtures/selected.env")

        for script, constant in RUNTIME_ENV_CONSUMERS.items():
            with self.subTest(script=script):
                self.assertEqual(
                    self._selected_path(script, constant, str(selected)),
                    ROOT / selected,
                )

    def test_makefile_exports_harness_env_to_runtime_scripts(self) -> None:
        self.assertIn("export HARNESS_ENV", MAKEFILE.read_text(encoding="utf-8").splitlines())

    def test_destructive_harness_scripts_keep_default_project_guard(self) -> None:
        for script in (
            ROOT / "harness/scripts/backup_restore.py",
            ROOT / "harness/scripts/persistence.py",
        ):
            with self.subTest(script=script.name):
                source = script.read_text(encoding="utf-8")
                self.assertIn('COMPOSE_PROJECT_NAME") != "farm_harness"', source)
                self.assertIn("refusing", source)


if __name__ == "__main__":
    unittest.main()
