from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from urllib.parse import quote
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORT = 19199
BASE = f"http://127.0.0.1:{PORT}"


def request(path: str, *, method: str = "GET", payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + quote(path, safe="/?=&"),
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=3) as result:
        return result.status, json.loads(result.read().decode())


def request_status(path: str, *, method: str = "GET", payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + quote(path, safe="/?=&"),
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as result:
            body = result.read().decode()
            return result.status, json.loads(body) if body else {}, dict(result.headers.items())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        return exc.code, json.loads(body) if body else {}, dict(exc.headers.items())


class MockServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = os.environ.copy()
        env["MOCK_PORT"] = str(PORT)
        cls.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "harness/mock_services.py")],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                status, _ = request("/health")
                if status == 200:
                    return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("mock service failed to start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)

    def setUp(self):
        request("/admin/reset", method="POST", payload={})

    def test_erp_work_order_detail_is_synthetic_and_read_only(self):
        status, payload = request("/erp/api/resource/Work Order/WO-HARNESS-0001", headers={"Authorization": "token fake-token"})

        self.assertEqual(status, 200)
        data = payload["data"]
        self.assertEqual(data["name"], "WO-HARNESS-0001")
        self.assertEqual(data["production_item"], "SKU-HARNESS")
        self.assertEqual(data["custom_artifact_reference"], "fixture-cube-v1")
        self.assertEqual(data["custom_profile_set_id"], "p1p-pla-fixture-v1")
        self.assertNotIn("access_code", json.dumps(payload).lower())
        self.assertNotIn("serial", json.dumps(payload).lower())

    def test_erp_work_order_missing_artifact_scenario(self):
        request("/admin/scenario", method="POST", payload={"scenario": "erp_missing_artifact"})

        status, payload = request("/erp/api/resource/Work Order/WO-HARNESS-0001", headers={"Authorization": "token fake-token"})

        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["custom_artifact_reference"], "missing-artifact-v1")

    def test_erp_work_order_missing_profile_scenario(self):
        request("/admin/scenario", method="POST", payload={"scenario": "erp_missing_profile"})

        status, payload = request("/erp/api/resource/Work Order/WO-HARNESS-0001", headers={"Authorization": "token fake-token"})

        self.assertEqual(status, 200)
        self.assertIsNone(payload["data"].get("custom_profile_set_id"))

    def test_erp_work_order_invalid_payload_scenario(self):
        request("/admin/scenario", method="POST", payload={"scenario": "erp_invalid_payload"})

        status, payload = request("/erp/api/resource/Work Order/WO-HARNESS-0001", headers={"Authorization": "token fake-token"})

        self.assertEqual(status, 200)
        self.assertNotIn("name", payload["data"])

    def test_erp_work_order_expired_token_scenario(self):
        request("/admin/scenario", method="POST", payload={"scenario": "erp_expired_token"})

        status, payload, _headers = request_status(
            "/erp/api/resource/Work Order/WO-HARNESS-0001",
            headers={"Authorization": "token expired-token"},
        )

        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "expired token")
        self.assertNotIn("expired-token", json.dumps(payload))

    def test_erp_rate_limit_scenario_has_retry_after(self):
        request("/admin/scenario", method="POST", payload={"scenario": "rate_limit"})

        status, _payload, headers = request_status("/erp/api/resource/Work Order/WO-HARNESS-0001")

        self.assertEqual(status, 429)
        self.assertEqual(headers.get("Retry-After"), "1")

    def test_erp_write_is_idempotent(self):
        headers = {"Idempotency-Key": "event-1"}
        _, first = request("/erp/api/resource/Stock Entry", method="POST", payload={}, headers=headers)
        _, second = request("/erp/api/resource/Stock Entry", method="POST", payload={}, headers=headers)
        self.assertEqual(first["data"]["name"], second["data"]["name"])
        self.assertEqual(first["data"]["docstatus"], 0)

    def test_bed_cycle_is_idempotent(self):
        payload = {"cycle_id": "cycle-1", "idempotency_key": "key-1", "dry_run": True}
        _, first = request("/printflow/v1/cycles", method="POST", payload=payload)
        _, second = request("/printflow/v1/cycles", method="POST", payload=payload)
        self.assertEqual(first["cycle_id"], second["cycle_id"])
        self.assertTrue(first["dry_run"])


if __name__ == "__main__":
    unittest.main()
