from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "backend/app/main.py"
COMPOSE = ROOT / "harness/docker-compose.harness.yml"


class BambuddyBaselineCharacterizationTest(unittest.TestCase):
    def test_source_exposes_root_health_and_docs_endpoints(self) -> None:
        text = MAIN.read_text(encoding="utf-8")

        self.assertIn('@app.get("/")', text)
        self.assertIn('@app.get("/health")', text)
        self.assertIn('return {"status": "healthy"}', text)

    def test_harness_uses_postgresql_without_printer_credentials(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")

        self.assertIn("postgresql+asyncpg://", text)
        self.assertIn("POSTGRES_PASSWORD", text)
        self.assertNotIn("BAMBU_ACCESS_CODE", text)
        self.assertNotIn("PRINTER_SERIAL", text)
        self.assertNotIn("MQTT_PASSWORD", text)


if __name__ == "__main__":
    unittest.main()
