from __future__ import annotations

import hashlib
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

from backend.app.services.slicer_3mf_convert import extract_source_printer_model

POSTPROCESS_PLAN_READY = "POSTPROCESS_PLAN_READY"
POSTPROCESS_UNSUPPORTED = "POSTPROCESS_UNSUPPORTED"
POSTPROCESS_MODE_DRY_RUN = "DRY_RUN_ONLY"
INSERTED_BLOCK_KIND = "SYMBOLIC_PLATE_CHANGE_REVIEW_ONLY"
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
    "3MF post-processing output requires human diff review before any future use",
    "Output artifacts are disabled by default and remain prototype evidence only",
    "Printer upload/start remains out of scope for WP-064-B",
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
                artifact_dir = _resolve_allowed_output_dir(output_dir, source, roots)
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
            "insertion_performed": insertion_performed,
            "insertion_marker_present": insertion_marker_present,
            "inserted_block_kind": inserted_block_kind,
            "source_sha256": source_sha256,
            "output_sha256": output_sha256,
            "deterministic_diff_summary": deterministic_diff_summary,
            "preserved_member_count": preserved_member_count,
            "modified_member_paths": modified_member_paths,
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
    ) -> dict[str, Any]:
        return {
            "mode": POSTPROCESS_MODE_DRY_RUN,
            "enabled": enabled,
            "dry_run": dry_run,
            "allow_output_artifact": allow_output_artifact,
            "postprocess_supported": False,
            "prototype_only": True,
            "output_artifact_created": False,
            "insertion_performed": False,
            "insertion_marker_present": False,
            "inserted_block_kind": None,
            "source_sha256": None,
            "output_sha256": None,
            "deterministic_diff_summary": _deterministic_diff_summary_no_output(member_count=0, marker_present=False),
            "preserved_member_count": 0,
            "modified_member_paths": [],
            "real_gcode_inserted": False,
            "printer_upload_supported": False,
            "printer_start_supported": False,
            "real_execution_supported": False,
            "safety_notes": list(SAFETY_NOTES),
            "sentinels": _new_sentinels(),
        }


def default_controlled_roots(base_dir: str | Path | None = None) -> list[Path]:
    _ = base_dir
    return [Path(tempfile.gettempdir()) / "bambuddy-plate-change-3mf-postprocess"]


def _resolved_roots(allowed_roots: Iterable[str | Path]) -> list[Path]:
    roots = [Path(root).expanduser().resolve() for root in allowed_roots]
    if not roots:
        raise PlateChange3mfPostprocessError(
            "controlled_root_required",
            "At least one controlled test/temp root is required",
        )
    return roots


def _resolve_allowed_source_path(source_path: str | Path, roots: list[Path]) -> Path:
    source = Path(source_path).expanduser().resolve()
    if not source.name.lower().endswith(".3mf"):
        raise PlateChange3mfPostprocessError(
            "unsupported_source_file",
            "Only .3mf or .gcode.3mf ZIP artifacts are accepted",
        )
    if not any(source.is_relative_to(root) for root in roots):
        raise PlateChange3mfPostprocessError(
            "source_path_not_allowed",
            "Source path must be inside a controlled test/temp root",
        )
    if not source.is_file():
        raise PlateChange3mfPostprocessError("source_not_found", "Source 3MF artifact was not found")
    return source


def _resolve_allowed_output_dir(output_dir: str | Path | None, source: Path, roots: list[Path]) -> Path:
    candidate = Path(output_dir).expanduser().resolve() if output_dir is not None else source.parent / "postprocess-output"
    candidate = candidate.resolve()
    if not any(candidate.is_relative_to(root) for root in roots):
        raise PlateChange3mfPostprocessError(
            "output_path_not_allowed",
            "Output artifact directory must be inside a controlled test/temp root",
        )
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


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


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


plate_change_3mf_postprocess_service = PlateChange3mfPostprocessService()
