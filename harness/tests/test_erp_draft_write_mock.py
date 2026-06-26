from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class MockErpDraftServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = _free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        env = os.environ.copy()
        env["MOCK_PORT"] = str(cls.port)
        cls.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "harness/mock_services.py")],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                status, _payload, _headers = cls.request_status("/health")
                if status == 200:
                    return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("mock service failed to start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)

    @classmethod
    def request_status(
        cls,
        path: str,
        *,
        method: str = "GET",
        payload: dict | None = None,
        headers: dict | None = None,
        timeout: float = 3.0,
    ):
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(
            cls.base + quote(path, safe="/?=&"),
            data=data,
            method=method,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as result:
                body = result.read().decode()
                return result.status, json.loads(body) if body else {}, dict(result.headers.items())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            return exc.code, json.loads(body) if body else {}, dict(exc.headers.items())

    def setUp(self):
        self.request_status("/admin/reset", method="POST", payload={})

    def _draft_payload(self, event_id: str = "evt-harness-0001") -> dict:
        return {
            "farm_event_id": event_id,
            "production_request_id": 101,
            "external_work_order_id": "WO-HARNESS-0001",
            "production_item": "SKU-HARNESS",
            "quantity_completed": 1,
            "completed_at": "2026-06-24T12:00:00Z",
        }

    def test_draft_create_is_idempotent_and_draft_only(self):
        headers = {"Idempotency-Key": "evt-harness-0001", "Authorization": "token fake-token"}

        first_status, first, _ = self.request_status(
            "/erp/api/resource/Farm Draft Result",
            method="POST",
            payload=self._draft_payload(),
            headers=headers,
        )
        second_status, second, _ = self.request_status(
            "/erp/api/resource/Farm Draft Result",
            method="POST",
            payload=self._draft_payload(),
            headers=headers,
        )
        state_status, state, _ = self.request_status("/admin/state")

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first["data"]["name"], second["data"]["name"])
        self.assertEqual(first["data"]["docstatus"], 0)
        self.assertEqual(first["data"]["status"], "Draft")
        self.assertEqual(first["data"]["farm_event_id"], "evt-harness-0001")
        self.assertEqual(state_status, 200)
        self.assertEqual(len(state["erp_draft_documents"]), 1)
        self.assertEqual(state["erp_submit_calls"], 0)
        self.assertEqual(state["erp_inventory_post_calls"], 0)
        self.assertEqual(state["erp_accounting_post_calls"], 0)
        self.assertNotIn("access_code", json.dumps(first).lower())
        self.assertNotIn("serial", json.dumps(first).lower())

    def test_timeout_after_create_can_be_looked_up_without_duplicate(self):
        self.request_status("/admin/scenario", method="POST", payload={"scenario": "erp_draft_timeout_after_create"})
        headers = {"Idempotency-Key": "evt-timeout-0001", "Authorization": "token fake-token"}

        with self.assertRaises(Exception):
            self.request_status(
                "/erp/api/resource/Farm Draft Result",
                method="POST",
                payload=self._draft_payload("evt-timeout-0001"),
                headers=headers,
                timeout=0.2,
            )

        lookup_status, lookup, _ = self.request_status(
            "/erp/api/resource/Farm Draft Result?farm_event_id=evt-timeout-0001",
            headers={"Authorization": "token fake-token"},
        )
        _state_status, state, _ = self.request_status("/admin/state")

        self.assertEqual(lookup_status, 200)
        self.assertEqual(lookup["data"]["farm_event_id"], "evt-timeout-0001")
        self.assertEqual(lookup["data"]["docstatus"], 0)
        self.assertEqual(len(state["erp_draft_documents"]), 1)

    def test_draft_failure_scenarios_are_deterministic(self):
        cases = [
            ("rate_limit", 429),
            ("http_500", 500),
            ("erp_expired_token", 401),
        ]
        for scenario, expected_status in cases:
            with self.subTest(scenario=scenario):
                self.request_status("/admin/reset", method="POST", payload={})
                self.request_status("/admin/scenario", method="POST", payload={"scenario": scenario})

                token = "expired-token" if scenario == "erp_expired_token" else "fake-token"
                status, payload, headers = self.request_status(
                    "/erp/api/resource/Farm Draft Result",
                    method="POST",
                    payload=self._draft_payload(f"evt-{scenario}"),
                    headers={"Idempotency-Key": f"evt-{scenario}", "Authorization": f"token {token}"},
                )

                self.assertEqual(status, expected_status)
                if scenario == "rate_limit":
                    self.assertEqual(headers.get("Retry-After"), "1")
                self.assertNotIn("expired-token", json.dumps(payload))

    def test_invalid_payload_and_reconciliation_mismatch_are_deterministic(self):
        self.request_status("/admin/scenario", method="POST", payload={"scenario": "erp_draft_invalid_payload"})
        status, payload, _ = self.request_status(
            "/erp/api/resource/Farm Draft Result",
            method="POST",
            payload=self._draft_payload("evt-invalid-0001"),
            headers={"Idempotency-Key": "evt-invalid-0001", "Authorization": "token fake-token"},
        )
        self.assertEqual(status, 200)
        self.assertNotIn("docstatus", payload["data"])

        self.request_status("/admin/reset", method="POST", payload={})
        self.request_status(
            "/erp/api/resource/Farm Draft Result",
            method="POST",
            payload=self._draft_payload("evt-mismatch-0001"),
            headers={"Idempotency-Key": "evt-mismatch-0001", "Authorization": "token fake-token"},
        )
        self.request_status("/admin/scenario", method="POST", payload={"scenario": "erp_draft_reconciliation_mismatch"})
        lookup_status, lookup, _ = self.request_status(
            "/erp/api/resource/Farm Draft Result?farm_event_id=evt-mismatch-0001",
            headers={"Authorization": "token fake-token"},
        )

        self.assertEqual(lookup_status, 200)
        self.assertEqual(lookup["data"]["farm_event_id"], "evt-mismatch-0001")
        self.assertEqual(lookup["data"]["quantity_completed"], 2)


if __name__ == "__main__":
    unittest.main()
