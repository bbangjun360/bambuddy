from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.swapmod_state_machine import SwapmodStateMachineCycle
from backend.app.services.swapmod_state_machine import (
    LOAD_NEXT_PLATE,
    READY_TO_LOAD,
    READY_TO_RELEASE,
    RELEASE_PLATE,
    START_STEP,
    STEP_REAL_COMMAND_SENT,
    TIMEOUT,
    apply_swapmod_event,
    public_swapmod_cycle,
)

A1MINI_DIRECT_CANARY_MODE = "A1_MINI_DIRECT_CANARY"
DIRECT_COMMAND_SENT = "COMMAND_SENT"
DIRECT_COMMAND_FAILED = "COMMAND_FAILED"

A1MINI_DIRECT_CHECKLIST_FIELDS = (
    "operator_present",
    "printer_visible",
    "emergency_stop_ready",
    "power_cutoff_ready",
    "a1_mini_confirmed",
    "swapmod_hardware_installed",
    "bed_area_clear",
    "plate_stack_ready",
    "no_other_job_running",
    "dry_run_gate_reviewed",
)


class SwapmodA1MiniDirectCanaryError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class A1MiniDirectCanaryTransport(Protocol):
    def get_status(self, printer_id: int) -> dict[str, object] | None: ...

    def send_gcode(self, printer_id: int, gcode: str) -> bool: ...


def required_a1mini_direct_canary_phrase(
    *,
    printer_id: int,
    cycle_key: str,
    step: str,
    sequence_sha256: str,
) -> str:
    return f"CONFIRM_A1_MINI_DIRECT_PLATE_CHANGE {printer_id} {cycle_key} {step} {sequence_sha256}"


class SwapmodA1MiniDirectCanaryService:
    def status_snapshot(
        self,
        *,
        enabled: bool,
        allow_real_commands: bool,
        release_sequence_configured: bool,
        load_sequence_configured: bool,
    ) -> dict[str, object]:
        return {
            "mode": A1MINI_DIRECT_CANARY_MODE,
            "enabled": enabled,
            "allow_real_commands": allow_real_commands,
            "release_sequence_configured": release_sequence_configured,
            "load_sequence_configured": load_sequence_configured,
            "single_printer_only": True,
            "human_confirmation_required": True,
            "arbitrary_gcode_supported": False,
            "raw_gcode_accepted": False,
            "raw_gcode_returned": False,
            "queue_supported": False,
            "scheduler_supported": False,
            "printer_upload_supported": False,
            "printer_start_supported": False,
            "auto_retry_supported": False,
        }

    async def execute_transport_step(
        self,
        db: AsyncSession,
        cycle: SwapmodStateMachineCycle,
        *,
        canary_key: str,
        printer_id: int,
        printer_model: str | None,
        step: str,
        operator_approved: bool,
        operator_approval_phrase: str | None,
        checklist: dict[str, bool],
        enabled: bool,
        allow_real_commands: bool,
        sequence_root: str | Path | None,
        release_sequence_file: str | None,
        release_sequence_sha256: str | None,
        load_sequence_file: str | None,
        load_sequence_sha256: str | None,
        transport: A1MiniDirectCanaryTransport,
    ) -> dict[str, object]:
        if not enabled:
            raise SwapmodA1MiniDirectCanaryError("direct_canary_disabled", "A1 Mini direct canary is disabled")
        if not allow_real_commands:
            raise SwapmodA1MiniDirectCanaryError(
                "real_commands_not_enabled",
                "A1 Mini direct canary real command flag is disabled",
            )
        if step not in {RELEASE_PLATE, LOAD_NEXT_PLATE}:
            raise SwapmodA1MiniDirectCanaryError("unsupported_step", "unsupported A1 Mini direct canary step")
        if int(cycle.printer_id or printer_id) != int(printer_id):
            raise SwapmodA1MiniDirectCanaryError("printer_id_mismatch", "cycle printer does not match request")
        if not _is_a1_mini(printer_model):
            raise SwapmodA1MiniDirectCanaryError("printer_model_not_a1_mini", "direct canary requires A1 Mini")

        required_state = READY_TO_RELEASE if step == RELEASE_PLATE else READY_TO_LOAD
        if cycle.state != required_state:
            raise SwapmodA1MiniDirectCanaryError(
                "cycle_state_not_ready_for_step",
                f"cycle must be {required_state} for {step}",
            )

        missing = [field for field in A1MINI_DIRECT_CHECKLIST_FIELDS if not bool(checklist.get(field))]
        if missing:
            raise SwapmodA1MiniDirectCanaryError("checklist_incomplete", "all direct canary checklist fields are required")
        if not operator_approved:
            raise SwapmodA1MiniDirectCanaryError("operator_approval_missing", "operator approval is required")

        sequence_path, sequence_sha256 = _select_sequence(
            step=step,
            sequence_root=sequence_root,
            release_sequence_file=release_sequence_file,
            release_sequence_sha256=release_sequence_sha256,
            load_sequence_file=load_sequence_file,
            load_sequence_sha256=load_sequence_sha256,
        )
        required_phrase = required_a1mini_direct_canary_phrase(
            printer_id=printer_id,
            cycle_key=cycle.cycle_key,
            step=step,
            sequence_sha256=sequence_sha256,
        )
        if operator_approval_phrase != required_phrase:
            raise SwapmodA1MiniDirectCanaryError("operator_phrase_mismatch", "operator phrase does not match")

        _require_known_idle_printer_state(transport.get_status(printer_id))
        sequence_text = sequence_path.read_text(encoding="utf-8")
        line_count = len(sequence_text.splitlines())

        event_prefix = f"a1mini-direct:{canary_key}"
        if any(str(event_id).startswith(event_prefix) for event_id in (cycle.seen_event_ids or [])):
            raise SwapmodA1MiniDirectCanaryError("duplicate_canary_key", "direct canary key was already used")

        cycle = await apply_swapmod_event(
            db,
            cycle,
            START_STEP,
            event_id=f"{event_prefix}:start",
            step=step,
            note="A1 Mini direct canary transport started",
        )

        command_sent = transport.send_gcode(printer_id, sequence_text)
        if not command_sent:
            cycle = await apply_swapmod_event(
                db,
                cycle,
                TIMEOUT,
                event_id=f"{event_prefix}:send-failed",
                step=step,
                note="A1 Mini direct canary command send failed; manual review required",
            )
            payload = public_swapmod_cycle(cycle)
            payload.update(
                {
                    "direct_canary_status": DIRECT_COMMAND_FAILED,
                    "mode": A1MINI_DIRECT_CANARY_MODE,
                    "step": step,
                    "sequence_sha256": sequence_sha256,
                    "sequence_line_count": line_count,
                    "required_operator_approval_phrase": required_phrase,
                    "real_execution_supported": True,
                    "real_command_sent": False,
                    "printer_command_sent": False,
                    "auto_retry_supported": False,
                    "raw_gcode_returned": False,
                }
            )
            return payload

        cycle = await apply_swapmod_event(
            db,
            cycle,
            STEP_REAL_COMMAND_SENT,
            event_id=f"{event_prefix}:sent",
            step=step,
            note="A1 Mini direct canary command sent; verification required",
        )
        payload = public_swapmod_cycle(cycle)
        payload.update(
            {
                "direct_canary_status": DIRECT_COMMAND_SENT,
                "mode": A1MINI_DIRECT_CANARY_MODE,
                "step": step,
                "sequence_sha256": sequence_sha256,
                "sequence_line_count": line_count,
                "required_operator_approval_phrase": required_phrase,
                "real_execution_supported": True,
                "real_command_sent": True,
                "printer_command_sent": True,
                "auto_retry_supported": False,
                "raw_gcode_returned": False,
            }
        )
        return payload


def _select_sequence(
    *,
    step: str,
    sequence_root: str | Path | None,
    release_sequence_file: str | None,
    release_sequence_sha256: str | None,
    load_sequence_file: str | None,
    load_sequence_sha256: str | None,
) -> tuple[Path, str]:
    if step == RELEASE_PLATE:
        configured_file = release_sequence_file
        configured_sha = release_sequence_sha256
    else:
        configured_file = load_sequence_file
        configured_sha = load_sequence_sha256
    if not sequence_root or not configured_file or not configured_sha:
        raise SwapmodA1MiniDirectCanaryError("sequence_not_configured", "direct canary sequence is not configured")
    if Path(configured_file).is_absolute() or ".." in Path(configured_file).parts:
        raise SwapmodA1MiniDirectCanaryError("sequence_path_not_allowed", "sequence file must be relative")

    root = Path(sequence_root).expanduser().resolve()
    path = (root / configured_file).resolve()
    if not path.is_relative_to(root):
        raise SwapmodA1MiniDirectCanaryError("sequence_path_not_allowed", "sequence file is outside configured root")
    if not path.is_file():
        raise SwapmodA1MiniDirectCanaryError("sequence_not_found", "direct canary sequence file was not found")

    actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_sha != configured_sha:
        raise SwapmodA1MiniDirectCanaryError("sequence_sha256_mismatch", "direct canary sequence SHA-256 mismatch")
    return path, actual_sha


def _require_known_idle_printer_state(state: dict[str, object] | None) -> None:
    if not state:
        raise SwapmodA1MiniDirectCanaryError("printer_not_connected", "printer status is unavailable")
    state_value = str(state.get("state") or "").upper()
    active_file = bool(state.get("gcode_file"))
    if state_value == "IDLE" and not active_file:
        return
    if state_value == "FINISH" and not active_file:
        return
    raise SwapmodA1MiniDirectCanaryError("printer_not_known_idle", "printer is not in a known idle state")


def _is_a1_mini(model: str | None) -> bool:
    normalized = (model or "").lower().replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())
    return normalized in {"a1 mini", "bambu lab a1 mini"}


swapmod_a1mini_direct_canary_service = SwapmodA1MiniDirectCanaryService()
