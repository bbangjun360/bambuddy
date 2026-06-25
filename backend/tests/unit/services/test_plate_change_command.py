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


class PlateChangeCommandDryRunServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PlateChangeCommandDryRunService()

    def request(self, **overrides: object) -> dict[str, object]:
        printer_id = str(overrides.get("printer_id", "printer-fixture-001"))
        command_sequence = str(overrides.get("command_sequence", "supervised_plate_change_v1"))
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
        self.assertEqual(first["command_sequence"], "supervised_plate_change_v1")
        self.assertEqual(first["stored"], True)
        self.assert_no_side_effects(first)

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
                operator_approval_phrase="CONFIRM_DRY_RUN_PLATE_CHANGE printer-fixture-001 supervised_plate_change_v1",
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
        self.assertEqual(status["allowed_command_sequences"], ["supervised_plate_change_v1"])
        self.assertEqual(status["dry_run_commands"], 1)
        for effect, count in status["sentinels"].items():
            self.assertEqual(count, 0, effect)


if __name__ == "__main__":
    unittest.main()
