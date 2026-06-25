from __future__ import annotations

import json as _json
import unittest
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
            return _json.loads(self.text)

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
            body = b"" if json is None else _json.dumps(json).encode("utf-8")
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

from backend.app.api.routes import printflow_canary as canary_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.erp_draft_write import ErpDraftWriteRecord
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.services.printflow_canary import READINESS_PASSED

REAL_CANARY_APPROVAL_PHRASE = "CONFIRM_REAL_PRINTFLOW_CANARY printer-fixture-001 job-fixture-001"


class PrintFlowCanaryApiTest(unittest.IsolatedAsyncioTestCase):
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

        self.previous_enabled = canary_route.settings.farm_printflow_canary_readiness_enabled
        self.previous_dry_run = canary_route.settings.farm_printflow_canary_dry_run
        self.previous_human_gate = canary_route.settings.farm_printflow_canary_human_approval_required
        self.previous_optional_settings: dict[str, object] = {}
        canary_route.settings.farm_printflow_canary_readiness_enabled = False
        canary_route.settings.farm_printflow_canary_dry_run = True
        canary_route.settings.farm_printflow_canary_human_approval_required = True
        canary_route.printflow_canary_service.clear()
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        canary_route.settings.farm_printflow_canary_readiness_enabled = self.previous_enabled
        canary_route.settings.farm_printflow_canary_dry_run = self.previous_dry_run
        canary_route.settings.farm_printflow_canary_human_approval_required = self.previous_human_gate
        for name, value in self.previous_optional_settings.items():
            setattr(canary_route.settings, name, value)
        canary_route.printflow_canary_service.clear()
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    async def count_rows(self, model) -> int:
        async with self.sessionmaker() as session:
            return (await session.execute(select(func.count(model.id)))).scalar_one()

    async def assert_no_control_rows(self) -> None:
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 0)

    def enable_canary(self) -> None:
        canary_route.settings.farm_printflow_canary_readiness_enabled = True

    def set_route_setting_if_present(self, name: str, value: object) -> None:
        if hasattr(canary_route.settings, name):
            self.previous_optional_settings.setdefault(name, getattr(canary_route.settings, name))
            setattr(canary_route.settings, name, value)

    def set_safe_real_canary_defaults_if_present(self) -> None:
        for name, value in {
            "farm_printflow_real_adapter_enabled": False,
            "farm_printflow_canary_single_printer_only": True,
            "farm_printflow_base_url": None,
            "farm_printflow_api_token": None,
        }.items():
            self.set_route_setting_if_present(name, value)

    def real_canary_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "idempotency_key": "real-canary-api-idempotency-001",
            "job_id": "job-fixture-001",
            "target_printer_ids": ["printer-fixture-001"],
            "dry_run": False,
            "audit_only": False,
            "operator_approved": True,
            "operator_approval_phrase": REAL_CANARY_APPROVAL_PHRASE,
        }
        payload.update(overrides)
        return payload

    async def test_readiness_api_disabled_by_default(self) -> None:
        response = await self.client.post(
            "/api/v1/printflow-canary/readiness-checks",
            json={"check_key": "disabled-check"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())
        await self.assert_no_control_rows()

    async def test_enabled_api_requires_human_approval_before_mock_probe(self) -> None:
        self.enable_canary()

        response = await self.client.post(
            "/api/v1/printflow-canary/readiness-checks",
            json={
                "check_key": "approval-required",
                "dry_run": True,
                "audit_only": True,
                "operator_approved": False,
                "mock_scenario": "ready",
            },
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "APPROVAL_REQUIRED")
        self.assertTrue(body["human_approval_required"])
        self.assertFalse(body["ready_for_canary"])
        self.assertIsNone(body["printer_action"])
        self.assertIsNone(body["queue_action"])
        self.assertIsNone(body["erp_action"])
        self.assertIsNone(body["obico_action"])
        self.assertIsNone(body["bed_action"])
        await self.assert_no_control_rows()

    async def test_enabled_api_passes_ready_mock_without_control_side_effects(self) -> None:
        self.enable_canary()

        response = await self.client.post(
            "/api/v1/printflow-canary/readiness-checks",
            json={
                "check_key": "ready-check",
                "dry_run": True,
                "audit_only": True,
                "operator_approved": True,
                "mock_scenario": "ready",
                "printer_alias": "printer-fixture-001",
                "cycle_alias": "cycle-fixture-001",
            },
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], READINESS_PASSED)
        self.assertTrue(body["ready_for_canary"])
        self.assertTrue(body["dry_run"])
        self.assertTrue(body["audit_only"])
        self.assertTrue(body["mock_only"])
        self.assertEqual(body["adapter_network_calls_made"], 0)
        self.assertEqual(body["adapter_hardware_calls_made"], 0)
        for effect, count in body["sentinels"].items():
            self.assertEqual(count, 0, effect)
        await self.assert_no_control_rows()

    async def test_enabled_api_rejects_non_dry_run_or_non_audit_requests(self) -> None:
        self.enable_canary()

        non_dry_run = await self.client.post(
            "/api/v1/printflow-canary/readiness-checks",
            json={"check_key": "unsafe-dry-run", "dry_run": False, "audit_only": True, "operator_approved": True},
        )
        non_audit = await self.client.post(
            "/api/v1/printflow-canary/readiness-checks",
            json={"check_key": "unsafe-audit", "dry_run": True, "audit_only": False, "operator_approved": True},
        )

        self.assertEqual(non_dry_run.status_code, 400)
        self.assertEqual(non_dry_run.json()["detail"]["code"], "dry_run_required")
        self.assertEqual(non_audit.status_code, 400)
        self.assertEqual(non_audit.json()["detail"]["code"], "audit_only_required")
        await self.assert_no_control_rows()

    async def test_enabled_api_rejects_when_global_dry_run_flag_is_disabled(self) -> None:
        self.enable_canary()
        canary_route.settings.farm_printflow_canary_dry_run = False

        response = await self.client.post(
            "/api/v1/printflow-canary/readiness-checks",
            json={
                "check_key": "global-dry-run-disabled",
                "dry_run": True,
                "audit_only": True,
                "operator_approved": True,
                "mock_scenario": "ready",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "dry_run_required")
        await self.assert_no_control_rows()

    async def test_real_canary_api_disabled_by_default_without_control_side_effects(self) -> None:
        response = await self.client.post(
            "/api/v1/printflow-canary/real-canary-runs",
            json=self.real_canary_payload(),
        )

        await self.assert_no_control_rows()
        self.assertEqual(response.status_code, 404)
        self.assertIn("real printflow canary is disabled", response.json()["detail"].lower())

    async def test_enabled_readiness_with_safe_real_defaults_blocks_without_real_adapter(self) -> None:
        self.enable_canary()
        self.set_safe_real_canary_defaults_if_present()

        with patch.object(
            canary_route,
            "printflow_real_canary_adapter_factory",
            side_effect=AssertionError("real PrintFlow adapter factory must not be called for blocked defaults"),
            create=True,
        ) as factory:
            response = await self.client.post(
                "/api/v1/printflow-canary/real-canary-runs",
                json=self.real_canary_payload(dry_run=True, audit_only=True),
            )

        await self.assert_no_control_rows()
        factory.assert_not_called()
        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "REAL_CANARY_BLOCKED")
        self.assertFalse(body["ready_for_canary"])
        self.assertIn("real_adapter_disabled", body["blocked_reasons"])
        self.assertIn("global_dry_run_enabled", body["blocked_reasons"])
        self.assertIn("request_dry_run", body["blocked_reasons"])
        self.assertIn("audit_only", body["blocked_reasons"])
        self.assertIsNone(body["printflow_action"])
        self.assertIsNone(body["printer_action"])
        self.assertIsNone(body["queue_action"])
        self.assertIsNone(body["scheduler_action"])
        self.assertIsNone(body["erp_action"])
        self.assertIsNone(body["obico_action"])
        self.assertIsNone(body["bed_action"])
        for effect, count in body["sentinels"].items():
            self.assertEqual(count, 0, effect)

    async def test_status_and_metrics_do_not_expose_secret_metadata(self) -> None:
        self.enable_canary()
        secret = "wp060-secret-not-for-output"

        response = await self.client.post(
            "/api/v1/printflow-canary/readiness-checks",
            json={
                "check_key": "secret-probe",
                "dry_run": True,
                "audit_only": True,
                "operator_approved": True,
                "mock_scenario": "ready",
                "metadata": {"access_token": secret},
            },
        )
        self.assertEqual(response.status_code, 202)

        status = await self.client.get("/api/v1/printflow-canary/status")
        metrics = await self.client.get("/api/v1/printflow-canary/metrics")
        exposed = status.text + "\n" + metrics.text

        self.assertEqual(status.status_code, 200)
        self.assertEqual(metrics.status_code, 200)
        self.assertIn("bambuddy_printflow_canary_readiness_checks_total", metrics.text)
        self.assertNotIn(secret, exposed)
        await self.assert_no_control_rows()


if __name__ == "__main__":
    unittest.main()
