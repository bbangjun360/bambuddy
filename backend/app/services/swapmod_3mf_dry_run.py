from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any, Iterable

SWAPMOD_DRY_RUN_READY = "SWAPMOD_DRY_RUN_READY"
SWAPMOD_DRY_RUN_REVIEW_REQUIRED = "SWAPMOD_DRY_RUN_REVIEW_REQUIRED"
SWAPMOD_DRY_RUN_MODE = "DRY_RUN_ONLY"

WORKFLOW_STATES = (
    "WAIT_ORIGINAL_FINISH",
    "EXTRACT_REVIEWED_SWAP_BLOCK",
    "MANUAL_REVIEW_REQUIRED",
    "WOULD_SEND_ALLOWLISTED_SEQUENCE",
    "WOULD_START_NEXT_PRINT",
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
    "WP-065 is dry-run only and does not send printer commands",
    "SwapMod candidate blocks require human review before any future canary",
    "Raw G-code is not returned by this endpoint",
    "A future real canary must verify bed READY before starting the next print",
)


class Swapmod3mfDryRunError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Swapmod3mfDryRunService:
    def status_snapshot(
        self,
        *,
        enabled: bool = False,
        dry_run: bool = True,
        allowed_roots: Iterable[str | Path] | None = None,
    ) -> dict[str, Any]:
        return {
            "mode": SWAPMOD_DRY_RUN_MODE,
            "enabled": enabled,
            "dry_run": dry_run,
            "allowed_root_configured": bool(_resolved_optional_roots(allowed_roots)),
            "real_execution_supported": False,
            "printer_upload_supported": False,
            "printer_start_supported": False,
            "queue_supported": False,
            "scheduler_supported": False,
            "batch_supported": False,
            "auto_retry_supported": False,
            "arbitrary_gcode_supported": False,
            "raw_gcode_returned": False,
            "human_review_required": True,
            "sentinels": _new_sentinels(),
        }

    def create_plan(
        self,
        *,
        original_path: str | Path,
        swapmod_path: str | Path,
        enabled: bool,
        dry_run: bool,
        request_dry_run: bool = True,
        allowed_roots: Iterable[str | Path],
        repository_root: str | Path | None = None,
        expected_printer_model_family: str | None = None,
    ) -> dict[str, Any]:
        if not enabled:
            raise Swapmod3mfDryRunError("feature_disabled", "SwapMod 3MF dry-run workflow is disabled")
        if not dry_run or request_dry_run is not True:
            raise Swapmod3mfDryRunError("dry_run_required", "SwapMod 3MF workflow is dry-run only")

        roots = _resolved_roots(allowed_roots)
        repo_root = Path(repository_root).expanduser().resolve() if repository_root is not None else None
        original = _resolve_allowed_3mf_path(original_path, roots, repository_root=repo_root)
        swapmod = _resolve_allowed_3mf_path(swapmod_path, roots, repository_root=repo_root)
        original_members = _read_gcode_members(original)
        swapmod_members = _read_gcode_members(swapmod)
        original_member_path, original_text = original_members[0]
        swapmod_member_path, swapmod_text = swapmod_members[0]
        original_lines = _split_lines(original_text)
        swapmod_lines = _split_lines(swapmod_text)
        occurrences = _find_exact_occurrences(swapmod_lines, original_lines)

        review_reasons: list[str] = []
        candidate_blocks: list[dict[str, Any]] = []
        status = SWAPMOD_DRY_RUN_READY
        if len(occurrences) == 2:
            first_start = occurrences[0]
            first_end = first_start + len(original_lines)
            second_start = occurrences[1]
            second_end = second_start + len(original_lines)
            windows = [
                ("plate_load_only", swapmod_lines[:first_start]),
                ("inter_job_swap", swapmod_lines[first_end:second_start]),
                ("final_swap", swapmod_lines[second_end:]),
            ]
            candidate_blocks = [
                _candidate_block(kind, lines)
                for kind, lines in windows
                if _has_nonempty_line(lines)
            ]
        else:
            status = SWAPMOD_DRY_RUN_REVIEW_REQUIRED
            review_reasons.append("expected_exactly_two_original_occurrences")

        return {
            "status": status,
            "mode": SWAPMOD_DRY_RUN_MODE,
            "original_file_name_redacted": _redacted_name(original),
            "swapmod_file_name_redacted": _redacted_name(swapmod),
            "original_sha256": _sha256_file(original),
            "swapmod_sha256": _sha256_file(swapmod),
            "original_gcode_members": [original_member_path],
            "swapmod_gcode_members": [swapmod_member_path],
            "expected_printer_model_family": expected_printer_model_family,
            "candidate_blocks": candidate_blocks,
            "review_reasons": review_reasons,
            "workflow_trace": _workflow_trace(),
            "human_review_required": True,
            "real_execution_supported": False,
            "printer_upload_supported": False,
            "printer_start_supported": False,
            "queue_supported": False,
            "scheduler_supported": False,
            "batch_supported": False,
            "auto_retry_supported": False,
            "arbitrary_gcode_supported": False,
            "raw_gcode_returned": False,
            "safety_notes": list(SAFETY_NOTES),
            "sentinels": _new_sentinels(),
        }


def default_swapmod_sample_root() -> Path:
    return Path.home() / "workspace" / "plate-change-samples"


def _resolved_roots(allowed_roots: Iterable[str | Path]) -> list[Path]:
    roots = _resolved_optional_roots(allowed_roots)
    if not roots:
        raise Swapmod3mfDryRunError("controlled_root_required", "At least one controlled root is required")
    return roots


def _resolved_optional_roots(allowed_roots: Iterable[str | Path] | None) -> list[Path]:
    if allowed_roots is None:
        return []
    return [Path(root).expanduser().resolve() for root in allowed_roots if root is not None]


def _resolve_allowed_3mf_path(
    source_path: str | Path,
    roots: list[Path],
    *,
    repository_root: Path | None = None,
) -> Path:
    source = Path(source_path).expanduser().resolve()
    lower = source.name.lower()
    if not (lower.endswith(".3mf") or lower.endswith(".gcode.3mf")):
        raise Swapmod3mfDryRunError("unsupported_source_file", "Only .3mf or .gcode.3mf artifacts are accepted")
    if repository_root is not None and source.is_relative_to(repository_root):
        raise Swapmod3mfDryRunError("source_path_not_allowed", "Source path must not be inside the repository")
    if not any(source.is_relative_to(root) for root in roots):
        raise Swapmod3mfDryRunError("source_path_not_allowed", "Source path must be inside a controlled root")
    if not source.exists():
        raise Swapmod3mfDryRunError("source_file_missing", "Source 3MF artifact was not found")
    return source


def _read_gcode_members(path: Path) -> list[tuple[str, str]]:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            members = [
                (name, zf.read(name).decode("utf-8", errors="replace"))
                for name in sorted(zf.namelist())
                if name.lower().endswith(".gcode")
            ]
    except (zipfile.BadZipFile, OSError, KeyError) as exc:
        raise Swapmod3mfDryRunError("invalid_3mf", "Source is not a readable 3MF ZIP artifact") from exc
    if not members:
        raise Swapmod3mfDryRunError("gcode_member_required", "3MF artifact must contain an internal .gcode member")
    return members


def _split_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").splitlines()


def _find_exact_occurrences(haystack: list[str], needle: list[str]) -> list[int]:
    if not needle or len(needle) > len(haystack):
        return []
    return [
        index
        for index in range(0, len(haystack) - len(needle) + 1)
        if haystack[index : index + len(needle)] == needle
    ]


def _candidate_block(kind: str, lines: list[str]) -> dict[str, Any]:
    line_range_hash = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
    return {
        "candidate_id": f"swapmod:{kind}:{line_range_hash[:12]}",
        "candidate_kind": kind,
        "line_count": len(lines),
        "line_range_hash": line_range_hash,
        "command_family_counts": _command_family_counts(lines),
        "review_required": True,
        "raw_gcode_included": False,
        "real_execution_supported": False,
    }


def _command_family_counts(lines: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        family = stripped.split(maxsplit=1)[0].upper()
        counts[family] = counts.get(family, 0) + 1
    return counts


def _has_nonempty_line(lines: list[str]) -> bool:
    return any(line.strip() for line in lines)


def _workflow_trace() -> list[dict[str, Any]]:
    return [{"state": state, "dry_run_only": True} for state in WORKFLOW_STATES]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _redacted_name(path: Path) -> str:
    suffix = ".gcode.3mf" if path.name.lower().endswith(".gcode.3mf") else ".3mf"
    return f"redacted-swapmod-input-{hashlib.sha256(path.name.encode('utf-8')).hexdigest()[:12]}{suffix}"


def _new_sentinels() -> dict[str, int]:
    return {effect: 0 for effect in FORBIDDEN_SIDE_EFFECTS}


swapmod_3mf_dry_run_service = Swapmod3mfDryRunService()
