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

REAL_CANARY_APPROVAL_PHRASE = "CONFIRM_REAL_PRINTFLOW_CANARY printer-fixture-001 job-fixture-001"


class FakeRealPrintFlowCanaryAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run_canary(
        self,
        *,
        job_id: str,
        target_printer_id: str,
        idempotency_key: str,
        dry_run: bool,
        audit_only: bool,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "job_id": job_id,
                "target_printer_id": target_printer_id,
                "idempotency_key": idempotency_key,
                "dry_run": dry_run,
                "audit_only": audit_only,
            }
        )
        return {
            "adapter_run_id": "fake-real-printflow-run-001",
            "status": "REAL_CANARY_DISPATCHED",
            "job_id": job_id,
            "target_printer_id": target_printer_id,
        }


class FailingRealPrintFlowCanaryAdapter(FakeRealPrintFlowCanaryAdapter):
    network_calls_made = 0
    hardware_calls_made = 0

    def run_canary(
        self,
        *,
        job_id: str,
        target_printer_id: str,
        idempotency_key: str,
        dry_run: bool,
        audit_only: bool,
    ) -> dict[str, object]:
        self.network_calls_made += 1
        self.hardware_calls_made += 1
        super().run_canary(
            job_id=job_id,
            target_printer_id=target_printer_id,
            idempotency_key=idempotency_key,
            dry_run=dry_run,
            audit_only=audit_only,
        )
        raise RuntimeError("simulated lost acknowledgement after request")


class RealPrintFlowAdapterFactorySpy:
    def __init__(self, *, adapter_cls=FakeRealPrintFlowCanaryAdapter) -> None:
        self.calls: list[dict[str, object]] = []
        self.adapters: list[FakeRealPrintFlowCanaryAdapter] = []
        self.adapter_cls = adapter_cls

    def __call__(self, *, base_url: str, api_token: str) -> FakeRealPrintFlowCanaryAdapter:
        self.calls.append({"base_url": base_url, "api_token": api_token})
        adapter = self.adapter_cls()
        self.adapters.append(adapter)
        return adapter


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


    def real_canary_request(self, **overrides: object) -> dict[str, object]:
        request: dict[str, object] = {
            "idempotency_key": "real-canary-idempotency-001",
            "job_id": "job-fixture-001",
            "target_printer_ids": ["printer-fixture-001"],
            "dry_run": False,
            "audit_only": False,
            "operator_approved": True,
            "operator_approval_phrase": REAL_CANARY_APPROVAL_PHRASE,
        }
        request.update(overrides)
        return request

    def real_canary_gates(self, **overrides: object) -> dict[str, object]:
        gates: dict[str, object] = {
            "real_adapter_enabled": True,
            "global_dry_run": False,
            "human_approval_required": True,
            "single_printer_only": True,
            "expected_approval_phrase": REAL_CANARY_APPROVAL_PHRASE,
            "base_url": "https://printflow.invalid",
            "api_token": "printflow-token-fixture",
        }
        gates.update(overrides)
        return gates

    def test_real_canary_blocks_before_constructing_adapter_when_any_gate_is_missing(self) -> None:
        cases = [
            (
                "real adapter disabled",
                {},
                {"real_adapter_enabled": False},
                "real_adapter_disabled",
            ),
            (
                "global dry-run true",
                {},
                {"global_dry_run": True},
                "global_dry_run_enabled",
            ),
            (
                "request dry-run true",
                {"dry_run": True},
                {},
                "request_dry_run",
            ),
            (
                "audit-only true",
                {"audit_only": True},
                {},
                "audit_only",
            ),
            (
                "human approval gate disabled",
                {},
                {"human_approval_required": False},
                "human_approval_gate_disabled",
            ),
            (
                "operator approval boolean false",
                {"operator_approved": False},
                {},
                "operator_approval_required",
            ),
            (
                "missing exact approval phrase",
                {"operator_approval_phrase": None},
                {},
                "approval_phrase_required",
            ),
            (
                "mismatched exact approval phrase",
                {"operator_approval_phrase": "I approve a different PrintFlow action"},
                {},
                "approval_phrase_mismatch",
            ),
            (
                "single-printer gate disabled",
                {},
                {"single_printer_only": False},
                "single_printer_gate_disabled",
            ),
            (
                "multiple target printers",
                {"target_printer_ids": ["printer-fixture-001", "printer-fixture-002"]},
                {},
                "single_printer_required",
            ),
            (
                "missing job id",
                {"job_id": ""},
                {},
                "missing_job_id",
            ),
            (
                "missing PrintFlow base URL",
                {},
                {"base_url": None},
                "missing_printflow_base_url",
            ),
            (
                "missing PrintFlow API token",
                {},
                {"api_token": None},
                "missing_printflow_api_token",
            ),
        ]

        for label, request_overrides, gate_overrides, expected_reason in cases:
            with self.subTest(label=label):
                factory = RealPrintFlowAdapterFactorySpy()

                result = self.service.create_real_canary(
                    self.real_canary_request(**request_overrides),
                    adapter_factory=factory,
                    **self.real_canary_gates(**gate_overrides),
                )

                self.assertEqual(result["status"], "REAL_CANARY_BLOCKED")
                self.assertFalse(result["ready_for_canary"])
                self.assertIn(expected_reason, result["blocked_reasons"])
                self.assertEqual(factory.calls, [])
                self.assertEqual(factory.adapters, [])
                self.assert_no_side_effects(result)

    def test_real_canary_all_gates_call_fake_once_and_replay_idempotency_key(self) -> None:
        factory = RealPrintFlowAdapterFactorySpy()
        request = self.real_canary_request()

        first = self.service.create_real_canary(
            request,
            adapter_factory=factory,
            **self.real_canary_gates(),
        )
        second = self.service.create_real_canary(
            request,
            adapter_factory=factory,
            **self.real_canary_gates(),
        )

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "REAL_CANARY_DISPATCHED")
        self.assertTrue(first["ready_for_canary"])
        self.assertEqual(
            factory.calls,
            [{"base_url": "https://printflow.invalid", "api_token": "printflow-token-fixture"}],
        )
        self.assertEqual(len(factory.adapters), 1)
        self.assertEqual(
            factory.adapters[0].calls,
            [
                {
                    "job_id": "job-fixture-001",
                    "target_printer_id": "printer-fixture-001",
                    "idempotency_key": "real-canary-idempotency-001",
                    "dry_run": False,
                    "audit_only": False,
                }
            ],
        )
        self.assert_no_side_effects(first)

    def test_real_canary_replay_rechecks_current_gates_and_payload(self) -> None:
        factory = RealPrintFlowAdapterFactorySpy()
        request = self.real_canary_request()
        first = self.service.create_real_canary(
            request,
            adapter_factory=factory,
            **self.real_canary_gates(),
        )

        missing_gate_replay = self.service.create_real_canary(
            {**request, "operator_approval_phrase": None},
            adapter_factory=factory,
            **self.real_canary_gates(real_adapter_enabled=False),
        )
        changed_payload_replay = self.service.create_real_canary(
            {
                **request,
                "job_id": "job-fixture-002",
                "operator_approval_phrase": "CONFIRM_REAL_PRINTFLOW_CANARY printer-fixture-001 job-fixture-002",
            },
            adapter_factory=factory,
            **self.real_canary_gates(
                expected_approval_phrase="CONFIRM_REAL_PRINTFLOW_CANARY printer-fixture-001 job-fixture-002"
            ),
        )

        self.assertEqual(first["status"], "REAL_CANARY_DISPATCHED")
        self.assertEqual(missing_gate_replay["status"], "REAL_CANARY_BLOCKED")
        self.assertFalse(missing_gate_replay["ready_for_canary"])
        self.assertIn("real_adapter_disabled", missing_gate_replay["blocked_reasons"])
        self.assertIn("approval_phrase_required", missing_gate_replay["blocked_reasons"])
        self.assertEqual(changed_payload_replay["status"], "REAL_CANARY_BLOCKED")
        self.assertFalse(changed_payload_replay["ready_for_canary"])
        self.assertIn("idempotency_payload_mismatch", changed_payload_replay["blocked_reasons"])
        self.assertEqual(len(factory.adapters), 1)
        self.assertEqual(len(factory.adapters[0].calls), 1)
        self.assert_no_side_effects(missing_gate_replay)
        self.assert_no_side_effects(changed_payload_replay)

    def test_real_canary_adapter_failure_is_manual_review_and_not_retried(self) -> None:
        factory = RealPrintFlowAdapterFactorySpy(adapter_cls=FailingRealPrintFlowCanaryAdapter)
        request = self.real_canary_request(idempotency_key="real-canary-failure-001")

        first = self.service.create_real_canary(
            request,
            adapter_factory=factory,
            **self.real_canary_gates(),
        )
        second = self.service.create_real_canary(
            request,
            adapter_factory=factory,
            **self.real_canary_gates(),
        )

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "MANUAL_REVIEW_REQUIRED")
        self.assertFalse(first["ready_for_canary"])
        self.assertTrue(first["manual_review_required"])
        self.assertTrue(first["uncertain_physical_state"])
        self.assertIn("real_adapter_exception", first["blocked_reasons"])
        self.assertEqual(first["adapter_network_calls_made"], 1)
        self.assertEqual(first["adapter_hardware_calls_made"], 1)
        self.assertEqual(len(factory.adapters), 1)
        self.assertEqual(len(factory.adapters[0].calls), 1)
        self.assert_no_side_effects(first)



if __name__ == "__main__":
    unittest.main()
