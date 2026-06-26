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
PORT = 19260
BASE = f"http://127.0.0.1:{PORT}"
READINESS_CHECK_PATH = "/printflow/v1/canary/readiness/check"
FORBIDDEN_SENTINELS = (
    "actuator_commands_sent",
    "queue_dispatches",
    "scheduler_dispatches",
    "erp_submit_calls",
    "erp_inventory_post_calls",
    "erp_accounting_post_calls",
    "obico_calls",
    "bed_cycle_mutations",
)


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


def assert_no_forbidden_side_effects(testcase: unittest.TestCase, sentinels: dict) -> None:
    for key in FORBIDDEN_SENTINELS:
        testcase.assertEqual(sentinels.get(key), 0, key)


class PrintFlowCanaryReadinessMockTest(unittest.TestCase):
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

    def test_canary_readiness_defaults_to_disabled_dry_run_audit_only(self):
        status, payload = request("/printflow/v1/canary/readiness")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["canary_enabled"])
        self.assertTrue(payload["dry_run"])
        self.assertTrue(payload["audit_only"])
        self.assertIn("feature_disabled", payload["blocked_reasons"])
        assert_no_forbidden_side_effects(self, payload["sentinels"])
        serialized = json.dumps(payload).lower()
        for forbidden in ("access_code", "serial", "token", "password", "api_key"):
            self.assertNotIn(forbidden, serialized)

    def test_canary_ready_check_is_idempotent_and_never_mutates_bed_cycles(self):
        request("/admin/scenario", method="POST", payload={"scenario": "printflow_canary_ready"})
        payload = {
            "idempotency_key": "wp060-check-1",
            "printer_id": "printer-fixture-001",
            "cycle_id": "cycle-fixture-001",
            "dry_run": True,
            "audit_only": True,
        }

        status, first = request(READINESS_CHECK_PATH, method="POST", payload=payload)
        _, second = request(READINESS_CHECK_PATH, method="POST", payload=payload)
        _, state = request("/admin/state")

        self.assertEqual(status, 202)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "ready")
        self.assertTrue(first["canary_enabled"])
        self.assertTrue(first["dry_run"])
        self.assertTrue(first["audit_only"])
        self.assertEqual(first["blocked_reasons"], [])
        assert_no_forbidden_side_effects(self, first["sentinels"])
        self.assertEqual(state["bed_cycles"], {})
        self.assertEqual(len(state["printflow_canary_checks"]), 1)

    def test_canary_readiness_rejects_non_dry_run_or_non_audit_checks(self):
        request("/admin/scenario", method="POST", payload={"scenario": "printflow_canary_ready"})

        non_dry_run_status, non_dry_run = request_status(
            READINESS_CHECK_PATH,
            method="POST",
            payload={"idempotency_key": "unsafe-1", "dry_run": False, "audit_only": True},
        )
        non_audit_status, non_audit = request_status(
            READINESS_CHECK_PATH,
            method="POST",
            payload={"idempotency_key": "unsafe-2", "dry_run": True, "audit_only": False},
        )
        _, state = request("/admin/state")

        self.assertEqual(non_dry_run_status, 400)
        self.assertEqual(non_dry_run["error"], "dry_run_required")
        self.assertEqual(non_audit_status, 400)
        self.assertEqual(non_audit["error"], "audit_only_required")
        self.assertEqual(state["printflow_canary_checks"], {})
        assert_no_forbidden_side_effects(self, state["printflow_canary_sentinels"])

    def test_canary_failure_scenarios_return_deterministic_manual_review_or_blockers(self):
        cases = {
            "printflow_canary_heartbeat_loss": ("blocked", "adapter_heartbeat_loss", False),
            "printflow_canary_camera_unavailable": ("blocked", "camera_unavailable", False),
            "printflow_canary_estop_active": ("manual_review", "e_stop_active", True),
            "printflow_canary_motion_timeout": ("manual_review", "motion_timeout", True),
            "printflow_canary_reply_lost": ("manual_review", "command_reply_lost", True),
            "printflow_canary_object_detected": ("manual_review", "object_detected", True),
        }

        for scenario, (expected_status, expected_failure, uncertain) in cases.items():
            with self.subTest(scenario=scenario):
                request("/admin/reset", method="POST", payload={})
                request("/admin/scenario", method="POST", payload={"scenario": scenario})

                status, payload = request(
                    READINESS_CHECK_PATH,
                    method="POST",
                    payload={
                        "idempotency_key": f"{scenario}-check",
                        "dry_run": True,
                        "audit_only": True,
                    },
                )

                self.assertEqual(status, 202)
                self.assertEqual(payload["status"], expected_status)
                self.assertEqual(payload["failure_class"], expected_failure)
                self.assertIn(expected_failure, payload["blocked_reasons"])
                self.assertEqual(payload["uncertain_physical_state"], uncertain)
                assert_no_forbidden_side_effects(self, payload["sentinels"])

    def test_canary_metrics_expose_readiness_and_forbidden_side_effect_sentinels(self):
        request("/admin/scenario", method="POST", payload={"scenario": "printflow_canary_ready"})
        request(
            READINESS_CHECK_PATH,
            method="POST",
            payload={"idempotency_key": "metrics-check", "dry_run": True, "audit_only": True},
        )

        with urllib.request.urlopen(f"{BASE}/metrics", timeout=3) as result:
            metrics = result.read().decode("utf-8")

        self.assertIn("farm_harness_printflow_canary_readiness_checks_total 1", metrics)
        self.assertIn('farm_harness_printflow_canary_status_total{status="ready"} 1', metrics)
        self.assertIn('farm_harness_printflow_forbidden_side_effects_total{effect="actuator_commands_sent"} 0', metrics)
        for forbidden in ("access_code", "secret-token", "expired-token", "password", "printer_serial"):
            self.assertNotIn(forbidden, metrics.lower())

    def test_makefile_exposes_printflow_canary_harness_targets(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("harness-printflow-canary:", makefile)
        self.assertIn("test-printflow-canary: harness-printflow-canary", makefile)


if __name__ == "__main__":
    unittest.main()
