from __future__ import annotations

import unittest

from backend.app.services.printflow_canary import (
    APPROVAL_REQUIRED,
    READINESS_BLOCKED,
    READINESS_PASSED,
    PrintFlowCanaryError,
    PrintFlowCanaryReadinessService,
    MockPrintFlowCanaryReadinessAdapter,
)


FORBIDDEN_ACTION_FIELDS = (
    "printflow_action",
    "printer_action",
    "queue_action",
    "scheduler_action",
    "erp_action",
    "obico_action",
    "bed_action",
)


class PrintFlowCanaryReadinessServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PrintFlowCanaryReadinessService()

    def assert_no_side_effects(self, payload: dict) -> None:
        for field in FORBIDDEN_ACTION_FIELDS:
            with self.subTest(field=field):
                self.assertIsNone(payload[field])
        for effect, count in payload["sentinels"].items():
            with self.subTest(effect=effect):
                self.assertEqual(count, 0)

    def test_human_approval_is_required_before_any_mock_probe(self) -> None:
        adapter = MockPrintFlowCanaryReadinessAdapter(scenario="ready")

        result = self.service.create_check(
            {
                "check_key": "approval-required",
                "dry_run": True,
                "audit_only": True,
                "operator_approved": False,
            },
            adapter=adapter,
        )

        self.assertEqual(result["status"], APPROVAL_REQUIRED)
        self.assertFalse(result["ready_for_canary"])
        self.assertTrue(result["human_approval_required"])
        self.assertFalse(result["operator_approved"])
        self.assertEqual(adapter.probes, [])
        self.assert_no_side_effects(result)

    def test_ready_check_is_dry_run_audit_only_idempotent_and_mock_only(self) -> None:
        adapter = MockPrintFlowCanaryReadinessAdapter(scenario="ready")
        request = {
            "check_key": "ready-check",
            "dry_run": True,
            "audit_only": True,
            "operator_approved": True,
            "printer_alias": "printer-fixture-001",
            "cycle_alias": "cycle-fixture-001",
        }

        first = self.service.create_check(request, adapter=adapter)
        second = self.service.create_check(request, adapter=adapter)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], READINESS_PASSED)
        self.assertTrue(first["ready_for_canary"])
        self.assertTrue(first["dry_run"])
        self.assertTrue(first["audit_only"])
        self.assertTrue(first["mock_only"])
        self.assertEqual(len(adapter.probes), 1)
        self.assertEqual(adapter.network_calls_made, 0)
        self.assertEqual(adapter.hardware_calls_made, 0)
        self.assert_no_side_effects(first)

    def test_non_dry_run_or_non_audit_request_is_rejected_without_probe(self) -> None:
        cases = [
            ({"check_key": "unsafe-dry-run", "dry_run": False, "audit_only": True, "operator_approved": True}, "dry_run_required"),
            ({"check_key": "unsafe-audit", "dry_run": True, "audit_only": False, "operator_approved": True}, "audit_only_required"),
        ]

        for request, code in cases:
            with self.subTest(code=code):
                adapter = MockPrintFlowCanaryReadinessAdapter(scenario="ready")
                with self.assertRaises(PrintFlowCanaryError) as raised:
                    self.service.create_check(request, adapter=adapter)

                self.assertEqual(raised.exception.code, code)
                self.assertEqual(adapter.probes, [])
                self.assertEqual(adapter.network_calls_made, 0)
                self.assertEqual(adapter.hardware_calls_made, 0)

    def test_uncertain_mock_scenarios_block_or_require_manual_review_without_side_effects(self) -> None:
        cases = {
            "heartbeat_loss": (READINESS_BLOCKED, "adapter_heartbeat_loss", False),
            "camera_unavailable": (READINESS_BLOCKED, "camera_unavailable", False),
            "estop_active": ("MANUAL_REVIEW_REQUIRED", "e_stop_active", True),
            "motion_timeout": ("MANUAL_REVIEW_REQUIRED", "motion_timeout", True),
            "reply_lost": ("MANUAL_REVIEW_REQUIRED", "command_reply_lost", True),
            "object_detected": ("MANUAL_REVIEW_REQUIRED", "object_detected", True),
        }

        for scenario, (expected_status, failure_class, uncertain) in cases.items():
            with self.subTest(scenario=scenario):
                service = PrintFlowCanaryReadinessService()
                adapter = MockPrintFlowCanaryReadinessAdapter(scenario=scenario)

                result = service.create_check(
                    {
                        "check_key": f"{scenario}-check",
                        "dry_run": True,
                        "audit_only": True,
                        "operator_approved": True,
                    },
                    adapter=adapter,
                )

                self.assertEqual(result["status"], expected_status)
                self.assertEqual(result["failure_class"], failure_class)
                self.assertIn(failure_class, result["blocked_reasons"])
                self.assertEqual(result["uncertain_physical_state"], uncertain)
                self.assert_no_side_effects(result)

    def test_metrics_keep_forbidden_side_effect_sentinels_at_zero(self) -> None:
        adapter = MockPrintFlowCanaryReadinessAdapter(scenario="ready")
        self.service.create_check(
            {
                "check_key": "metrics-check",
                "dry_run": True,
                "audit_only": True,
                "operator_approved": True,
            },
            adapter=adapter,
        )

        metrics = self.service.render_metrics()

        self.assertIn("bambuddy_printflow_canary_readiness_checks_total 1", metrics)
        self.assertIn('bambuddy_printflow_canary_status_total{status="READINESS_PASSED"} 1', metrics)
        self.assertIn('bambuddy_printflow_forbidden_side_effects_total{effect="printer_commands"} 0', metrics)
        for forbidden in ("access_code", "secret-token", "password", "printer_serial"):
            self.assertNotIn(forbidden, metrics.lower())


if __name__ == "__main__":
    unittest.main()
