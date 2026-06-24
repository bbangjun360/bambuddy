from __future__ import annotations

import unittest

import httpx

from backend.app.services.erp_readonly import (
    ERP_AUTH_FAILED,
    ERP_RATE_LIMITED,
    ERP_TIMEOUT,
    ERP_UPSTREAM_ERROR,
    ErpReadOnlyClient,
    ErpReadOnlyError,
)


def _client_for(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class ErpReadOnlyClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_client_fetches_work_order_with_token_header(self) -> None:
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["authorization"] = request.headers.get("authorization")
            return httpx.Response(200, json={"data": {"name": "WO-FAKE-0001", "production_item": "SKU-FAKE", "qty": 1}})

        http_client = _client_for(handler)
        client = ErpReadOnlyClient("http://erp.test", "fake-token", http_client=http_client)

        payload = await client.fetch_work_order("WO-FAKE-0001")

        self.assertEqual(payload["name"], "WO-FAKE-0001")
        self.assertEqual(seen["url"], "http://erp.test/erp/api/resource/Work%20Order/WO-FAKE-0001")
        self.assertEqual(seen["authorization"], "token fake-token")
        await http_client.aclose()

    async def test_client_classifies_upstream_http_errors_without_leaking_token(self) -> None:
        cases = [
            (401, ERP_AUTH_FAILED, 401, False),
            (429, ERP_RATE_LIMITED, 503, True),
            (500, ERP_UPSTREAM_ERROR, 502, True),
        ]
        for status_code, expected_code, expected_http_status, retryable in cases:
            with self.subTest(status_code=status_code):
                def handler(_request: httpx.Request) -> httpx.Response:
                    headers = {"Retry-After": "1"} if status_code == 429 else {}
                    return httpx.Response(status_code, json={"error": "upstream"}, headers=headers)

                http_client = _client_for(handler)
                client = ErpReadOnlyClient("http://erp.test", "secret-token", http_client=http_client)

                with self.assertRaises(ErpReadOnlyError) as ctx:
                    await client.fetch_work_order("WO-FAKE-0001")

                exc = ctx.exception
                self.assertEqual(exc.code, expected_code)
                self.assertEqual(exc.http_status, expected_http_status)
                self.assertIs(exc.retryable, retryable)
                self.assertNotIn("secret-token", str(exc))
                await http_client.aclose()

    async def test_client_classifies_timeout_as_retryable_without_side_effects(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("read timed out")

        http_client = _client_for(handler)
        client = ErpReadOnlyClient("http://erp.test", "secret-token", http_client=http_client)

        with self.assertRaises(ErpReadOnlyError) as ctx:
            await client.fetch_work_order("WO-FAKE-0001")

        exc = ctx.exception
        self.assertEqual(exc.code, ERP_TIMEOUT)
        self.assertEqual(exc.http_status, 504)
        self.assertIs(exc.retryable, True)
        self.assertNotIn("secret-token", str(exc))
        await http_client.aclose()


if __name__ == "__main__":
    unittest.main()
