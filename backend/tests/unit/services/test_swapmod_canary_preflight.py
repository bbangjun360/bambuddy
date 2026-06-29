from __future__ import annotations

import json
import unittest

from backend.app.services.swapmod_canary_preflight import SwapmodCanaryPreflightService


CHECKLIST = {
    "operator_present": True,
    "printer_visible": True,
    "emergency_stop_ready": True,
    "power_cutoff_ready": True,
    "bed_clear_confirmed": True,
    "correct_plate_confirmed": True,
    "no_other_job_running": True,
    "swapmod_hardware_installed": True,
    "plate_stack_loaded": True,
    "original_print_finished": True,
    "bed_state_reviewed": True,
}


def dry_run_plan(status: str = "SWAPMOD_DRY_RUN_READY") -> dict[str, object]:
    line_range_hash = "a" * 64
    return {
        "status": status,
        "mode": "DRY_RUN_ONLY",
        "expected_printer_model_family": "A1 Mini",
        "candidate_blocks": [
            {
                "candidate_id": "swapmod:inter_job_swap:aaaaaaaaaaaa",
                "candidate_kind": "inter_job_swap",
                "line_count": 42,
                "line_range_hash": line_range_hash,
                "command_family_counts": {"G1": 12, "G4": 4},
                "review_required": True,
                "raw_gcode_included": False,
                "real_execution_supported": False,
            }
        ],
        "sentinels": {"printer_commands": 0, "queue_dispatches": 0},
    }


class SwapmodCanaryPreflightServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SwapmodCanaryPreflightService()

    def request(self, **overrides: object) -> dict[str, object]:
        plan = dry_run_plan()
        candidate = plan["candidate_blocks"][0]
        body: dict[str, object] = {
            "dry_run_plan": plan,
            "candidate_id": candidate["candidate_id"],
            "target_printer_id": "101",
            "expected_printer_model_family": "A1 Mini",
            "checklist": dict(CHECKLIST),
            "operator_confirmation_phrase": (
                f"CONFIRM_SWAPMOD_CANARY_PREFLIGHT 101 {candidate['candidate_id']} "
                f"{candidate['line_range_hash']}"
            ),
        }
        body.update(overrides)
        return body

    def test_status_is_default_disabled_and_preflight_only(self) -> None:
        status = self.service.status_snapshot(enabled=False)

        self.assertFalse(status["enabled"])
        self.assertEqual(status["mode"], "CANARY_PREFLIGHT_ONLY")
        self.assertFalse(status["real_execution_supported"])
        self.assertFalse(status["printer_command_supported"])
        self.assertTrue(all(value == 0 for value in status["sentinels"].values()))

    def test_ready_package_returns_redacted_candidate_and_zero_sentinels(self) -> None:
        result = self.service.create_package(self.request(), enabled=True)

        self.assertEqual(result["status"], "SWAPMOD_CANARY_PREFLIGHT_READY")
        self.assertEqual(result["target_printer_id"], "101")
        self.assertEqual(result["selected_candidate"]["candidate_kind"], "inter_job_swap")
        self.assertFalse(result["real_execution_supported"])
        self.assertFalse(result["printer_command_supported"])
        self.assertFalse(result["printer_upload_supported"])
        self.assertFalse(result["printer_start_supported"])
        self.assertTrue(all(value == 0 for value in result["sentinels"].values()))
        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("G1 ", rendered)
        self.assertNotIn("access_code", rendered)

    def test_non_ready_plan_candidate_mismatch_non_a1_and_bad_phrase_require_review(self) -> None:
        cases = [
            self.request(dry_run_plan=dry_run_plan(status="SWAPMOD_DRY_RUN_REVIEW_REQUIRED")),
            self.request(candidate_id="missing-candidate"),
            self.request(expected_printer_model_family="A1"),
            self.request(operator_confirmation_phrase="CONFIRM_SWAPMOD_CANARY_PREFLIGHT wrong"),
        ]
        for body in cases:
            with self.subTest(candidate_id=body["candidate_id"]):
                result = self.service.create_package(body, enabled=True)
                self.assertEqual(result["status"], "SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED")
                self.assertFalse(result["real_execution_supported"])

    def test_incomplete_checklist_requires_review(self) -> None:
        checklist = dict(CHECKLIST)
        checklist["bed_state_reviewed"] = False

        result = self.service.create_package(self.request(checklist=checklist), enabled=True)

        self.assertEqual(result["status"], "SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED")
        self.assertIn("checklist_incomplete", result["review_reasons"])

    def test_raw_command_like_fields_in_dry_run_plan_require_review(self) -> None:
        plan = dry_run_plan()
        plan["raw_gcode"] = "G1 X999"

        result = self.service.create_package(self.request(dry_run_plan=plan), enabled=True)

        self.assertEqual(result["status"], "SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED")
        self.assertIn("raw_command_field_rejected", result["review_reasons"])


if __name__ == "__main__":
    unittest.main()
