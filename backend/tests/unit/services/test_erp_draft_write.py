from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

import httpx

from backend.app.services.erp_draft_write import (
    ERP_DRAFT_AUTH_FAILED,
    ERP_DRAFT_INVALID_PAYLOAD,
    ERP_DRAFT_RATE_LIMITED,
    ERP_DRAFT_TIMEOUT,
    ERP_DRAFT_UPSTREAM_ERROR,
    DraftWriteClientResult,
    ErpDraftWriteClient,
    ErpDraftWriteError,
    format_frappe_datetime,
)


def _client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def draft_payload(event_id: str = "evt-unit-0001") -> dict:
    return {
        "farm_event_id": event_id,
        "production_request_id": 101,
        "external_work_order_id": "WO-FAKE-0001",
        "production_item": "SKU-FAKE-001",
        "quantity_completed": 1,
        "completed_at": "2026-06-24T12:00:00Z",
    }


def draft_response(event_id: str = "evt-unit-0001", *, name: str = "FDR-UNIT-0001") -> dict:
    return {
        "data": {
            "name": name,
            "doctype": "Farm Draft Result",
            "docstatus": 0,
            "status": "Draft",
            "farm_event_id": event_id,
            "production_request_id": 101,
            "external_work_order_id": "WO-FAKE-0001",
            "production_item": "SKU-FAKE-001",
            "quantity_completed": 1,
        }
    }


class ErpDraftWriteClientTest(unittest.IsolatedAsyncioTestCase):
    def test_frappe_datetime_uses_configured_timezone_and_database_format(self) -> None:
        completed_at = datetime(2026, 7, 10, 0, 0, 0, tzinfo=timezone.utc)
        value = format_frappe_datetime(completed_at, timezone_name="Asia/Seoul")
        self.assertEqual(value, "2026-07-10 09:00:00")

    def test_frappe_datetime_treats_naive_input_as_utc(self) -> None:
        value = format_frappe_datetime(datetime(2026, 7, 10, 0, 0, 0), timezone_name="Asia/Seoul")
        self.assertEqual(value, "2026-07-10 09:00:00")

    def test_frappe_datetime_rejects_unknown_timezone(self) -> None:
        with self.assertRaises(ValueError):
            format_frappe_datetime(datetime.now(timezone.utc), timezone_name="Synthetic/Invalid")

    async def test_client_rejects_mismatched_event_and_idempotency_keys_without_request(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            raise AssertionError("ERP request must not be sent")

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        with self.assertRaises(ErpDraftWriteError) as ctx:
            await client.create_or_lookup_draft_result(draft_payload(), idempotency_key="different-event")

        self.assertEqual(ctx.exception.code, ERP_DRAFT_INVALID_PAYLOAD)
        self.assertFalse(ctx.exception.retryable)
        await http_client.aclose()

    async def test_client_creates_draft_with_idempotency_key_and_token_header(self) -> None:
        seen = {"methods": []}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["methods"].append(request.method)
            seen["url"] = str(request.url)
            seen["authorization"] = request.headers.get("authorization")
            seen["idempotency"] = request.headers.get("idempotency-key")
            if request.method == "GET":
                seen["filters"] = json.loads(request.url.params["filters"])
                seen["fields"] = json.loads(request.url.params["fields"])
                seen["limit"] = request.url.params["limit_page_length"]
                return httpx.Response(200, json={"data": []})
            return httpx.Response(200, json=draft_response())

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        result = await client.create_or_lookup_draft_result(draft_payload(), idempotency_key="evt-unit-0001")

        self.assertIsInstance(result, DraftWriteClientResult)
        self.assertEqual(result.document.name, "FDR-UNIT-0001")
        self.assertEqual(result.document.docstatus, 0)
        self.assertTrue(result.created)
        self.assertFalse(result.recovered_after_timeout)
        self.assertEqual(seen["methods"], ["GET", "POST"])
        self.assertEqual(seen["url"], "http://erp.test/api/resource/Farm%20Draft%20Result")
        self.assertEqual(seen["authorization"], "token synthetic-secret-token")
        self.assertEqual(seen["idempotency"], "evt-unit-0001")
        self.assertEqual(seen["filters"], [["farm_event_id", "=", "evt-unit-0001"]])
        self.assertIn("docstatus", seen["fields"])
        self.assertEqual(seen["limit"], "2")
        await http_client.aclose()

    async def test_existing_frappe_collection_result_avoids_create(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.method)
            return httpx.Response(200, json={"data": [draft_response()["data"]]})

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        result = await client.create_or_lookup_draft_result(draft_payload(), idempotency_key="evt-unit-0001")

        self.assertEqual(calls, ["GET"])
        self.assertFalse(result.created)
        self.assertEqual(result.document.name, "FDR-UNIT-0001")
        await http_client.aclose()

    async def test_timeout_after_create_uses_lookup_without_second_create(self) -> None:
        calls: list[str] = []
        lookup_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal lookup_count
            if request.method == "POST":
                calls.append("post")
                raise httpx.ReadTimeout("read timed out")
            calls.append("get")
            lookup_count += 1
            self.assertEqual(json.loads(request.url.params["filters"]), [["farm_event_id", "=", "evt-timeout-0001"]])
            if lookup_count == 1:
                return httpx.Response(200, json={"data": []})
            return httpx.Response(200, json={"data": [draft_response("evt-timeout-0001", name="FDR-UNIT-0002")["data"]]})

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        result = await client.create_or_lookup_draft_result(
            draft_payload("evt-timeout-0001"),
            idempotency_key="evt-timeout-0001",
        )

        self.assertEqual(calls, ["get", "post", "get"])
        self.assertEqual(result.document.name, "FDR-UNIT-0002")
        self.assertFalse(result.created)
        self.assertTrue(result.recovered_after_timeout)
        await http_client.aclose()

    async def test_timeout_followup_preserves_nonretryable_lookup_error(self) -> None:
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            if calls == 1:
                return httpx.Response(200, json={"data": []})
            if request.method == "POST":
                raise httpx.ReadTimeout("read timed out")
            return httpx.Response(401, json={"error": "expired token"})

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        with self.assertRaises(ErpDraftWriteError) as ctx:
            await client.create_or_lookup_draft_result(
                draft_payload("evt-timeout-auth"),
                idempotency_key="evt-timeout-auth",
            )

        self.assertEqual(ctx.exception.code, ERP_DRAFT_AUTH_FAILED)
        self.assertFalse(ctx.exception.retryable)
        await http_client.aclose()

    async def test_client_classifies_retryable_and_auth_errors_without_leaking_token(self) -> None:
        cases = [
            (401, ERP_DRAFT_AUTH_FAILED, 401, False),
            (429, ERP_DRAFT_RATE_LIMITED, 503, True),
            (500, ERP_DRAFT_UPSTREAM_ERROR, 502, True),
        ]
        for status_code, expected_code, expected_http_status, retryable in cases:
            with self.subTest(status_code=status_code):
                def handler(_request: httpx.Request) -> httpx.Response:
                    headers = {"Retry-After": "1"} if status_code == 429 else {}
                    return httpx.Response(status_code, json={"error": "synthetic-secret-token"}, headers=headers)

                http_client = _client_for(handler)
                client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

                with self.assertRaises(ErpDraftWriteError) as ctx:
                    await client.create_or_lookup_draft_result(draft_payload(), idempotency_key="evt-unit-0001")

                exc = ctx.exception
                self.assertEqual(exc.code, expected_code)
                self.assertEqual(exc.http_status, expected_http_status)
                self.assertIs(exc.retryable, retryable)
                self.assertNotIn("synthetic-secret-token", str(exc))
                await http_client.aclose()

    async def test_plain_timeout_without_lookup_result_is_retryable(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("read timed out")

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        with self.assertRaises(ErpDraftWriteError) as ctx:
            await client.create_or_lookup_draft_result(draft_payload("evt-timeout-missing"), idempotency_key="evt-timeout-missing")

        self.assertEqual(ctx.exception.code, ERP_DRAFT_TIMEOUT)
        self.assertEqual(ctx.exception.http_status, 504)
        self.assertTrue(ctx.exception.retryable)
        self.assertNotIn("synthetic-secret-token", str(ctx.exception))
        await http_client.aclose()

    async def test_invalid_erp_payload_is_safe_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(200, json={"data": []})
            return httpx.Response(200, json={"data": {"name": "FDR-BAD"}})

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        with self.assertRaises(ErpDraftWriteError) as ctx:
            await client.create_or_lookup_draft_result(draft_payload(), idempotency_key="evt-unit-0001")

        self.assertEqual(ctx.exception.code, ERP_DRAFT_INVALID_PAYLOAD)
        self.assertEqual(ctx.exception.http_status, 422)
        self.assertFalse(ctx.exception.retryable)
        await http_client.aclose()

    async def test_multiple_frappe_lookup_results_are_unsafe_failure(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            document = draft_response()["data"]
            return httpx.Response(200, json={"data": [document, {**document, "name": "FDR-UNIT-0002"}]})

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        with self.assertRaises(ErpDraftWriteError) as ctx:
            await client.lookup_draft_result("evt-unit-0001")

        self.assertEqual(ctx.exception.code, ERP_DRAFT_INVALID_PAYLOAD)
        self.assertFalse(ctx.exception.retryable)
        await http_client.aclose()


if __name__ == "__main__":
    unittest.main()
