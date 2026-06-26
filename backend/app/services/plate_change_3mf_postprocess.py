from __future__ import annotations

import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

from backend.app.services.slicer_3mf_convert import extract_source_printer_model

POSTPROCESS_PLAN_READY = "POSTPROCESS_PLAN_READY"
POSTPROCESS_UNSUPPORTED = "POSTPROCESS_UNSUPPORTED"
POSTPROCESS_MODE_DRY_RUN = "DRY_RUN_ONLY"
INSERTED_BLOCK_KIND = "SYMBOLIC_PLATE_CHANGE_REVIEW_ONLY"
REAL_SAMPLE_OUTPUT_MODE = "REAL_SAMPLE_OUTPUT_REVIEW_ONLY"
REAL_SAMPLE_REVIEW_MANIFEST_PATH = "Metadata/bambuddy_real_sample_output_review.json"
SYNTHETIC_INSERTION_POINT = "; BAMBUDDY_SYNTHETIC_PLATE_CHANGE_INSERTION_POINT"
PLATE_CHANGE_SYMBOLIC_BLOCK = (
    "; BAMBUDDY_PLATE_CHANGE_BLOCK_START\n"
    "; symbolic_step: PLATE_CHANGE_REVIEW_REQUIRED\n"
    "; symbolic_step: NO_REAL_GCODE_IN_WP_064_B\n"
    "; BAMBUDDY_PLATE_CHANGE_BLOCK_END\n"
)

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
)

SAFETY_NOTES = (
    "WP-064-A does not upload, start, send MQTT, use FTPS, or execute G-code",
    "WP-064-B inserts only a symbolic synthetic marker block for deterministic tests",
    "WP-064-C real-sample output review adds only a deterministic manifest member",
    "3MF post-processing output requires human diff review before any future use",
    "Output artifacts are disabled by default and remain prototype evidence only",
    "Printer upload/start remains out of scope for WP-064-C",
    "WP-064-D physical canary upload/start requires explicit flags and separate human confirmations",
)


class PlateChange3mfPostprocessError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PlateChange3mfPostprocessService:
    def create_plan(
        self,
        *,
        source_path: str | Path,
        enabled: bool,
        dry_run: bool,
        allow_output_artifact: bool,
        allowed_roots: Iterable[str | Path],
        request_dry_run: bool = True,
        create_output_artifact: bool = False,
        output_dir: str | Path | None = None,
        allow_real_sample_output: bool = False,
        real_sample_output_review: bool = False,
        real_sample_roots: Iterable[str | Path] | None = None,
        output_roots: Iterable[str | Path] | None = None,
    ) -> dict[str, Any]:
        if not enabled:
            raise PlateChange3mfPostprocessError(
                "feature_disabled",
                "Plate-change 3MF post-processing prototype is disabled",
            )
        if not dry_run or request_dry_run is not True:
            raise PlateChange3mfPostprocessError(
                "dry_run_required",
                "Plate-change 3MF post-processing is dry-run only",
            )

        real_roots = _resolved_optional_roots(real_sample_roots)
        if (
            create_output_artifact
            and allow_real_sample_output
            and not real_sample_output_review
            and real_roots
            and _path_is_under_roots(source_path, real_roots)
        ):
            raise PlateChange3mfPostprocessError(
                "real_sample_output_review_required",
                "Real-sample output review mode requires an explicit request flag",
            )

        if real_sample_output_review:
            if not create_output_artifact:
                raise PlateChange3mfPostprocessError(
                    "output_artifact_required",
                    "Real-sample output review mode requires output artifact creation",
                )
            if not allow_output_artifact:
                raise PlateChange3mfPostprocessError(
                    "output_artifact_not_allowed",
                    "3MF output artifact creation is disabled",
                )
            if not allow_real_sample_output:
                raise PlateChange3mfPostprocessError(
                    "real_sample_output_not_allowed",
                    "Real-sample 3MF output review mode is disabled",
                )
            sample_roots = real_roots or [default_real_sample_root()]
            review_output_roots = _resolved_optional_roots(output_roots) or [default_real_sample_output_root()]
            return _create_real_sample_output_review_plan(
                source_path=source_path,
                output_dir=output_dir,
                sample_roots=sample_roots,
                output_roots=review_output_roots,
            )

        if create_output_artifact and not allow_output_artifact:
            raise PlateChange3mfPostprocessError(
                "output_artifact_not_allowed",
                "3MF output artifact creation is disabled",
            )

        roots = _resolved_roots(allowed_roots)
        source = _resolve_allowed_source_path(source_path, roots)
        internal_listing, gcode_paths = _read_3mf_listing(source)
        source_bytes = source.read_bytes()
        source_sha256 = _sha256_bytes(source_bytes)
        detected_printer_model_family = extract_source_printer_model(source_bytes)
        candidate_blocks, insertion_points = _build_candidate_plan(source, gcode_paths)
        insertion_target, insertion_marker_present = _find_synthetic_insertion_target(source, gcode_paths)

        status = POSTPROCESS_PLAN_READY
        output_artifact_created = False
        output_artifact_root_redacted = None
        output_file_name_redacted = None
        output_sha256 = None
        insertion_performed = False
        inserted_block_kind = None
        preserved_member_count = len(internal_listing)
        modified_member_paths: list[str] = []
        deterministic_diff_summary = _deterministic_diff_summary_no_output(
            member_count=len(internal_listing),
            marker_present=insertion_marker_present,
        )

        if create_output_artifact:
            if insertion_target is None:
                status = POSTPROCESS_UNSUPPORTED
                deterministic_diff_summary = _deterministic_diff_summary_unsupported(
                    member_count=len(internal_listing),
                    marker_present=insertion_marker_present,
                )
            else:
                artifact_dir = _resolve_allowed_output_dir(
                    output_dir,
                    roots,
                    default_dir=source.parent / "postprocess-output",
                    root_description="controlled test/temp root",
                )
                artifact_path = _write_output_artifact(
                    source=source,
                    output_dir=artifact_dir,
                    source_sha256=source_sha256,
                    target_internal_gcode_path=insertion_target,
                )
                output_artifact_created = True
                output_artifact_root_redacted = "controlled-temp-output"
                output_file_name_redacted = _redacted_artifact_name(artifact_path)
                output_sha256 = _sha256_bytes(artifact_path.read_bytes())
                insertion_performed = True
                inserted_block_kind = INSERTED_BLOCK_KIND
                preserved_member_count = max(0, len(internal_listing) - 1)
                modified_member_paths = [insertion_target]
                deterministic_diff_summary = _deterministic_diff_summary_inserted(
                    target_internal_gcode_path=insertion_target,
                    preserved_member_count=preserved_member_count,
                    member_count=len(internal_listing),
                )

        result = {
            "status": status,
            "mode": POSTPROCESS_MODE_DRY_RUN,
            "source_file_name_redacted": _redacted_source_file_name(source),
            "source_name_redacted": _redacted_source_file_name(source),
            "internal_file_listing": internal_listing,
            "internal_gcode_paths": gcode_paths,
            "detected_printer_model_family": detected_printer_model_family,
            "candidate_blocks": candidate_blocks,
            "insertion_points": insertion_points,
            "postprocess_supported": False,
            "prototype_only": True,
            "output_artifact_created": output_artifact_created,
            "output_artifact_root_redacted": output_artifact_root_redacted,
            "output_artifact_file_name_redacted": output_file_name_redacted,
            "output_file_name_redacted": output_file_name_redacted,
            "output_name_redacted": output_file_name_redacted,
            "insertion_performed": insertion_performed,
            "insertion_marker_present": insertion_marker_present,
            "inserted_block_kind": inserted_block_kind,
            "source_sha256": source_sha256,
            "output_sha256": output_sha256,
            "deterministic_diff_summary": deterministic_diff_summary,
            "preserved_member_count": preserved_member_count,
            "modified_member_paths": modified_member_paths,
            "modified_internal_paths": modified_member_paths,
            "review_manifest_path": None,
            "real_sample_output_review": False,
            "human_review_required": True,
            "not_approved_for_printing": True,
            "real_gcode_inserted": False,
            "printer_upload_supported": False,
            "printer_start_supported": False,
            "real_execution_supported": False,
            "safety_notes": list(SAFETY_NOTES),
            "redacted_diff_summary": _redacted_diff_summary(gcode_paths, insertion_points),
            "sentinels": _new_sentinels(),
        }
        return result

    def status_snapshot(
        self,
        *,
        enabled: bool = False,
        dry_run: bool = True,
        allow_output_artifact: bool = False,
        allow_real_sample_output: bool = False,
    ) -> dict[str, Any]:
        return {
            "mode": POSTPROCESS_MODE_DRY_RUN,
            "enabled": enabled,
            "dry_run": dry_run,
            "allow_output_artifact": allow_output_artifact,
            "allow_real_sample_output": allow_real_sample_output,
            "postprocess_supported": False,
            "prototype_only": True,
            "output_artifact_created": False,
            "output_artifact_root_redacted": None,
            "output_artifact_file_name_redacted": None,
            "output_file_name_redacted": None,
            "insertion_performed": False,
            "insertion_marker_present": False,
            "inserted_block_kind": None,
            "source_sha256": None,
            "output_sha256": None,
            "deterministic_diff_summary": _deterministic_diff_summary_no_output(member_count=0, marker_present=False),
            "preserved_member_count": 0,
            "modified_member_paths": [],
            "modified_internal_paths": [],
            "review_manifest_path": None,
            "real_sample_output_review": False,
            "human_review_required": True,
            "not_approved_for_printing": True,
            "real_gcode_inserted": False,
            "printer_upload_supported": False,
            "printer_start_supported": False,
            "real_execution_supported": False,
            "safety_notes": list(SAFETY_NOTES),
            "sentinels": _new_sentinels(),
        }



CANARY_UPLOAD_RECORDED = "CANARY_UPLOAD_RECORDED"
CANARY_START_ATTEMPTED = "CANARY_START_ATTEMPTED"
CANARY_REQUIRED_CHECKLIST_FIELDS = (
    "operator_present",
    "printer_visible",
    "emergency_stop_ready",
    "power_cutoff_ready",
    "bed_clear_confirmed",
    "correct_plate_confirmed",
    "no_other_job_running",
    "fire_risk_area_clear",
)


class PlateChange3mfPhysicalCanaryService:
    def __init__(self) -> None:
        self._upload_record: dict[str, Any] | None = None
        self._start_attempts_used = 0

    def reset_for_tests(self) -> None:
        self._upload_record = None
        self._start_attempts_used = 0

    def canary_status(
        self,
        *,
        physical_canary_enabled: bool = False,
        allow_printer_upload: bool = False,
        allow_print_start: bool = False,
        single_printer_only: bool = True,
        require_human_confirmation: bool = True,
        disable_auto_retry: bool = True,
        max_starts: int = 1,
        output_roots: Iterable[str | Path] | None = None,
    ) -> dict[str, Any]:
        all_runtime_gates_enabled = _physical_canary_runtime_gates_enabled(
            physical_canary_enabled=physical_canary_enabled,
            allow_printer_upload=allow_printer_upload,
            allow_print_start=allow_print_start,
            single_printer_only=single_printer_only,
            require_human_confirmation=require_human_confirmation,
            disable_auto_retry=disable_auto_retry,
            max_starts=max_starts,
        )
        return {
            "mode": "SUPERVISED_PHYSICAL_CANARY",
            "physical_canary_enabled": physical_canary_enabled,
            "allow_printer_upload": allow_printer_upload,
            "allow_print_start": allow_print_start,
            "single_printer_only": single_printer_only,
            "require_human_confirmation": require_human_confirmation,
            "disable_auto_retry": disable_auto_retry,
            "max_starts": max_starts,
            "output_root_configured": bool(_resolved_optional_roots(output_roots)),
            "upload_recorded": self._upload_record is not None,
            "canary_printer_id": self._upload_record.get("printer_id") if self._upload_record else None,
            "artifact_sha256": self._upload_record.get("artifact_sha256") if self._upload_record else None,
            "start_attempts_used": self._start_attempts_used,
            "printer_upload_supported": all_runtime_gates_enabled,
            "printer_start_supported": all_runtime_gates_enabled and self._upload_record is not None,
            "real_execution_supported": all_runtime_gates_enabled,
            "queue_supported": False,
            "scheduler_supported": False,
            "batch_supported": False,
            "multi_printer_supported": False,
            "auto_retry_supported": False,
            "arbitrary_gcode_supported": False,
            "human_review_required": True,
            "human_supervision_required": True,
            "sentinels": _new_sentinels(),
        }

    async def canary_upload(
        self,
        request: dict[str, Any],
        *,
        printer_ops: Any,
        physical_canary_enabled: bool,
        allow_printer_upload: bool,
        allow_print_start: bool,
        single_printer_only: bool,
        require_human_confirmation: bool,
        disable_auto_retry: bool,
        max_starts: int,
        output_roots: Iterable[str | Path],
    ) -> dict[str, Any]:
        _require_physical_canary_gates(
            physical_canary_enabled=physical_canary_enabled,
            allow_printer_upload=allow_printer_upload,
            allow_print_start=allow_print_start,
            single_printer_only=single_printer_only,
            require_human_confirmation=require_human_confirmation,
            disable_auto_retry=disable_auto_retry,
            max_starts=max_starts,
        )
        printer_id = _single_canary_printer_id(request, single_printer_only=single_printer_only)
        artifact_path = _resolve_canary_artifact_path(request.get("artifact_path"), output_roots)
        artifact_sha256 = _validated_artifact_sha256(request.get("artifact_sha256"), artifact_path)
        _require_confirmation_phrase(
            request.get("operator_confirmation_phrase"),
            expected=f"CONFIRM_UPLOAD_REVIEWED_3MF {printer_id} {artifact_sha256}",
        )
        if self._upload_record is not None:
            raise PlateChange3mfPostprocessError(
                "single_artifact_required",
                "The supervised physical canary already has one uploaded artifact recorded",
            )

        try:
            remote_path = await printer_ops.upload_artifact(printer_id, artifact_path)
        except PlateChange3mfPostprocessError:
            raise
        except Exception as exc:
            raise PlateChange3mfPostprocessError("printer_upload_failed", "Canary printer upload failed") from exc
        if not remote_path:
            raise PlateChange3mfPostprocessError("printer_upload_failed", "Canary printer upload failed")

        self._upload_record = {
            "printer_id": printer_id,
            "artifact_sha256": artifact_sha256,
            "artifact_path": str(artifact_path),
            "artifact_name": artifact_path.name,
            "remote_path": str(remote_path),
        }
        self._start_attempts_used = 0
        return {
            "status": CANARY_UPLOAD_RECORDED,
            "mode": "SUPERVISED_PHYSICAL_CANARY",
            "printer_id": printer_id,
            "artifact_sha256": artifact_sha256,
            "artifact_file_name_redacted": _redacted_artifact_name(artifact_path),
            "remote_path_redacted": "redacted-printer-path",
            "upload_recorded": True,
            "start_attempts_used": self._start_attempts_used,
            "printer_upload_supported": True,
            "printer_start_supported": allow_print_start,
            "real_execution_supported": True,
            "queue_supported": False,
            "scheduler_supported": False,
            "batch_supported": False,
            "multi_printer_supported": False,
            "auto_retry_supported": False,
            "arbitrary_gcode_supported": False,
            "human_supervision_required": True,
            "sentinels": _new_sentinels(),
        }

    async def canary_start(
        self,
        request: dict[str, Any],
        *,
        printer_ops: Any,
        printer_state: Any,
        physical_canary_enabled: bool,
        allow_printer_upload: bool,
        allow_print_start: bool,
        single_printer_only: bool,
        require_human_confirmation: bool,
        disable_auto_retry: bool,
        max_starts: int,
        output_roots: Iterable[str | Path],
    ) -> dict[str, Any]:
        _require_physical_canary_gates(
            physical_canary_enabled=physical_canary_enabled,
            allow_printer_upload=allow_printer_upload,
            allow_print_start=allow_print_start,
            single_printer_only=single_printer_only,
            require_human_confirmation=require_human_confirmation,
            disable_auto_retry=disable_auto_retry,
            max_starts=max_starts,
        )
        if self._upload_record is None:
            raise PlateChange3mfPostprocessError(
                "prior_upload_required",
                "Print start requires a prior successful supervised canary upload record",
            )
        printer_id = _single_canary_printer_id(request, single_printer_only=single_printer_only)
        artifact_path = _resolve_canary_artifact_path(request.get("artifact_path"), output_roots)
        artifact_sha256 = _validated_artifact_sha256(request.get("artifact_sha256"), artifact_path)
        if (
            self._upload_record.get("printer_id") != printer_id
            or self._upload_record.get("artifact_sha256") != artifact_sha256
            or self._upload_record.get("artifact_path") != str(artifact_path)
        ):
            raise PlateChange3mfPostprocessError(
                "prior_upload_required",
                "Print start request must match the prior successful supervised canary upload record",
            )
        _require_confirmation_phrase(
            request.get("operator_confirmation_phrase"),
            expected=f"CONFIRM_START_REVIEWED_3MF {printer_id} {artifact_sha256}",
        )
        _require_canary_checklist(request.get("checklist"))
        if self._start_attempts_used >= max_starts:
            raise PlateChange3mfPostprocessError(
                "max_start_attempts_reached",
                "The supervised physical canary start attempt has already been used",
            )
        _require_known_idle_printer_state(printer_state)

        self._start_attempts_used += 1
        try:
            started = await printer_ops.start_print(printer_id, str(self._upload_record["remote_path"]))
        except PlateChange3mfPostprocessError:
            raise
        except Exception as exc:
            raise PlateChange3mfPostprocessError("printer_start_failed", "Canary print start failed") from exc
        if not started:
            raise PlateChange3mfPostprocessError("printer_start_failed", "Canary print start failed")

        return {
            "status": CANARY_START_ATTEMPTED,
            "mode": "SUPERVISED_PHYSICAL_CANARY",
            "printer_id": printer_id,
            "artifact_sha256": artifact_sha256,
            "artifact_file_name_redacted": _redacted_artifact_name(artifact_path),
            "remote_path_redacted": "redacted-printer-path",
            "start_attempts_used": self._start_attempts_used,
            "max_starts": max_starts,
            "printer_upload_supported": True,
            "printer_start_supported": True,
            "real_execution_supported": True,
            "queue_supported": False,
            "scheduler_supported": False,
            "batch_supported": False,
            "multi_printer_supported": False,
            "auto_retry_supported": False,
            "arbitrary_gcode_supported": False,
            "human_supervision_required": True,
            "sentinels": _new_sentinels(),
        }


def default_controlled_roots(base_dir: str | Path | None = None) -> list[Path]:
    _ = base_dir
    return [Path(tempfile.gettempdir()) / "bambuddy-plate-change-3mf-postprocess"]


def default_real_sample_root() -> Path:
    return Path.home() / "workspace" / "plate-change-samples"


def default_real_sample_output_root() -> Path:
    return Path.home() / "workspace" / "plate-change-outputs"


def _resolved_roots(allowed_roots: Iterable[str | Path]) -> list[Path]:
    roots = _resolved_optional_roots(allowed_roots)
    if not roots:
        raise PlateChange3mfPostprocessError(
            "controlled_root_required",
            "At least one controlled test/temp root is required",
        )
    return roots


def _resolved_optional_roots(allowed_roots: Iterable[str | Path] | None) -> list[Path]:
    if allowed_roots is None:
        return []
    roots: list[Path] = []
    for root in allowed_roots:
        if root is None:
            continue
        roots.append(Path(root).expanduser().resolve())
    return roots


def _path_is_under_roots(path: str | Path, roots: list[Path]) -> bool:
    candidate = Path(path).expanduser().resolve()
    return any(candidate.is_relative_to(root) for root in roots)


def _resolve_allowed_source_path(
    source_path: str | Path,
    roots: list[Path],
    *,
    root_description: str = "controlled test/temp root",
) -> Path:
    source = Path(source_path).expanduser().resolve()
    if not source.name.lower().endswith(".3mf"):
        raise PlateChange3mfPostprocessError(
            "unsupported_source_file",
            "Only .3mf or .gcode.3mf ZIP artifacts are accepted",
        )
    if not any(source.is_relative_to(root) for root in roots):
        raise PlateChange3mfPostprocessError(
            "source_path_not_allowed",
            f"Source path must be inside a {root_description}",
        )
    if not source.is_file():
        raise PlateChange3mfPostprocessError("source_not_found", "Source 3MF artifact was not found")
    return source


def _resolve_allowed_output_dir(
    output_dir: str | Path | None,
    roots: list[Path],
    *,
    default_dir: Path,
    root_description: str,
    block_repo_paths: bool = False,
) -> Path:
    candidate = Path(output_dir).expanduser().resolve() if output_dir is not None else default_dir.resolve()
    if block_repo_paths and _path_is_repo_relative(candidate):
        raise PlateChange3mfPostprocessError(
            "repo_output_path_not_allowed",
            "Output artifact directory must not be inside the repository",
        )
    if not any(candidate.is_relative_to(root) for root in roots):
        raise PlateChange3mfPostprocessError(
            "output_path_not_allowed",
            f"Output artifact directory must be inside a {root_description}",
        )
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _path_is_repo_relative(path: Path) -> bool:
    repo_root = Path(__file__).resolve().parents[3]
    resolved = path.expanduser().resolve()
    return resolved == repo_root or resolved.is_relative_to(repo_root)


def _read_3mf_listing(source: Path) -> tuple[list[str], list[str]]:
    try:
        with zipfile.ZipFile(source, "r") as zf:
            internal_listing = sorted(name for name in zf.namelist() if not name.endswith("/"))
    except (zipfile.BadZipFile, OSError) as exc:
        raise PlateChange3mfPostprocessError("invalid_3mf", "Source is not a readable 3MF ZIP artifact") from exc
    gcode_paths = sorted(name for name in internal_listing if name.lower().endswith(".gcode"))
    return internal_listing, gcode_paths


def _build_candidate_plan(source: Path, gcode_paths: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_blocks: list[dict[str, Any]] = []
    insertion_points: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(source, "r") as zf:
            for index, internal_path in enumerate(gcode_paths, start=1):
                raw = zf.read(internal_path)
                line_count, markers = _summarize_gcode_bytes(raw)
                start_line = max(1, line_count - 20)
                block_id = f"candidate-{index}"
                candidate_blocks.append(
                    {
                        "block_id": block_id,
                        "internal_gcode_path": internal_path,
                        "candidate_type": "plate_tail_review_window",
                        "line_range": {"start_line": start_line, "end_line": line_count},
                        "matched_symbolic_markers": markers,
                        "raw_content_redacted": True,
                    }
                )
                insertion_points.append(
                    {
                        "insertion_point_id": f"insertion-{index}",
                        "internal_gcode_path": internal_path,
                        "candidate_block_id": block_id,
                        "position": "before_plate_tail_review_window",
                        "review_required": True,
                        "proposed_change": "SYMBOLIC_SYNTHETIC_INSERTION_ONLY_IN_WP_064_B",
                        "raw_gcode_added": False,
                    }
                )
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        raise PlateChange3mfPostprocessError("invalid_3mf", "Source is not a readable 3MF ZIP artifact") from exc
    return candidate_blocks, insertion_points


def _summarize_gcode_bytes(raw: bytes) -> tuple[int, list[str]]:
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    marker_map = {
        "LAYER_CHANGE": "LAYER_CHANGE_MARKER",
        "stop printing object": "OBJECT_STOP_MARKER",
        "END gcode": "PRINT_END_MARKER",
    }
    markers: list[str] = []
    for needle, symbolic in marker_map.items():
        if needle in text and symbolic not in markers:
            markers.append(symbolic)
    if not markers:
        markers.append("GENERIC_GCODE_TAIL")
    return len(lines), markers


def _find_synthetic_insertion_target(source: Path, gcode_paths: list[str]) -> tuple[str | None, bool]:
    marker = SYNTHETIC_INSERTION_POINT.encode("utf-8")
    inserted_block = PLATE_CHANGE_SYMBOLIC_BLOCK.encode("utf-8")
    matching_paths: list[str] = []
    marker_present = False
    try:
        with zipfile.ZipFile(source, "r") as zf:
            for internal_path in gcode_paths:
                raw = zf.read(internal_path)
                marker_count = raw.count(marker)
                if marker_count:
                    marker_present = True
                if marker_count == 1 and inserted_block not in raw:
                    matching_paths.append(internal_path)
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        raise PlateChange3mfPostprocessError("invalid_3mf", "Source is not a readable 3MF ZIP artifact") from exc
    if len(matching_paths) != 1:
        return None, marker_present
    return matching_paths[0], marker_present



def _create_real_sample_output_review_plan(
    *,
    source_path: str | Path,
    output_dir: str | Path | None,
    sample_roots: list[Path],
    output_roots: list[Path],
) -> dict[str, Any]:
    source = _resolve_allowed_source_path(
        source_path,
        sample_roots,
        root_description="configured real sample root",
    )
    internal_listing, gcode_paths = _read_3mf_listing(source)
    source_bytes = source.read_bytes()
    source_sha256 = _sha256_bytes(source_bytes)
    detected_printer_model_family = extract_source_printer_model(source_bytes)
    candidate_blocks, insertion_points = _build_candidate_plan(source, gcode_paths)
    artifact_dir = _resolve_allowed_output_dir(
        output_dir,
        output_roots,
        default_dir=output_roots[0],
        root_description="configured real-sample output root",
        block_repo_paths=True,
    )
    manifest_already_present = REAL_SAMPLE_REVIEW_MANIFEST_PATH in internal_listing
    artifact_path = _write_real_sample_review_artifact(
        source=source,
        output_dir=artifact_dir,
        source_sha256=source_sha256,
        internal_listing=internal_listing,
        internal_gcode_paths=gcode_paths,
        detected_printer_model_family=detected_printer_model_family,
        manifest_already_present=manifest_already_present,
    )
    output_sha256 = _sha256_bytes(artifact_path.read_bytes())
    output_file_name_redacted = _redacted_artifact_name(artifact_path)
    preserved_member_count = len(internal_listing) - (1 if manifest_already_present else 0)
    modified_internal_paths = [REAL_SAMPLE_REVIEW_MANIFEST_PATH]
    deterministic_diff_summary = _deterministic_diff_summary_real_sample_review(
        member_count=len(internal_listing),
        preserved_member_count=preserved_member_count,
        manifest_already_present=manifest_already_present,
    )

    return {
        "status": POSTPROCESS_PLAN_READY,
        "mode": POSTPROCESS_MODE_DRY_RUN,
        "source_file_name_redacted": _redacted_source_file_name(source),
        "source_name_redacted": _redacted_source_file_name(source),
        "internal_file_listing": internal_listing,
        "internal_gcode_paths": gcode_paths,
        "detected_printer_model_family": detected_printer_model_family,
        "candidate_blocks": candidate_blocks,
        "insertion_points": insertion_points,
        "postprocess_supported": False,
        "prototype_only": True,
        "output_artifact_created": True,
        "output_artifact_root_redacted": "configured-real-sample-output",
        "output_artifact_file_name_redacted": output_file_name_redacted,
        "output_file_name_redacted": output_file_name_redacted,
        "output_name_redacted": output_file_name_redacted,
        "insertion_performed": False,
        "insertion_marker_present": False,
        "inserted_block_kind": None,
        "source_sha256": source_sha256,
        "output_sha256": output_sha256,
        "deterministic_diff_summary": deterministic_diff_summary,
        "preserved_member_count": preserved_member_count,
        "modified_member_paths": modified_internal_paths,
        "modified_internal_paths": modified_internal_paths,
        "review_manifest_path": REAL_SAMPLE_REVIEW_MANIFEST_PATH,
        "real_sample_output_review": True,
        "human_review_required": True,
        "not_approved_for_printing": True,
        "real_gcode_inserted": False,
        "printer_upload_supported": False,
        "printer_start_supported": False,
        "real_execution_supported": False,
        "safety_notes": list(SAFETY_NOTES),
        "redacted_diff_summary": _redacted_diff_summary(gcode_paths, insertion_points),
        "sentinels": _new_sentinels(),
    }


def _write_real_sample_review_artifact(
    *,
    source: Path,
    output_dir: Path,
    source_sha256: str,
    internal_listing: list[str],
    internal_gcode_paths: list[str],
    detected_printer_model_family: str | None,
    manifest_already_present: bool,
) -> Path:
    output_path = output_dir / f"plate-change-real-sample-review-{_short_hash(source_sha256)}.3mf"
    tmp_path = output_path.with_suffix(".tmp")
    manifest = _real_sample_review_manifest_bytes(
        source_sha256=source_sha256,
        internal_listing=internal_listing,
        internal_gcode_paths=internal_gcode_paths,
        detected_printer_model_family=detected_printer_model_family,
        manifest_already_present=manifest_already_present,
    )
    try:
        with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            manifest_written = False
            for item in zin.infolist():
                payload = zin.read(item.filename)
                if item.filename == REAL_SAMPLE_REVIEW_MANIFEST_PATH:
                    payload = manifest
                    manifest_written = True
                zout.writestr(item, payload)
            if not manifest_written:
                manifest_info = zipfile.ZipInfo(REAL_SAMPLE_REVIEW_MANIFEST_PATH, date_time=(1980, 1, 1, 0, 0, 0))
                manifest_info.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(manifest_info, manifest)
        tmp_path.replace(output_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return output_path


def _real_sample_review_manifest_bytes(
    *,
    source_sha256: str,
    internal_listing: list[str],
    internal_gcode_paths: list[str],
    detected_printer_model_family: str | None,
    manifest_already_present: bool,
) -> bytes:
    manifest = {
        "mode": REAL_SAMPLE_OUTPUT_MODE,
        "source_sha256": source_sha256,
        "internal_gcode_paths": internal_gcode_paths,
        "zip_member_count_before": len(internal_listing),
        "manifest_already_present": manifest_already_present,
        "detected_printer_model_family": detected_printer_model_family,
        "raw_gcode_included": False,
        "real_gcode_inserted": False,
        "printer_upload_supported": False,
        "printer_start_supported": False,
        "real_execution_supported": False,
        "human_review_required": True,
        "not_approved_for_printing": True,
    }
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

def _write_output_artifact(
    *,
    source: Path,
    output_dir: Path,
    source_sha256: str,
    target_internal_gcode_path: str,
) -> Path:
    output_path = output_dir / f"plate-change-3mf-postprocess-{_short_hash(source_sha256)}.3mf"
    tmp_path = output_path.with_suffix(".tmp")
    try:
        with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                payload = zin.read(item.filename)
                if item.filename == target_internal_gcode_path:
                    payload = _insert_symbolic_block(payload)
                zout.writestr(item, payload)
        tmp_path.replace(output_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return output_path


def _insert_symbolic_block(raw: bytes) -> bytes:
    marker = SYNTHETIC_INSERTION_POINT.encode("utf-8")
    return raw.replace(marker, PLATE_CHANGE_SYMBOLIC_BLOCK.encode("utf-8") + marker, 1)


def _redacted_source_file_name(source: Path) -> str:
    lower = source.name.lower()
    if lower.endswith(".gcode.3mf"):
        return "redacted-gcode-3mf"
    return "redacted-3mf"


def _redacted_artifact_name(path: Path) -> str:
    return f"redacted-artifact-{_short_hash(path.name)}.3mf"


def _redacted_diff_summary(gcode_paths: list[str], insertion_points: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "summary": "No raw G-code diff is emitted by WP-064-B; only symbolic synthetic insertion metadata is reported",
        "gcode_files_scanned": len(gcode_paths),
        "candidate_insertion_points": len(insertion_points),
        "raw_lines_added": 0,
        "raw_lines_removed": 0,
        "raw_gcode_included": False,
        "requires_human_diff_review": True,
    }



def _deterministic_diff_summary_real_sample_review(
    *,
    member_count: int,
    preserved_member_count: int,
    manifest_already_present: bool,
) -> dict[str, Any]:
    added_member_count = 0 if manifest_already_present else 1
    return {
        "summary": "Added deterministic review manifest only; no internal G-code was modified",
        "target_internal_gcode_path": None,
        "added_internal_paths": [] if manifest_already_present else [REAL_SAMPLE_REVIEW_MANIFEST_PATH],
        "modified_internal_paths": [REAL_SAMPLE_REVIEW_MANIFEST_PATH],
        "inserted_block_count": 0,
        "modified_member_count": 1 if manifest_already_present else 0,
        "added_member_count": added_member_count,
        "preserved_member_count": preserved_member_count,
        "zip_member_count_before": member_count,
        "zip_member_count_after": member_count + added_member_count,
        "raw_gcode_included": False,
        "human_review_required": True,
        "not_approved_for_printing": True,
    }

def _deterministic_diff_summary_no_output(*, member_count: int, marker_present: bool) -> dict[str, Any]:
    return {
        "summary": "No output artifact requested; deterministic synthetic insertion was not performed",
        "target_internal_gcode_path": None,
        "inserted_block_count": 0,
        "modified_member_count": 0,
        "preserved_member_count": member_count,
        "zip_member_count_before": member_count,
        "zip_member_count_after": member_count,
        "insertion_marker_present": marker_present,
        "raw_gcode_included": False,
        "requires_human_diff_review": True,
    }


def _deterministic_diff_summary_unsupported(*, member_count: int, marker_present: bool) -> dict[str, Any]:
    return {
        "summary": "No deterministic synthetic insertion point found; output artifact blocked",
        "target_internal_gcode_path": None,
        "inserted_block_count": 0,
        "modified_member_count": 0,
        "preserved_member_count": member_count,
        "zip_member_count_before": member_count,
        "zip_member_count_after": member_count,
        "insertion_marker_present": marker_present,
        "raw_gcode_included": False,
        "requires_human_diff_review": True,
    }


def _deterministic_diff_summary_inserted(
    *,
    target_internal_gcode_path: str,
    preserved_member_count: int,
    member_count: int,
) -> dict[str, Any]:
    return {
        "summary": "Inserted one symbolic WP-064-B marker block into one synthetic internal G-code member",
        "target_internal_gcode_path": target_internal_gcode_path,
        "inserted_block_count": 1,
        "modified_member_count": 1,
        "preserved_member_count": preserved_member_count,
        "zip_member_count_before": member_count,
        "zip_member_count_after": member_count,
        "raw_gcode_included": False,
        "requires_human_diff_review": True,
    }


def _new_sentinels() -> dict[str, int]:
    return {effect: 0 for effect in FORBIDDEN_SIDE_EFFECTS}



def _physical_canary_runtime_gates_enabled(
    *,
    physical_canary_enabled: bool,
    allow_printer_upload: bool,
    allow_print_start: bool,
    single_printer_only: bool,
    require_human_confirmation: bool,
    disable_auto_retry: bool,
    max_starts: int,
) -> bool:
    return all(
        (
            physical_canary_enabled,
            allow_printer_upload,
            allow_print_start,
            single_printer_only,
            require_human_confirmation,
            disable_auto_retry,
            max_starts == 1,
        )
    )


def _require_physical_canary_gates(
    *,
    physical_canary_enabled: bool,
    allow_printer_upload: bool,
    allow_print_start: bool,
    single_printer_only: bool,
    require_human_confirmation: bool,
    disable_auto_retry: bool,
    max_starts: int,
) -> None:
    if not physical_canary_enabled:
        raise PlateChange3mfPostprocessError(
            "physical_canary_disabled",
            "Supervised physical canary is disabled",
        )
    if not allow_printer_upload:
        raise PlateChange3mfPostprocessError(
            "printer_upload_not_allowed",
            "Supervised physical canary printer upload is disabled",
        )
    if not allow_print_start:
        raise PlateChange3mfPostprocessError(
            "print_start_not_allowed",
            "Supervised physical canary print start is disabled",
        )
    if not single_printer_only:
        raise PlateChange3mfPostprocessError(
            "single_printer_gate_required",
            "Supervised physical canary requires the single-printer gate",
        )
    if not require_human_confirmation:
        raise PlateChange3mfPostprocessError(
            "human_confirmation_gate_required",
            "Supervised physical canary requires human confirmation",
        )
    if not disable_auto_retry:
        raise PlateChange3mfPostprocessError(
            "auto_retry_disabled_required",
            "Supervised physical canary requires automatic retry to be disabled",
        )
    if max_starts != 1:
        raise PlateChange3mfPostprocessError(
            "single_start_required",
            "Supervised physical canary allows exactly one start attempt",
        )


def _single_canary_printer_id(request: dict[str, Any], *, single_printer_only: bool) -> str:
    printer_ids = request.get("target_printer_ids")
    if not isinstance(printer_ids, list) or not printer_ids:
        raise PlateChange3mfPostprocessError("single_printer_required", "Exactly one canary printer is required")
    normalized = [str(value) for value in printer_ids]
    if single_printer_only and len(normalized) != 1:
        raise PlateChange3mfPostprocessError("single_printer_required", "Exactly one canary printer is required")
    return normalized[0]


def _resolve_canary_artifact_path(artifact_path: object, output_roots: Iterable[str | Path]) -> Path:
    if not isinstance(artifact_path, str) or not artifact_path.strip():
        raise PlateChange3mfPostprocessError("artifact_path_required", "A reviewed 3MF artifact path is required")
    candidate = Path(artifact_path).expanduser().resolve()
    if _path_is_repo_relative(candidate):
        raise PlateChange3mfPostprocessError(
            "repo_artifact_path_not_allowed",
            "Supervised physical canary artifact must not be inside the repository",
        )
    if not candidate.name.lower().endswith(".3mf"):
        raise PlateChange3mfPostprocessError(
            "unsupported_artifact_file",
            "Supervised physical canary accepts only reviewed .3mf or .gcode.3mf artifacts",
        )
    roots = _resolved_roots(output_roots)
    if not any(candidate.is_relative_to(root) for root in roots):
        raise PlateChange3mfPostprocessError(
            "artifact_path_not_allowed",
            "Supervised physical canary artifact path must be inside the configured output root",
        )
    if not candidate.is_file():
        raise PlateChange3mfPostprocessError("artifact_not_found", "Reviewed 3MF artifact was not found")
    return candidate


def _validated_artifact_sha256(artifact_sha256: object, artifact_path: Path) -> str:
    if not isinstance(artifact_sha256, str) or len(artifact_sha256) != 64:
        raise PlateChange3mfPostprocessError("artifact_sha256_required", "Reviewed artifact SHA-256 is required")
    normalized = artifact_sha256.lower()
    if any(char not in "0123456789abcdef" for char in normalized):
        raise PlateChange3mfPostprocessError("artifact_sha256_required", "Reviewed artifact SHA-256 is required")
    actual = _sha256_bytes(artifact_path.read_bytes())
    if normalized != actual:
        raise PlateChange3mfPostprocessError(
            "artifact_sha256_mismatch",
            "Reviewed artifact SHA-256 does not match the artifact bytes",
        )
    return normalized


def _require_confirmation_phrase(actual: object, *, expected: str) -> None:
    if actual != expected:
        raise PlateChange3mfPostprocessError(
            "confirmation_phrase_mismatch",
            "Human confirmation phrase did not match the reviewed artifact and printer",
        )


def _require_canary_checklist(checklist: object) -> None:
    if hasattr(checklist, "model_dump"):
        values = checklist.model_dump()
    elif isinstance(checklist, dict):
        values = checklist
    else:
        values = {}
    missing = [field for field in CANARY_REQUIRED_CHECKLIST_FIELDS if values.get(field) is not True]
    if missing:
        raise PlateChange3mfPostprocessError(
            "canary_checklist_incomplete",
            "Every supervised physical canary checklist field must be true before print start",
        )


def _require_known_idle_printer_state(printer_state: Any) -> None:
    if printer_state is None:
        raise PlateChange3mfPostprocessError(
            "printer_state_uncertain",
            "Printer state is uncertain; supervised physical canary start is blocked",
        )
    if isinstance(printer_state, dict):
        state_value = printer_state.get("state")
        active_file = printer_state.get("gcode_file")
    else:
        state_value = getattr(printer_state, "state", None)
        active_file = getattr(printer_state, "gcode_file", None)
    known_idle_states = {"IDLE", "FINISH"}
    if not isinstance(state_value, str) or state_value.upper() not in known_idle_states or active_file:
        raise PlateChange3mfPostprocessError(
            "printer_state_uncertain",
            "Printer must report a known idle state before supervised physical canary start",
        )


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


plate_change_3mf_postprocess_service = PlateChange3mfPostprocessService()
plate_change_3mf_physical_canary_service = PlateChange3mfPhysicalCanaryService()
