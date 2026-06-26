from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import swapmod_3mf_dry_run as swapmod_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.tests.integration.test_plate_change_3mf_postprocess_api import ASGITransport, AsyncClient


def _write_3mf(path: Path, gcode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("3D/3dmodel.model", b"<model/>")
        zf.writestr("Metadata/plate_1.gcode", gcode.encode("utf-8"))


class Swapmod3mfDryRunApiTest(unittest.IsolatedAsyncioTestCase):
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
            "farm_swapmod_3mf_dry_run_enabled": swapmod_route.settings.farm_swapmod_3mf_dry_run_enabled,
            "farm_swapmod_3mf_dry_run_required": swapmod_route.settings.farm_swapmod_3mf_dry_run_required,
            "farm_swapmod_3mf_sample_root": swapmod_route.settings.farm_swapmod_3mf_sample_root,
        }
        swapmod_route.settings.farm_swapmod_3mf_dry_run_enabled = False
        swapmod_route.settings.farm_swapmod_3mf_dry_run_required = True

        self.tmp = Path(tempfile.mkdtemp(prefix="wp065-swapmod-api-"))
        self.sample_root = self.tmp / "samples"
        self.original = self.sample_root / "original.3mf"
        self.swapmod = self.sample_root / "swapmod.3mf"
        original_gcode = "G28\n; print\nG1 X1\nM400\n"
        swapmod_gcode = (
            "; load\nG1 Y1\n"
            + original_gcode
            + "; swap\nG1 Y2\nG4 P100\n"
            + original_gcode
            + "; final\nG1 Y3\n"
        )
        _write_3mf(self.original, original_gcode)
        _write_3mf(self.swapmod, swapmod_gcode)
        swapmod_route.settings.farm_swapmod_3mf_sample_root = str(self.sample_root)
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        for name, value in self.previous_settings.items():
            setattr(swapmod_route.settings, name, value)
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def enable_boundary(self) -> None:
        swapmod_route.settings.farm_swapmod_3mf_dry_run_enabled = True

    def plan_body(self, **overrides: object) -> dict[str, object]:
        body: dict[str, object] = {
            "original_path": str(self.original),
            "swapmod_path": str(self.swapmod),
            "dry_run": True,
            "expected_printer_model_family": "A1 Mini",
        }
        body.update(overrides)
        return body

    async def test_status_reports_safe_defaults(self) -> None:
        response = await self.client.get("/api/v1/plate-change-3mf/swapmod-dry-run/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["enabled"])
        self.assertEqual(body["mode"], "DRY_RUN_ONLY")
        self.assertFalse(body["real_execution_supported"])
        self.assertFalse(body["printer_upload_supported"])
        self.assertFalse(body["printer_start_supported"])

    async def test_plan_is_default_disabled(self) -> None:
        response = await self.client.post(
            "/api/v1/plate-change-3mf/swapmod-dry-run/plans",
            json=self.plan_body(),
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())

    async def test_enabled_plan_returns_redacted_candidates_without_raw_gcode(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change-3mf/swapmod-dry-run/plans",
            json=self.plan_body(),
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["status"], "SWAPMOD_DRY_RUN_READY")
        self.assertEqual(len(body["candidate_blocks"]), 3)
        rendered = json.dumps(body, sort_keys=True)
        self.assertNotIn("G1 Y2", rendered)
        self.assertFalse(body["real_execution_supported"])
        self.assertFalse(body["printer_upload_supported"])
        self.assertFalse(body["printer_start_supported"])
        self.assertTrue(all(value == 0 for value in body["sentinels"].values()))

    async def test_schema_rejects_raw_gcode_field(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change-3mf/swapmod-dry-run/plans",
            json=self.plan_body(raw_gcode="G1 X999"),
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
