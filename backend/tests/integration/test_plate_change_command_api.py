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

from backend.app.api.routes import plate_change_command as plate_change_route
from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.models.bed_automation import BedAutomationCycle
from backend.app.models.erp_draft_write import ErpDraftWriteRecord
from backend.app.models.print_log import PrintLogEntry
from backend.app.models.print_queue import PrintQueueItem
from backend.app.services.plate_change_command import required_plate_change_approval_phrase


ACTION_FIELDS = (
    "printflow_action",
    "printer_action",
    "queue_action",
    "scheduler_action",
    "erp_action",
    "obico_action",
    "bed_action",
)

ALLOWED_A1_MINI_SEQUENCES = [
    "A1_MINI_PLATE_CHANGE_DRY_RUN",
    "A1_MINI_PLATE_CHANGE_CANDIDATE_V1",
]


class PlateChangeCommandApiTest(unittest.IsolatedAsyncioTestCase):
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
            "farm_plate_change_command_enabled": plate_change_route.settings.farm_plate_change_command_enabled,
            "farm_plate_change_command_dry_run": plate_change_route.settings.farm_plate_change_command_dry_run,
            "farm_plate_change_human_approval_required": (
                plate_change_route.settings.farm_plate_change_human_approval_required
            ),
            "farm_plate_change_single_printer_only": (
                plate_change_route.settings.farm_plate_change_single_printer_only
            ),
            "farm_plate_change_allow_real_commands": (
                plate_change_route.settings.farm_plate_change_allow_real_commands
            ),
            "farm_plate_change_transport_enabled": (
                plate_change_route.settings.farm_plate_change_transport_enabled
            ),
            "farm_plate_change_allow_real_transport": (
                plate_change_route.settings.farm_plate_change_allow_real_transport
            ),
            "farm_plate_change_transport_dry_run": (
                plate_change_route.settings.farm_plate_change_transport_dry_run
            ),
        }
        plate_change_route.settings.farm_plate_change_command_enabled = False
        plate_change_route.settings.farm_plate_change_command_dry_run = True
        plate_change_route.settings.farm_plate_change_human_approval_required = True
        plate_change_route.settings.farm_plate_change_single_printer_only = True
        plate_change_route.settings.farm_plate_change_allow_real_commands = False
        plate_change_route.settings.farm_plate_change_transport_enabled = False
        plate_change_route.settings.farm_plate_change_allow_real_transport = False
        plate_change_route.settings.farm_plate_change_transport_dry_run = True
        plate_change_route.plate_change_command_service.clear()
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        for name, value in self.previous_settings.items():
            setattr(plate_change_route.settings, name, value)
        plate_change_route.plate_change_command_service.clear()
        for patcher in reversed(self.patches):
            patcher.stop()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    def enable_boundary(self) -> None:
        plate_change_route.settings.farm_plate_change_command_enabled = True

    def payload(self, **overrides: object) -> dict[str, object]:
        printer_id = str(overrides.get("printer_id", "printer-fixture-001"))
        command_sequence = str(overrides.get("command_sequence", "A1_MINI_PLATE_CHANGE_DRY_RUN"))
        payload: dict[str, object] = {
            "idempotency_key": "plate-change-api-dry-run-001",
            "target_printer_ids": [printer_id],
            "command_sequence": command_sequence,
            "dry_run": True,
            "operator_approved": True,
            "operator_approval_phrase": required_plate_change_approval_phrase(printer_id, command_sequence),
        }
        payload.update(overrides)
        payload.pop("printer_id", None)
        return payload

    async def count_rows(self, model) -> int:
        async with self.sessionmaker() as session:
            return (await session.execute(select(func.count(model.id)))).scalar_one()

    async def assert_no_control_rows(self) -> None:
        self.assertEqual(await self.count_rows(PrintQueueItem), 0)
        self.assertEqual(await self.count_rows(PrintLogEntry), 0)
        self.assertEqual(await self.count_rows(BedAutomationCycle), 0)
        self.assertEqual(await self.count_rows(ErpDraftWriteRecord), 0)

    def assert_no_side_effects(self, body: dict[str, object]) -> None:
        for field in ACTION_FIELDS:
            with self.subTest(field=field):
                self.assertIsNone(body[field])
        sentinels = body["sentinels"]
        self.assertIsInstance(sentinels, dict)
        for effect, count in sentinels.items():
            with self.subTest(effect=effect):
                self.assertEqual(count, 0)

    def assert_transport_boundary_blocked(self, body: dict[str, object]) -> None:
        self.assertEqual(body.get("transport_mode"), "DRY_RUN")
        self.assertEqual(body.get("transport_status"), "BLOCKED_AUDIT_ONLY")
        self.assertFalse(body.get("real_transport_supported"))
        self.assertFalse(body.get("real_command_sent"))
        self.assertTrue(body.get("audit_required"))
        self.assertIn("transport_feature_disabled", body.get("blocked_reasons", []))
        self.assertIn("real_transport_not_allowed", body.get("blocked_reasons", []))
        self.assertIn("transport_dry_run_required", body.get("blocked_reasons", []))

    async def test_dry_run_command_api_disabled_by_default(self) -> None:
        response = await self.client.post("/api/v1/plate-change/dry-run-commands", json=self.payload())

        self.assertEqual(response.status_code, 404)
        self.assertIn("disabled", response.json()["detail"].lower())
        await self.assert_no_control_rows()

    async def test_status_reports_disabled_safe_defaults(self) -> None:
        response = await self.client.get("/api/v1/plate-change/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["enabled"])
        self.assertTrue(body["dry_run"])
        self.assertTrue(body["human_approval_required"])
        self.assertTrue(body["single_printer_only"])
        self.assertFalse(body["allow_real_commands"])
        self.assertEqual(body["allowed_command_sequences"], ALLOWED_A1_MINI_SEQUENCES)

    async def test_transport_status_reports_blocked_audit_only_defaults(self) -> None:
        response = await self.client.get("/api/v1/plate-change/transport-status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["transport_enabled"])
        self.assertFalse(body["allow_real_transport"])
        self.assertTrue(body["transport_dry_run"])
        self.assertEqual(body.get("transport_mode"), "DRY_RUN")
        self.assertEqual(body.get("transport_status"), "BLOCKED_AUDIT_ONLY")
        self.assertFalse(body.get("real_transport_supported"))
        self.assertFalse(body.get("real_command_sent"))
        self.assertTrue(body.get("audit_required"))
        self.assertIn("transport_feature_disabled", body.get("blocked_reasons", []))
        for effect, count in body["sentinels"].items():
            self.assertEqual(count, 0, effect)

    async def test_failure_path_reports_actual_transport_flag_state(self) -> None:
        self.enable_boundary()
        plate_change_route.settings.farm_plate_change_transport_enabled = True
        plate_change_route.settings.farm_plate_change_allow_real_transport = True
        plate_change_route.settings.farm_plate_change_transport_dry_run = False

        response = await self.client.post(
            "/api/v1/plate-change/dry-run-commands",
            json=self.payload(operator_approved=False, operator_approval_phrase=None),
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "APPROVAL_REQUIRED")
        self.assertIn("operator_approval_required", body.get("blocked_reasons", []))
        self.assertIn("real_transport_not_implemented", body.get("blocked_reasons", []))
        self.assertNotIn("transport_feature_disabled", body.get("blocked_reasons", []))
        self.assertNotIn("real_transport_not_allowed", body.get("blocked_reasons", []))
        self.assertNotIn("transport_dry_run_required", body.get("blocked_reasons", []))
        self.assertFalse(body.get("real_transport_supported"))
        self.assertFalse(body.get("real_command_sent"))
        self.assert_no_side_effects(body)
        await self.assert_no_control_rows()

    async def test_enabled_dry_run_requires_request_dry_run_true(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change/dry-run-commands",
            json=self.payload(dry_run=False),
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "dry_run_required")
        await self.assert_no_control_rows()

    async def test_enabled_dry_run_blocks_when_global_dry_run_gate_is_disabled(self) -> None:
        self.enable_boundary()
        plate_change_route.settings.farm_plate_change_command_dry_run = False

        response = await self.client.post("/api/v1/plate-change/dry-run-commands", json=self.payload())

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "dry_run_required")
        await self.assert_no_control_rows()

    async def test_missing_human_approval_blocks_without_side_effects(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change/dry-run-commands",
            json=self.payload(operator_approved=False, operator_approval_phrase=None),
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "APPROVAL_REQUIRED")
        self.assertFalse(body["stored"])
        self.assertIn("operator_approval_required", body.get("blocked_reasons", []))
        self.assert_transport_boundary_blocked(body)
        self.assert_no_side_effects(body)
        await self.assert_no_control_rows()

    async def test_wrong_human_approval_phrase_blocks_without_side_effects(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change/dry-run-commands",
            json=self.payload(operator_approval_phrase="WRONG PHRASE"),
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "PLATE_CHANGE_BLOCKED")
        self.assertFalse(body["stored"])
        self.assertIn("approval_phrase_mismatch", body.get("blocked_reasons", []))
        self.assert_transport_boundary_blocked(body)
        self.assert_no_side_effects(body)
        await self.assert_no_control_rows()

    async def test_disabled_human_approval_gate_blocks_without_side_effects(self) -> None:
        self.enable_boundary()
        plate_change_route.settings.farm_plate_change_human_approval_required = False

        response = await self.client.post(
            "/api/v1/plate-change/dry-run-commands",
            json=self.payload(operator_approved=False, operator_approval_phrase=None),
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "PLATE_CHANGE_BLOCKED")
        self.assertFalse(body["stored"])
        self.assertIn("human_approval_gate_required", body.get("blocked_reasons", []))
        self.assert_transport_boundary_blocked(body)
        self.assert_no_side_effects(body)
        await self.assert_no_control_rows()

    async def test_multi_printer_input_blocks_without_side_effects(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change/dry-run-commands",
            json=self.payload(
                target_printer_ids=["printer-fixture-001", "printer-fixture-002"],
                operator_approval_phrase="CONFIRM_DRY_RUN_PLATE_CHANGE printer-fixture-001 A1_MINI_PLATE_CHANGE_DRY_RUN",
            ),
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "PLATE_CHANGE_BLOCKED")
        self.assertIn("single_printer_required", body.get("blocked_reasons", []))
        self.assert_transport_boundary_blocked(body)
        self.assert_no_side_effects(body)
        await self.assert_no_control_rows()

    async def test_arbitrary_command_body_fields_are_rejected_by_schema(self) -> None:
        self.enable_boundary()
        for field_name in ("gcode", "command_text", "raw_command"):
            with self.subTest(field_name=field_name):
                payload = self.payload(idempotency_key=f"plate-change-api-{field_name}-001")
                payload[field_name] = "M999"

                response = await self.client.post("/api/v1/plate-change/dry-run-commands", json=payload)

                self.assertEqual(response.status_code, 422)
        await self.assert_no_control_rows()

    async def test_unknown_command_sequence_is_rejected_by_schema(self) -> None:
        self.enable_boundary()

        response = await self.client.post(
            "/api/v1/plate-change/dry-run-commands",
            json=self.payload(command_sequence="NOT_ALLOWLISTED_FOR_A1_MINI"),
        )

        self.assertEqual(response.status_code, 422)
        await self.assert_no_control_rows()

    async def test_approved_dry_run_returns_command_plan_only(self) -> None:
        self.enable_boundary()

        response = await self.client.post("/api/v1/plate-change/dry-run-commands", json=self.payload())

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "DRY_RUN_COMMANDS_READY")
        self.assertFalse(body["ready_for_real_command"])
        self.assert_transport_boundary_blocked(body)
        plan = body["command_plan"]
        self.assertEqual(plan["sequence_id"], "A1_MINI_PLATE_CHANGE_DRY_RUN")
        self.assertEqual(plan["printer_model_family"], "A1 mini")
        self.assertEqual(
            plan["commands_redacted_or_symbolic"][0]["symbolic_command"],
            "NO_PRINTER_COMMAND_DRY_RUN_BOUNDARY",
        )
        self.assertTrue(plan["requires_human_confirmation"])
        self.assertTrue(plan["requires_single_printer"])
        self.assertFalse(plan["real_execution_supported"])
        self.assertEqual(plan["status"], "PLAN_ONLY")
        rendered_body = response.text
        for raw_token in ("G28", "G1", "M400", "gcode_line"):
            with self.subTest(raw_token=raw_token):
                self.assertNotIn(raw_token, rendered_body)
        self.assert_no_side_effects(body)
        await self.assert_no_control_rows()

    async def test_approved_dry_run_does_not_call_printer_ftp_queue_scheduler_erp_obico_or_bed_paths(self) -> None:
        self.enable_boundary()

        with (
            patch(
                "backend.app.services.printer_manager.printer_manager.get_client",
                side_effect=AssertionError("printer manager must not be touched by dry-run boundary"),
            ) as get_client,
            patch(
                "backend.app.services.bambu_mqtt.BambuMQTTClient.start_print",
                side_effect=AssertionError("Bambu MQTT start_print must not run"),
            ) as mqtt_start_print,
            patch(
                "backend.app.services.bambu_mqtt.BambuMQTTClient.stop_print",
                side_effect=AssertionError("Bambu MQTT stop_print must not run"),
            ) as mqtt_stop_print,
            patch(
                "backend.app.services.bambu_mqtt.BambuMQTTClient.pause_print",
                side_effect=AssertionError("Bambu MQTT pause_print must not run"),
            ) as mqtt_pause_print,
            patch(
                "backend.app.services.bambu_mqtt.BambuMQTTClient.resume_print",
                side_effect=AssertionError("Bambu MQTT resume_print must not run"),
            ) as mqtt_resume_print,
            patch(
                "backend.app.services.bambu_mqtt.BambuMQTTClient.send_gcode",
                side_effect=AssertionError("Bambu MQTT G-code emitter must not run"),
            ) as mqtt_send_command,
            patch(
                "backend.app.services.printer_manager.printer_manager.start_print",
                side_effect=AssertionError("printer manager start_print must not run"),
            ) as manager_start_print,
            patch(
                "backend.app.services.printer_manager.printer_manager.stop_print",
                side_effect=AssertionError("printer manager stop_print must not run"),
            ) as manager_stop_print,
            patch(
                "backend.app.services.bambu_ftp.upload_file_async",
                side_effect=AssertionError("FTPS upload must not run"),
            ) as upload_file,
            patch(
                "backend.app.services.bambu_ftp.download_file_async",
                side_effect=AssertionError("FTPS download must not run"),
            ) as download_file,
            patch(
                "backend.app.services.bambu_ftp.delete_file_async",
                side_effect=AssertionError("FTPS delete must not run"),
            ) as delete_file,
            patch(
                "backend.app.services.print_scheduler.scheduler.check_queue",
                side_effect=AssertionError("scheduler must not run"),
            ) as check_queue,
            patch(
                "backend.app.services.background_dispatch.background_dispatch.dispatch_reprint_archive",
                side_effect=AssertionError("background dispatch must not run"),
            ) as dispatch_reprint,
            patch(
                "backend.app.services.erp_draft_write.create_draft_for_request",
                side_effect=AssertionError("ERP draft write must not run"),
            ) as erp_draft,
            patch(
                "backend.app.services.obico_shadow.obico_shadow_service.ingest_event",
                side_effect=AssertionError("Obico shadow mutation must not run"),
            ) as obico_ingest,
        ):
            response = await self.client.post("/api/v1/plate-change/dry-run-commands", json=self.payload())

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "DRY_RUN_COMMANDS_READY")
        self.assertFalse(body["ready_for_real_command"])
        self.assert_transport_boundary_blocked(body)
        self.assert_no_side_effects(body)
        get_client.assert_not_called()
        mqtt_start_print.assert_not_called()
        mqtt_stop_print.assert_not_called()
        mqtt_pause_print.assert_not_called()
        mqtt_resume_print.assert_not_called()
        mqtt_send_command.assert_not_called()
        manager_start_print.assert_not_called()
        manager_stop_print.assert_not_called()
        upload_file.assert_not_called()
        download_file.assert_not_called()
        delete_file.assert_not_called()
        check_queue.assert_not_called()
        dispatch_reprint.assert_not_called()
        erp_draft.assert_not_called()
        obico_ingest.assert_not_called()
        await self.assert_no_control_rows()


if __name__ == "__main__":
    unittest.main()
