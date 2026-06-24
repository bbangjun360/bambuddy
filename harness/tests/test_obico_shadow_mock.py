from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORT = 19270
BASE = f"http://127.0.0.1:{PORT}"


def request(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=3) as result:
        return json.loads(result.read().decode())


class ObicoShadowMockTest(unittest.TestCase):
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
                if request("/health")["status"] == "ok":
                    return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("mock service failed to start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)

    def test_shadow_event_scenarios_are_deterministic_and_synthetic(self) -> None:
        first = request("/obico-shadow/v1/events/spaghetti")
        second = request("/obico-shadow/v1/events/spaghetti")

        self.assertEqual(first, second)
        self.assertEqual(first["event_type"], "POSSIBLE_SPAGHETTI")
        self.assertEqual(first["printer_id"], "printer-fixture-001")
        serialized = json.dumps(first).lower()
        for forbidden in ("access_code", "token", "customer", "192.168.", "10.0.", "serial"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, serialized)

    def test_shadow_timeout_scenario_is_retryable_event_payload(self) -> None:
        payload = request("/obico-shadow/v1/events/timeout")

        self.assertEqual(payload["event_type"], "MONITORING_TIMEOUT")
        self.assertEqual(payload["event_id"], "shadow-timeout-0001")
        self.assertEqual(payload["metadata"], {"scenario": "timeout", "synthetic": True})


if __name__ == "__main__":
    unittest.main()
