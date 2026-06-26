from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

try:
    from httpx import ASGITransport, AsyncClient
except ModuleNotFoundError:
    class ASGITransport:
        def __init__(self, *, app):
            self.app = app

    class _FallbackResponse:
        def __init__(self, *, status_code: int, headers: list[tuple[bytes, bytes]], body: bytes) -> None:
            self.status_code = status_code
            self.headers = {key.decode("latin1").lower(): value.decode("latin1") for key, value in headers}
            self.content = body
            self.text = body.decode("utf-8")

        def json(self):
            return json.loads(self.text)

    class AsyncClient:
        def __init__(self, *, transport: ASGITransport, base_url: str) -> None:
            self.transport = transport
            self.base_url = base_url

        async def aclose(self) -> None:
            return None

        async def get(self, path: str) -> _FallbackResponse:
            return await self.request("GET", path)

        async def post(self, path: str, *, json: object | None = None) -> _FallbackResponse:
            return await self.request("POST", path, json=json)

        async def request(self, method: str, path: str, *, json: object | None = None) -> _FallbackResponse:
            parsed = urlsplit(path)
            body = b"" if json is None else globals()["json"].dumps(json).encode("utf-8")
            headers = [(b"host", b"test")]
            if body:
                headers.append((b"content-type", b"application/json"))

            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": parsed.path,
                "raw_path": parsed.path.encode("ascii"),
                "query_string": parsed.query.encode("ascii"),
                "headers": headers,
                "client": ("testclient", 50000),
                "server": ("test", 80),
            }
            response = {"status": 500, "headers": [], "body": bytearray()}
            request_sent = False

            async def receive():
                nonlocal request_sent
                if not request_sent:
                    request_sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                if message["type"] == "http.response.start":
                    response["status"] = message["status"]
                    response["headers"] = message.get("headers", [])
                elif message["type"] == "http.response.body":
                    response["body"].extend(message.get("body", b""))

            await self.transport.app(scope, receive, send)
            return _FallbackResponse(
                status_code=response["status"],
                headers=response["headers"],
                body=bytes(response["body"]),
            )

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.api.routes import plate_change_3mf_postprocess as postprocess_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.erp_draft_write import ErpDraftWriteRecord
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem


def _write_3mf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("3D/3dmodel.model", b"<model/>")
        zf.writestr("Metadata/project_settings.config", b'{"printer_model": "Bambu Lab A1 Mini"}')
        zf.writestr("Metadata/plate_1.gcode", b";LAYER_CHANGE\nG1 X1 Y1\nM400\n")


class PlateChange3mfPostprocessApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from backend.app.models import (  # noqa: F401
            api_key,
            auth_ephemeral,
            bed_automation,
            erp_draft_write,
            group,
            notification_template,
            print_log,
            print_queue,
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
            "farm_plate_change_3mf_postprocess_enabled": (
                postprocess_route.settings.farm_plate_change_3mf_postprocess_enabled
            ),
            "farm_plate_change_3mf_postprocess_dry_run": (
                postprocess_route.settings.farm_plate_change_3mf_postprocess_dry_run
            ),
            "farm_plate_change_3mf_allow_output_artifact": (
                postprocess_route.settings.farm_plate_change_3mf_allow_output_artifact
            ),
        }
        postprocess_route.settings.farm_plate_change_3mf_postprocess_enabled = False
        postprocess_route.settings.farm_plate_change_3mf_postprocess_dry_run = True
        postprocess_route.settings.farm_plate_change_3mf_allow_output_artifact = False

        self.controlled_root = (
            Path(tempfile.gettempdir())
            / "bambuddy-plate-change-3mf-postprocess"
            / f"api-test-{uuid.uuid4().hex}"
        )
        self.source = self.controlled_root / "inputs" / "api-secret-name.gcode.3mf"
        _write_3mf(self.source)

        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        for name, value in self.previous_settings.items():
            setattr(postprocess_route.settings, name, value)
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()
        shutil.rmtree(self.controlled_root, ignore_errors=True)

    def enable_boundary(self) -> None:
        postprocess_route.settings.farm_plate_change_3mf_postprocess_enabled = True

    async def count_rows(self, model) -> int:
        async with self.sessionmaker() as session:
            return (await session.execute(select(func.count(model.id)))).scalar_one()

    async def assert_no_control_rows(self) -> None:
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 0)

    def assert_no_side_effects(self, body: dict[str, object]) -> None:
        self.assertFalse(body["printer_upload_supported"])
        self.assertFalse(body["printer_start_supported"])
        self.assertFalse(body["real_execution_supported"])
        sentinels = body["sentinels"]
        self.assertIsInstance(sentinels, dict)
        for effect, count in sentinels.items():
            with self.subTest(effect=effect):
                self.assertEqual(count, 0)

    async def test_postprocess_plan_api_disabled_by_default(self) -> None:
        response = await self.client.post(
            "/api/v1/plate-change-3mf/postprocess-plans",
            json={"source_path": str(self.source), "dry_run": True},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())
        await self.assert_no_control_rows()

    async def test_status_reports_safe_defaults(self) -> None:
        response = await self.client.get("/api/v1/plate-change-3mf/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["enabled"])
        self.assertTrue(body["dry_run"])
        self.assertFalse(body["allow_output_artifact"])
        self.assertFalse(body["printer_upload_supported"])
        self.assertFalse(body["printer_start_supported"])
        self.assertFalse(body["real_execution_supported"])

    async def test_enabled_plan_returns_redacted_dry_run_only_response(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change-3mf/postprocess-plans",
            json={"source_path": str(self.source), "dry_run": True},
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertEqual(body["status"], "POSTPROCESS_PLAN_READY")
        self.assertEqual(body["internal_gcode_paths"], ["Metadata/plate_1.gcode"])
        self.assertEqual(body["detected_printer_model_family"], "A1 Mini")
        self.assertFalse(body["output_artifact_created"])
        self.assert_no_side_effects(body)
        rendered = json.dumps(body, sort_keys=True)
        self.assertNotIn("api-secret-name", rendered)
        self.assertNotIn("G1 X1", rendered)
        self.assertNotIn("M400", rendered)
        await self.assert_no_control_rows()

    async def test_raw_gcode_body_field_is_rejected_by_schema(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change-3mf/postprocess-plans",
            json={
                "source_path": str(self.source),
                "dry_run": True,
                "raw_gcode": "G1 X1 Y1",
            },
        )

        self.assertEqual(response.status_code, 422)
        await self.assert_no_control_rows()

    async def test_runtime_must_remain_dry_run(self) -> None:
        self.enable_boundary()
        postprocess_route.settings.farm_plate_change_3mf_postprocess_dry_run = False

        response = await self.client.post(
            "/api/v1/plate-change-3mf/postprocess-plans",
            json={"source_path": str(self.source), "dry_run": True},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "dry_run_required")
        await self.assert_no_control_rows()

    async def test_output_artifact_requires_setting_and_remains_under_controlled_temp(self) -> None:
        self.enable_boundary()

        blocked = await self.client.post(
            "/api/v1/plate-change-3mf/postprocess-plans",
            json={"source_path": str(self.source), "dry_run": True, "create_output_artifact": True},
        )

        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(blocked.json()["detail"]["code"], "output_artifact_not_allowed")
        self.assertFalse((self.controlled_root / "postprocess-output").exists())

        postprocess_route.settings.farm_plate_change_3mf_allow_output_artifact = True
        response = await self.client.post(
            "/api/v1/plate-change-3mf/postprocess-plans",
            json={"source_path": str(self.source), "dry_run": True, "create_output_artifact": True},
        )

        self.assertEqual(response.status_code, 202, response.text)
        body = response.json()
        self.assertTrue(body["output_artifact_created"])
        outputs = list((self.controlled_root / "inputs" / "postprocess-output").glob("*.3mf"))
        self.assertEqual(len(outputs), 1)
        self.assertTrue(outputs[0].resolve().is_relative_to(self.controlled_root.resolve()))
        await self.assert_no_control_rows()


if __name__ == "__main__":
    unittest.main()
