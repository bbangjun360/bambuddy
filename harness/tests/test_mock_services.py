from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
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
