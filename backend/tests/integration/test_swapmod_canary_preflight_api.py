from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import swapmod_canary_preflight as preflight_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.tests.integration.test_plate_change_3mf_postprocess_api import ASGITransport, AsyncClient
from backend.tests.unit.services.test_swapmod_canary_preflight import CHECKLIST, dry_run_plan


class SwapmodCanaryPreflightApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
            group,
            settings,
            user,
        )

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_get_db():
            async with self.sessionmaker() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.patches = [
            patch("backend.app.core.database.async_session", self.sessionmaker),
            patch("backend.app.core.auth.async_session", self.sessionmaker),
            patch("backend.app.main.async_session", self.sessionmaker),
        ]
        for patcher in self.patches:
            patcher.start()

        self.previous_settings = {
            "farm_swapmod_canary_preflight_enabled": (
                preflight_route.settings.farm_swapmod_canary_preflight_enabled
            ),
            "farm_swapmod_canary_preflight_require_human_confirmation": (
                preflight_route.settings.farm_swapmod_canary_preflight_require_human_confirmation
            ),
            "farm_swapmod_canary_preflight_single_printer_only": (
                preflight_route.settings.farm_swapmod_canary_preflight_single_printer_only
            ),
        }
        preflight_route.settings.farm_swapmod_canary_preflight_enabled = False
        preflight_route.settings.farm_swapmod_canary_preflight_require_human_confirmation = True
        preflight_route.settings.farm_swapmod_canary_preflight_single_printer_only = True
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        for name, value in self.previous_settings.items():
            setattr(preflight_route.settings, name, value)
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    def enable_boundary(self) -> None:
        preflight_route.settings.farm_swapmod_canary_preflight_enabled = True

    def package_body(self, **overrides: object) -> dict[str, object]:
        plan = dry_run_plan()
        candidate = plan["candidate_blocks"][0]
        body: dict[str, object] = {
            "dry_run_plan": plan,
            "candidate_id": candidate["candidate_id"],
            "target_printer_id": "101",
            "expected_printer_model_family": "A1 Mini",
            "checklist": dict(CHECKLIST),
            "operator_confirmation_phrase": (
                f"CONFIRM_SWAPMOD_CANARY_PREFLIGHT 101 {candidate['candidate_id']} "
                f"{candidate['line_range_hash']}"
            ),
        }
        body.update(overrides)
        return body

    async def test_status_reports_safe_defaults(self) -> None:
        response = await self.client.get("/api/v1/plate-change-3mf/swapmod-canary-preflight/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["enabled"])
        self.assertEqual(body["mode"], "CANARY_PREFLIGHT_ONLY")
        self.assertFalse(body["real_execution_supported"])
        self.assertFalse(body["printer_command_supported"])
        self.assertFalse(body["printer_upload_supported"])
        self.assertFalse(body["printer_start_supported"])

    async def test_package_is_default_disabled(self) -> None:
        response = await self.client.post(
            "/api/v1/plate-change-3mf/swapmod-canary-preflight/packages",
            json=self.package_body(),
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())

    async def test_enabled_package_returns_redacted_preflight_without_side_effects(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change-3mf/swapmod-canary-preflight/packages",
            json=self.package_body(),
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["status"], "SWAPMOD_CANARY_PREFLIGHT_READY")
        self.assertEqual(body["selected_candidate"]["candidate_kind"], "inter_job_swap")
        self.assertFalse(body["real_execution_supported"])
        self.assertFalse(body["printer_command_supported"])
        self.assertTrue(all(value == 0 for value in body["sentinels"].values()))
        rendered = json.dumps(body, sort_keys=True)
        self.assertNotIn("G1 ", rendered)

    async def test_schema_rejects_raw_gcode_field(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change-3mf/swapmod-canary-preflight/packages",
            json=self.package_body(raw_gcode="G1 X999"),
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
