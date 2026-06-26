from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
PORT = 19250
BASE = f"http://127.0.0.1:{PORT}"


def request(path: str, *, method: str = "GET", payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BASE + quote(path, safe="/?=&"),
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=3) as result:
        body = result.read().decode("utf-8")
        return result.status, json.loads(body) if body else {}


def request_status(path: str, *, method: str = "GET", payload: dict | None = None):
    try:
        return request(path, method=method, payload=payload)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body) if body else {}


class BedAutomationMockServiceTest(unittest.TestCase):
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

    def test_printflow_cycle_success_is_idempotent_and_synthetic(self):
        payload = {"cycle_id": "cycle-success", "idempotency_key": "key-success", "dry_run": True}

        status, first = request("/printflow/v1/cycles", method="POST", payload=payload)
        _, second = request("/printflow/v1/cycles", method="POST", payload=payload)
        _, stored = request("/printflow/v1/cycles/cycle-success")

        self.assertEqual(status, 202)
        self.assertEqual(first, second)
        self.assertEqual(stored, first)
        self.assertEqual(first["status"], "completed")
        self.assertTrue(first["dry_run"])
        serialized = json.dumps(first).lower()
        for forbidden in ("access_code", "serial", "token", "password"):
            self.assertNotIn(forbidden, serialized)

    def test_printflow_cycle_failure_scenario_is_deterministic(self):
        request("/admin/scenario", method="POST", payload={"scenario": "bed_failure"})
        payload = {"cycle_id": "cycle-failure", "idempotency_key": "key-failure", "dry_run": True}

        _, first = request("/printflow/v1/cycles", method="POST", payload=payload)
        _, second = request("/printflow/v1/cycles", method="POST", payload=payload)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "failed")
        self.assertEqual(first["failure_class"], "simulated_failure")
        self.assertTrue(first["manual_review_required"])

    def test_printflow_cycle_timeout_scenario_is_deterministic(self):
        status, payload = request_status("/admin/scenario", method="POST", payload={"scenario": "bed_timeout"})
        self.assertEqual(status, 200, payload)

        _, cycle = request(
            "/printflow/v1/cycles",
            method="POST",
            payload={"cycle_id": "cycle-timeout", "idempotency_key": "key-timeout", "dry_run": True},
        )

        self.assertEqual(cycle["status"], "timeout")
        self.assertEqual(cycle["failure_class"], "simulated_timeout")
        self.assertTrue(cycle["manual_review_required"])

    def test_mock_metrics_include_bed_timeout_scenario_without_secret_values(self):
        request("/admin/scenario", method="POST", payload={"scenario": "bed_timeout"})

        with urllib.request.urlopen(f"{BASE}/metrics", timeout=3) as result:
            metrics = result.read().decode("utf-8")

        self.assertIn('farm_harness_mock_scenario_info{scenario="bed_timeout"} 1', metrics)
        for forbidden in ("access_code", "secret-token", "expired-token", "password", "printer_serial"):
            self.assertNotIn(forbidden, metrics.lower())


if __name__ == "__main__":
    unittest.main()
