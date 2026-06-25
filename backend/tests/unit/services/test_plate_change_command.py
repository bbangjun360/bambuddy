from __future__ import annotations

import unittest

from backend.app.services.plate_change_command import (
    APPROVAL_REQUIRED,
    DRY_RUN_COMMANDS_READY,
    PLATE_CHANGE_BLOCKED,
    PlateChangeCommandDryRunService,
    PlateChangeCommandError,
    required_plate_change_approval_phrase,
)


ACTION_FIELDS = (
    "printflow_action",
    "printer_action",
    "queue_action",
    "scheduler_action",
    "erp_action",
    "obico_action",
    "bed_action",
)

ALLOWED_A1_MINI_SEQUENCES = [
    "A1_MINI_PLATE_CHANGE_DRY_RUN",
    "A1_MINI_PLATE_CHANGE_CANDIDATE_V1",
]


class PlateChangeCommandDryRunServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PlateChangeCommandDryRunService()

    def request(self, **overrides: object) -> dict[str, object]:
        printer_id = str(overrides.get("printer_id", "printer-fixture-001"))
        command_sequence = str(overrides.get("command_sequence", "A1_MINI_PLATE_CHANGE_DRY_RUN"))
        request: dict[str, object] = {
            "idempotency_key": "plate-change-dry-run-001",
            "target_printer_ids": [printer_id],
            "command_sequence": command_sequence,
            "dry_run": True,
            "operator_approved": True,
            "operator_approval_phrase": required_plate_change_approval_phrase(printer_id, command_sequence),
        }
        request.update(overrides)
        request.pop("printer_id", None)
        return request

    def assert_no_side_effects(self, payload: dict[str, object]) -> None:
        for field in ACTION_FIELDS:
            with self.subTest(field=field):
                self.assertIsNone(payload[field])
        sentinels = payload["sentinels"]
        self.assertIsInstance(sentinels, dict)
        for effect, count in sentinels.items():
            with self.subTest(effect=effect):
                self.assertEqual(count, 0)

    def create(self, payload: dict[str, object]) -> dict[str, object]:
        return self.service.create_dry_run(
            payload,
            global_dry_run=True,
            human_approval_required=True,
            single_printer_only=True,
            allow_real_commands=False,
        )

    def test_approved_single_printer_dry_run_is_idempotent_and_never_ready_for_real_commands(self) -> None:
        payload = self.request()

        first = self.create(payload)
        second = self.create(payload)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], DRY_RUN_COMMANDS_READY)
        self.assertTrue(first["dry_run"])
        self.assertTrue(first["mock_only"])
        self.assertFalse(first["ready_for_real_command"])
        self.assertEqual(first["target_printer_id"], "printer-fixture-001")
        self.assertEqual(first["command_sequence"], "A1_MINI_PLATE_CHANGE_DRY_RUN")
        self.assertEqual(first["stored"], True)
        self.assertEqual(
            first["command_plan"],
            {
                "sequence_id": "A1_MINI_PLATE_CHANGE_DRY_RUN",
                "printer_model_family": "A1 mini",
                "commands_redacted_or_symbolic": [
                    {
                        "step": 1,
                        "symbolic_command": "NO_PRINTER_COMMAND_DRY_RUN_BOUNDARY",
                        "candidate": False,
                    }
                ],
                "requires_human_confirmation": True,
                "requires_single_printer": True,
                "real_execution_supported": False,
                "status": "PLAN_ONLY",
                "hardware_approval_status": "NOT_APPROVED_FOR_HARDWARE",
            },
        )
        self.assert_no_side_effects(first)

    def test_candidate_sequence_returns_symbolic_plan_without_real_execution_support(self) -> None:
        payload = self.request(
            idempotency_key="plate-change-candidate-001",
            command_sequence="A1_MINI_PLATE_CHANGE_CANDIDATE_V1",
        )

        result = self.create(payload)

        self.assertEqual(result["status"], DRY_RUN_COMMANDS_READY)
        plan = result["command_plan"]
        self.assertEqual(plan["sequence_id"], "A1_MINI_PLATE_CHANGE_CANDIDATE_V1")
        self.assertEqual(plan["printer_model_family"], "A1 mini")
        self.assertEqual(plan["status"], "DRY_RUN_PLANNED")
        self.assertTrue(plan["requires_human_confirmation"])
        self.assertTrue(plan["requires_single_printer"])
        self.assertFalse(plan["real_execution_supported"])
        self.assertEqual(plan["hardware_approval_status"], "NOT_APPROVED_FOR_HARDWARE")
        self.assertGreaterEqual(len(plan["commands_redacted_or_symbolic"]), 3)
        rendered_plan = str(plan)
        for raw_token in ("G28", "G1", "M400", "gcode_line"):
            with self.subTest(raw_token=raw_token):
                self.assertNotIn(raw_token, rendered_plan)
        self.assert_no_side_effects(result)

    def test_non_dry_run_request_is_rejected_without_storing_a_record(self) -> None:
        with self.assertRaises(PlateChangeCommandError) as raised:
            self.create(self.request(dry_run=False))

        self.assertEqual(raised.exception.code, "dry_run_required")
        self.assertEqual(self.service.status_snapshot()["dry_run_commands"], 0)

    def test_global_dry_run_must_remain_enabled(self) -> None:
        with self.assertRaises(PlateChangeCommandError) as raised:
            self.service.create_dry_run(
                self.request(),
                global_dry_run=False,
                human_approval_required=True,
                single_printer_only=True,
                allow_real_commands=False,
            )

        self.assertEqual(raised.exception.code, "dry_run_required")
        self.assertEqual(self.service.status_snapshot()["dry_run_commands"], 0)

    def test_missing_operator_approval_blocks_before_any_command_plan_is_stored(self) -> None:
        result = self.create(self.request(operator_approved=False, operator_approval_phrase=None))

        self.assertEqual(result["status"], APPROVAL_REQUIRED)
        self.assertFalse(result["stored"])
        self.assertFalse(result["ready_for_real_command"])
        self.assertIn("operator_approval_required", result["blocked_reasons"])
        self.assert_no_side_effects(result)
        self.assertEqual(self.service.status_snapshot()["dry_run_commands"], 0)

    def test_wrong_approval_phrase_blocks_before_any_command_plan_is_stored(self) -> None:
        result = self.create(self.request(operator_approval_phrase="CONFIRM SOMETHING ELSE"))

        self.assertEqual(result["status"], PLATE_CHANGE_BLOCKED)
        self.assertFalse(result["stored"])
        self.assertIn("approval_phrase_mismatch", result["blocked_reasons"])
        self.assert_no_side_effects(result)
        self.assertEqual(self.service.status_snapshot()["dry_run_commands"], 0)

    def test_multi_printer_input_blocks_before_any_command_plan_is_stored(self) -> None:
        result = self.create(
            self.request(
                target_printer_ids=["printer-fixture-001", "printer-fixture-002"],
                operator_approval_phrase="CONFIRM_DRY_RUN_PLATE_CHANGE printer-fixture-001 A1_MINI_PLATE_CHANGE_DRY_RUN",
            )
        )

        self.assertEqual(result["status"], PLATE_CHANGE_BLOCKED)
        self.assertFalse(result["stored"])
        self.assertIn("single_printer_required", result["blocked_reasons"])
        self.assert_no_side_effects(result)
        self.assertEqual(self.service.status_snapshot()["dry_run_commands"], 0)

    def test_status_snapshot_exposes_allowlist_and_zero_sentinels(self) -> None:
        self.create(self.request())

        status = self.service.status_snapshot()

        self.assertEqual(status["mode"], "DRY_RUN_ONLY")
        self.assertEqual(status["allowed_command_sequences"], ALLOWED_A1_MINI_SEQUENCES)
        self.assertEqual(status["dry_run_commands"], 1)
        for effect, count in status["sentinels"].items():
            self.assertEqual(count, 0, effect)


if __name__ == "__main__":
    unittest.main()
