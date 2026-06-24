from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
import unittest

import harness.scripts.smoke as smoke


SCENARIO_NAME = "synthetic-baseline-harness-smoke"
SYNTHETIC_SCENARIO_ENV = "\n".join(
    [
        "COMPOSE_PROJECT_NAME=farm_scenario_synthetic",
        "BAMBUDDY_PORT=18130",
        "MOCK_PORT=19130",
    ]
)
FORBIDDEN_SCENARIO_MARKERS = (
    "BAMBU_ACCESS_CODE",
    "PRINTER_SERIAL",
    "MQTT_PASSWORD",
    "ERP_API_KEY",
    "OBICO_API_KEY",
    "CUSTOMER_EMAIL",
    "PRODUCTION",
)


class BaselineHarnessScenarioTest(unittest.TestCase):
    def _write_env(self, tmpdir: str) -> Path:
        env_file = Path(tmpdir) / ".env.harness"
        env_file.write_text(SYNTHETIC_SCENARIO_ENV, encoding="utf-8")
        return env_file

    def test_synthetic_baseline_scenario_resolves_loopback_targets(self) -> None:
        with TemporaryDirectory() as tmpdir:
            targets = smoke.resolve_targets(env_file=self._write_env(tmpdir), environ={})

        self.assertEqual(
            targets,
            {
                "bambuddy-root": "http://127.0.0.1:18130/",
                "bambuddy-health": "http://127.0.0.1:18130/health",
                "bambuddy-docs": "http://127.0.0.1:18130/docs",
                "mock-services": "http://127.0.0.1:19130/health",
            },
        )
        for name, url in targets.items():
            with self.subTest(name=name):
                parsed = urlparse(url)
                self.assertEqual(parsed.scheme, "http")
                self.assertEqual(parsed.hostname, "127.0.0.1")

    def test_synthetic_baseline_scenario_excludes_real_data_markers(self) -> None:
        scenario_text = "\n".join([SCENARIO_NAME, SYNTHETIC_SCENARIO_ENV])

        self.assertIn("synthetic", SCENARIO_NAME)
        self.assertIn("harness", SCENARIO_NAME)
        for marker in FORBIDDEN_SCENARIO_MARKERS:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, scenario_text)
        self.assertNotRegex(scenario_text, r"\b(?:10|172\.(?:1[6-9]|2\d|3[0-1])|192\.168)\.\d{1,3}\.\d{1,3}\b")


if __name__ == "__main__":
    unittest.main()
