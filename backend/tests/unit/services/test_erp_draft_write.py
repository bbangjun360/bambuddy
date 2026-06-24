from __future__ import annotations

import unittest

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
    async def test_client_creates_draft_with_idempotency_key_and_token_header(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["url"] = str(request.url)
            seen["authorization"] = request.headers.get("authorization")
            seen["idempotency"] = request.headers.get("idempotency-key")
            return httpx.Response(200, json=draft_response())

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        result = await client.create_or_lookup_draft_result(draft_payload(), idempotency_key="evt-unit-0001")

        self.assertIsInstance(result, DraftWriteClientResult)
        self.assertEqual(result.document.name, "FDR-UNIT-0001")
        self.assertEqual(result.document.docstatus, 0)
        self.assertTrue(result.created)
        self.assertFalse(result.recovered_after_timeout)
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["url"], "http://erp.test/erp/api/resource/Farm%20Draft%20Result")
        self.assertEqual(seen["authorization"], "token synthetic-secret-token")
        self.assertEqual(seen["idempotency"], "evt-unit-0001")
        await http_client.aclose()

    async def test_timeout_after_create_uses_lookup_without_second_create(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST":
                calls.append("post")
                raise httpx.ReadTimeout("read timed out")
            calls.append("get")
            self.assertIn("farm_event_id=evt-timeout-0001", str(request.url))
            return httpx.Response(200, json=draft_response("evt-timeout-0001", name="FDR-UNIT-0002"))

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        result = await client.create_or_lookup_draft_result(
            draft_payload("evt-timeout-0001"),
            idempotency_key="evt-timeout-0001",
        )

        self.assertEqual(calls, ["post", "get"])
        self.assertEqual(result.document.name, "FDR-UNIT-0002")
        self.assertFalse(result.created)
        self.assertTrue(result.recovered_after_timeout)
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
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": {"name": "FDR-BAD"}})

        http_client = _client_for(handler)
        client = ErpDraftWriteClient("http://erp.test", "synthetic-secret-token", http_client=http_client)

        with self.assertRaises(ErpDraftWriteError) as ctx:
            await client.create_or_lookup_draft_result(draft_payload(), idempotency_key="evt-unit-0001")

        self.assertEqual(ctx.exception.code, ERP_DRAFT_INVALID_PAYLOAD)
        self.assertEqual(ctx.exception.http_status, 422)
        self.assertFalse(ctx.exception.retryable)
        await http_client.aclose()


if __name__ == "__main__":
    unittest.main()
