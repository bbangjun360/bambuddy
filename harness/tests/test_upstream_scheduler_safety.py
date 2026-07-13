from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEDULER = ROOT / "backend/app/services/print_scheduler.py"
SETTINGS_SCHEMA = ROOT / "backend/app/schemas/settings.py"
SETTINGS_PAGE = ROOT / "frontend/src/pages/SettingsPage.tsx"


class UpstreamSchedulerSafetyCharacterizationTest(unittest.TestCase):
    def test_missing_plate_clear_setting_remains_fail_closed_for_farm(self) -> None:
        source = SCHEDULER.read_text(encoding="utf-8")
        schema_source = SETTINGS_SCHEMA.read_text(encoding="utf-8")
        settings_page_source = SETTINGS_PAGE.read_text(encoding="utf-8")

        self.assertIn(
            'require_plate_clear = await self._get_bool_setting(db, "require_plate_clear", default=True)',
            source,
        )
        self.assertNotIn(
            'require_plate_clear = await self._get_bool_setting(db, "require_plate_clear", default=False)',
            source,
        )


        plate_setting = schema_source.split("require_plate_clear: bool = Field(", 1)[1].split(")", 1)[0]
        self.assertIn("default=True", plate_setting)
        self.assertIn(
            "(settings.require_plate_clear ?? true) !== (localSettings.require_plate_clear ?? true)",
            settings_page_source,
        )
        self.assertIn("checked={localSettings.require_plate_clear ?? true}", settings_page_source)

if __name__ == "__main__":
    unittest.main()
