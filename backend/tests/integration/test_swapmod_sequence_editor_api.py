from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import swapmod_a1mini_direct_canary as direct_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.tests.integration.test_plate_change_3mf_postprocess_api import ASGITransport, AsyncClient


class SwapmodSequenceEditorApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
            group,
            print_log,
            print_queue,
            printer,
            settings,
            swapmod_state_machine,
            user,
        )

        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.release_text = "G91\nG1 X-14 F5000\nG1 Y182 F10000\nG90\n"
        self.load_text = "G91\nG1 Y180 F2000\nG90\n"
        (self.root / "release.gcode").write_text(self.release_text, encoding="utf-8")
        (self.root / "load.gcode").write_text(self.load_text, encoding="utf-8")
        self.release_sha = hashlib.sha256(self.release_text.encode("utf-8")).hexdigest()
        self.load_sha = hashlib.sha256(self.load_text.encode("utf-8")).hexdigest()

        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async def override_get_db():
            async with self.sessionmaker() as session:
                try:
                    yield session
                    await session.commit()
                except BaseException:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_get_db
        self.patches = [
            patch("backend.app.core.database.async_session", self.sessionmaker),
            patch("backend.app.core.auth.async_session", self.sessionmaker),
            patch("backend.app.main.async_session", self.sessionmaker),
        ]
        for patcher in self.patches:
            patcher.start()

        self.previous_values = {
            "farm_swapmod_a1mini_sequence_editor_enabled": direct_route.settings.farm_swapmod_a1mini_sequence_editor_enabled,
            "farm_swapmod_a1mini_direct_canary_enabled": direct_route.settings.farm_swapmod_a1mini_direct_canary_enabled,
            "farm_swapmod_a1mini_direct_canary_allow_real_commands": direct_route.settings.farm_swapmod_a1mini_direct_canary_allow_real_commands,
            "farm_swapmod_a1mini_direct_canary_sequence_root": direct_route.settings.farm_swapmod_a1mini_direct_canary_sequence_root,
            "farm_swapmod_a1mini_direct_canary_release_sequence_file": direct_route.settings.farm_swapmod_a1mini_direct_canary_release_sequence_file,
            "farm_swapmod_a1mini_direct_canary_release_sequence_sha256": direct_route.settings.farm_swapmod_a1mini_direct_canary_release_sequence_sha256,
            "farm_swapmod_a1mini_direct_canary_load_sequence_file": direct_route.settings.farm_swapmod_a1mini_direct_canary_load_sequence_file,
            "farm_swapmod_a1mini_direct_canary_load_sequence_sha256": direct_route.settings.farm_swapmod_a1mini_direct_canary_load_sequence_sha256,
        }
        direct_route.settings.farm_swapmod_a1mini_sequence_editor_enabled = False
        direct_route.settings.farm_swapmod_a1mini_direct_canary_enabled = False
        direct_route.settings.farm_swapmod_a1mini_direct_canary_allow_real_commands = False
        direct_route.settings.farm_swapmod_a1mini_direct_canary_sequence_root = str(self.root)
        direct_route.settings.farm_swapmod_a1mini_direct_canary_release_sequence_file = "release.gcode"
        direct_route.settings.farm_swapmod_a1mini_direct_canary_release_sequence_sha256 = self.release_sha
        direct_route.settings.farm_swapmod_a1mini_direct_canary_load_sequence_file = "load.gcode"
        direct_route.settings.farm_swapmod_a1mini_direct_canary_load_sequence_sha256 = self.load_sha
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        for name, value in self.previous_values.items():
            setattr(direct_route.settings, name, value)
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()
        self.tmp.cleanup()

    async def test_status_is_flag_safe_and_exposes_no_source_content_or_path(self) -> None:
        disabled = await self.client.get("/api/v1/swapmod-a1-mini-direct-canary/sequence-editor")
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()["enabled"])
        self.assertTrue(all(not sequence["actions"] for sequence in disabled.json()["sequences"]))

        direct_route.settings.farm_swapmod_a1mini_sequence_editor_enabled = True
        response = await self.client.get("/api/v1/swapmod-a1-mini-direct-canary/sequence-editor")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["sequences"][0]["actions"][0]["target"], "X-14")
        serialized = json.dumps(payload)
        self.assertNotIn("G1 ", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn("release.gcode", serialized)

    async def test_create_candidate_is_inactive_and_never_changes_active_source(self) -> None:
        direct_route.settings.farm_swapmod_a1mini_sequence_editor_enabled = True
        status = (await self.client.get("/api/v1/swapmod-a1-mini-direct-canary/sequence-editor")).json()
        release = status["sequences"][0]

        response = await self.client.post(
            "/api/v1/swapmod-a1-mini-direct-canary/sequence-versions",
            json={
                "step": "RELEASE_PLATE",
                "base_sha256": self.release_sha,
                "actions": [
                    {"action_id": action["action_id"], "feedrate": action["feedrate"] + 100}
                    for action in release["actions"]
                ],
            },
        )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertFalse(payload["active"])
        self.assertFalse(payload["activation_supported"])
        self.assertEqual(payload["review_status"], "PENDING_REVIEW")
        self.assertEqual((self.root / "release.gcode").read_text(encoding="utf-8"), self.release_text)
        self.assertEqual(len(list((self.root / ".bambuddy-swapmod-candidates").glob("*.gcode"))), 1)

    async def test_create_candidate_rejects_raw_content_and_path_fields(self) -> None:
        direct_route.settings.farm_swapmod_a1mini_sequence_editor_enabled = True
        response = await self.client.post(
            "/api/v1/swapmod-a1-mini-direct-canary/sequence-versions",
            json={
                "step": "RELEASE_PLATE",
                "base_sha256": self.release_sha,
                "actions": [],
                "raw_gcode": "G1 X1 F1",
                "sequence_path": "/tmp/unsafe.gcode",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertFalse((self.root / ".bambuddy-swapmod-candidates").exists())

    async def test_create_candidate_rejects_action_coordinate_override(self) -> None:
        direct_route.settings.farm_swapmod_a1mini_sequence_editor_enabled = True
        status = (await self.client.get("/api/v1/swapmod-a1-mini-direct-canary/sequence-editor")).json()
        action = status["sequences"][0]["actions"][0]

        response = await self.client.post(
            "/api/v1/swapmod-a1-mini-direct-canary/sequence-versions",
            json={
                "step": "RELEASE_PLATE",
                "base_sha256": self.release_sha,
                "actions": [
                    {
                        "action_id": action["action_id"],
                        "feedrate": action["feedrate"],
                        "target": "X999",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertFalse((self.root / ".bambuddy-swapmod-candidates").exists())

    async def test_create_candidate_rejects_string_feedrates(self) -> None:
        direct_route.settings.farm_swapmod_a1mini_sequence_editor_enabled = True
        status = (await self.client.get("/api/v1/swapmod-a1-mini-direct-canary/sequence-editor")).json()
        release = status["sequences"][0]

        response = await self.client.post(
            "/api/v1/swapmod-a1-mini-direct-canary/sequence-versions",
            json={
                "step": "RELEASE_PLATE",
                "base_sha256": self.release_sha,
                "actions": [
                    {"action_id": action["action_id"], "feedrate": str(action["feedrate"])}
                    for action in release["actions"]
                ],
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertFalse((self.root / ".bambuddy-swapmod-candidates").exists())

    async def test_create_candidate_fails_closed_while_direct_canary_is_armed(self) -> None:
        direct_route.settings.farm_swapmod_a1mini_sequence_editor_enabled = True
        status = (await self.client.get("/api/v1/swapmod-a1-mini-direct-canary/sequence-editor")).json()
        release = status["sequences"][0]
        direct_route.settings.farm_swapmod_a1mini_direct_canary_enabled = True

        response = await self.client.post(
            "/api/v1/swapmod-a1-mini-direct-canary/sequence-versions",
            json={
                "step": "RELEASE_PLATE",
                "base_sha256": self.release_sha,
                "actions": [
                    {"action_id": action["action_id"], "feedrate": action["feedrate"]} for action in release["actions"]
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "direct_canary_must_be_disarmed")
        self.assertFalse((self.root / ".bambuddy-swapmod-candidates").exists())


if __name__ == "__main__":
    unittest.main()
