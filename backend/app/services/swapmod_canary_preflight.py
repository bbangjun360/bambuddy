from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

SWAPMOD_CANARY_PREFLIGHT_READY = "SWAPMOD_CANARY_PREFLIGHT_READY"
SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED = "SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED"
SWAPMOD_CANARY_PREFLIGHT_MODE = "CANARY_PREFLIGHT_ONLY"
EXPECTED_MODEL_FAMILY = "A1 Mini"

FORBIDDEN_SIDE_EFFECTS = (
    "printer_uploads",
    "printer_starts",
    "printer_commands",
    "printer_manager_calls",
    "bambu_mqtt_commands",
    "ftps_calls",
    "queue_dispatches",
    "scheduler_dispatches",
    "erp_submit_calls",
    "erp_inventory_post_calls",
    "erp_accounting_post_calls",
    "obico_mutations",
    "bed_cycle_mutations",
    "restart_resume_attempts",
)

CHECKLIST_FIELDS = (
    "operator_present",
    "printer_visible",
    "emergency_stop_ready",
    "power_cutoff_ready",
    "bed_clear_confirmed",
    "correct_plate_confirmed",
    "no_other_job_running",
    "swapmod_hardware_installed",
    "plate_stack_loaded",
    "original_print_finished",
    "bed_state_reviewed",
)

RAW_COMMAND_FIELDS = {
    "raw_gcode",
    "gcode",
    "command",
    "commands",
    "send_gcode",
    "execute_gcode",
    "queue_action",
    "scheduler_action",
    "printer_action",
}

ALLOWED_CANDIDATE_KINDS = {"plate_load_only", "inter_job_swap", "final_swap"}

STOP_CONDITIONS = (
    "Stop before any printer upload, start, raw command, queue dispatch, or scheduler dispatch.",
    "Stop if the dry-run plan is not SWAPMOD_DRY_RUN_READY.",
    "Stop if the candidate id, line range hash, A1 Mini scope, checklist, or confirmation phrase does not match.",
    "Stop for manual review before any later hardware Work Package.",
    "Stop and require manual recovery after restart; preflight packages are not durable resume tokens.",
    "Stop before any next print until a later Work Package verifies bed READY.",
)

WORKFLOW_TRACE = (
    "RECEIVE_REDACTED_DRY_RUN_PLAN",
    "SELECT_ONE_CANDIDATE",
    "VERIFY_A1_MINI_SCOPE",
    "VERIFY_OPERATOR_CHECKLIST",
    "VERIFY_EXACT_CONFIRMATION",
    "PACKAGE_FOR_MANUAL_REVIEW",
    "STOP_BEFORE_REAL_EXECUTION",
)


class SwapmodCanaryPreflightError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class SwapmodCanaryPreflightService:
    def status_snapshot(
        self,
        *,
        enabled: bool = False,
        require_human_confirmation: bool = True,
        single_printer_only: bool = True,
    ) -> dict[str, Any]:
        return {
            "mode": SWAPMOD_CANARY_PREFLIGHT_MODE,
            "enabled": enabled,
            "require_human_confirmation": require_human_confirmation,
            "single_printer_only": single_printer_only,
            "expected_printer_model_family": EXPECTED_MODEL_FAMILY,
            "real_execution_supported": False,
            "printer_command_supported": False,
            "printer_upload_supported": False,
            "printer_start_supported": False,
            "queue_supported": False,
            "scheduler_supported": False,
            "batch_supported": False,
            "auto_retry_supported": False,
            "restart_resume_supported": False,
            "arbitrary_gcode_supported": False,
            "raw_gcode_returned": False,
            "human_review_required": True,
            "stop_conditions": list(STOP_CONDITIONS),
            "sentinels": _new_sentinels(),
        }

    def create_package(
        self,
        request: Mapping[str, Any],
        *,
        enabled: bool,
        require_human_confirmation: bool = True,
        single_printer_only: bool = True,
    ) -> dict[str, Any]:
        if not enabled:
            raise SwapmodCanaryPreflightError(
                "feature_disabled",
                "SwapMod canary preflight is disabled",
            )

        review_reasons: list[str] = []
        dry_run_plan = _mapping_or_empty(request.get("dry_run_plan"))
        candidate_id = _string_or_empty(request.get("candidate_id"))
        target_printer_id = _string_or_empty(request.get("target_printer_id"))
        expected_model_family = _string_or_empty(request.get("expected_printer_model_family"))
        checklist = _mapping_or_empty(request.get("checklist"))
        operator_phrase = _string_or_empty(request.get("operator_confirmation_phrase"))

        if _contains_raw_command_field(request):
            review_reasons.append("raw_command_field_rejected")
        if dry_run_plan.get("status") != "SWAPMOD_DRY_RUN_READY":
            review_reasons.append("dry_run_plan_not_ready")
        if dry_run_plan.get("mode") != "DRY_RUN_ONLY":
            review_reasons.append("dry_run_plan_mode_not_supported")
        if expected_model_family != EXPECTED_MODEL_FAMILY:
            review_reasons.append("a1_mini_scope_required")
        plan_model_family = dry_run_plan.get("expected_printer_model_family")
        if plan_model_family not in (None, "", EXPECTED_MODEL_FAMILY):
            review_reasons.append("dry_run_plan_model_family_mismatch")
        if single_printer_only and not target_printer_id:
            review_reasons.append("single_printer_required")

        candidates = [candidate for candidate in dry_run_plan.get("candidate_blocks", []) if isinstance(candidate, Mapping)]
        matching_candidates = [candidate for candidate in candidates if candidate.get("candidate_id") == candidate_id]
        selected_candidate = matching_candidates[0] if len(matching_candidates) == 1 else None
        if len(matching_candidates) != 1:
            review_reasons.append("candidate_id_not_found_exactly_once")
        elif not _candidate_metadata_valid(selected_candidate):
            review_reasons.append("candidate_metadata_incomplete")

        if not _checklist_complete(checklist):
            review_reasons.append("checklist_incomplete")

        line_range_hash = _string_or_empty(selected_candidate.get("line_range_hash") if selected_candidate else "")
        required_phrase = f"CONFIRM_SWAPMOD_CANARY_PREFLIGHT {target_printer_id} {candidate_id} {line_range_hash}"
        if require_human_confirmation and operator_phrase != required_phrase:
            review_reasons.append("confirmation_phrase_mismatch")

        sentinels = _new_sentinels()
        if not _sentinels_zero(dry_run_plan.get("sentinels")):
            review_reasons.append("dry_run_sentinels_not_zero")

        package_ready = not review_reasons
        package_id = _package_id(target_printer_id, candidate_id, line_range_hash) if package_ready else None
        return {
            "status": SWAPMOD_CANARY_PREFLIGHT_READY if package_ready else SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED,
            "mode": SWAPMOD_CANARY_PREFLIGHT_MODE,
            "package_id": package_id,
            "target_printer_id": target_printer_id,
            "expected_printer_model_family": EXPECTED_MODEL_FAMILY,
            "selected_candidate": _redacted_candidate(selected_candidate),
            "checklist_summary": _checklist_summary(checklist),
            "review_reasons": _dedupe(review_reasons),
            "required_confirmation_phrase": required_phrase if selected_candidate else None,
            "stop_conditions": list(STOP_CONDITIONS),
            "workflow_trace": [{"state": state, "preflight_only": True} for state in WORKFLOW_TRACE],
            "human_review_required": True,
            "real_execution_supported": False,
            "printer_command_supported": False,
            "printer_upload_supported": False,
            "printer_start_supported": False,
            "queue_supported": False,
            "scheduler_supported": False,
            "batch_supported": False,
            "auto_retry_supported": False,
            "restart_resume_supported": False,
            "arbitrary_gcode_supported": False,
            "raw_gcode_returned": False,
            "sentinels": sentinels,
        }


def _mapping_or_empty(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _string_or_empty(value: object) -> str:
    return value if isinstance(value, str) else ""


def _candidate_metadata_valid(candidate: Mapping[str, Any]) -> bool:
    candidate_kind = candidate.get("candidate_kind")
    line_range_hash = candidate.get("line_range_hash")
    line_count = candidate.get("line_count")
    counts = candidate.get("command_family_counts")
    return (
        candidate_kind in ALLOWED_CANDIDATE_KINDS
        and isinstance(line_range_hash, str)
        and re.fullmatch(r"[A-Fa-f0-9]{64}", line_range_hash) is not None
        and isinstance(line_count, int)
        and line_count > 0
        and isinstance(counts, Mapping)
        and candidate.get("raw_gcode_included") is False
        and candidate.get("real_execution_supported") is False
    )


def _redacted_candidate(candidate: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    counts = candidate.get("command_family_counts")
    safe_counts = dict(counts) if isinstance(counts, Mapping) else {}
    return {
        "candidate_id": candidate.get("candidate_id"),
        "candidate_kind": candidate.get("candidate_kind"),
        "line_count": candidate.get("line_count"),
        "line_range_hash": candidate.get("line_range_hash"),
        "command_family_counts": safe_counts,
        "raw_gcode_included": False,
        "real_execution_supported": False,
    }


def _checklist_complete(checklist: Mapping[str, Any]) -> bool:
    return all(checklist.get(field) is True for field in CHECKLIST_FIELDS)


def _checklist_summary(checklist: Mapping[str, Any]) -> dict[str, Any]:
    missing_or_false = [field for field in CHECKLIST_FIELDS if checklist.get(field) is not True]
    return {
        "required_fields": list(CHECKLIST_FIELDS),
        "all_required_fields_true": not missing_or_false,
        "missing_or_false_fields": missing_or_false,
    }


def _contains_raw_command_field(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in RAW_COMMAND_FIELDS:
                return True
            if _contains_raw_command_field(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_raw_command_field(item) for item in value)
    return False


def _sentinels_zero(value: object) -> bool:
    if not isinstance(value, Mapping):
        return True
    return all(item == 0 for item in value.values() if isinstance(item, int))


def _package_id(printer_id: str, candidate_id: str, line_range_hash: str) -> str:
    digest = hashlib.sha256(f"{printer_id}:{candidate_id}:{line_range_hash}".encode("utf-8")).hexdigest()
    return f"redacted-swapmod-canary-preflight-{digest[:16]}"


def _dedupe(reasons: list[str]) -> list[str]:
    deduped: list[str] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    return deduped


def _new_sentinels() -> dict[str, int]:
    return {effect: 0 for effect in FORBIDDEN_SIDE_EFFECTS}


swapmod_canary_preflight_service = SwapmodCanaryPreflightService()
