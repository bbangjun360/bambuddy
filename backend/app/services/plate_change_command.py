from __future__ import annotations

import hashlib
import json
from collections import Counter, OrderedDict
from threading import RLock
from typing import Any

DRY_RUN_COMMANDS_READY = "DRY_RUN_COMMANDS_READY"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
PLATE_CHANGE_BLOCKED = "PLATE_CHANGE_BLOCKED"

ALLOWED_COMMAND_SEQUENCES = ("supervised_plate_change_v1",)

FORBIDDEN_SIDE_EFFECTS = (
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

ACTION_FIELDS = (
    "printflow_action",
    "printer_action",
    "queue_action",
    "scheduler_action",
    "erp_action",
    "obico_action",
    "bed_action",
)


class PlateChangeCommandError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PlateChangeCommandDryRunService:
    def __init__(self) -> None:
        self._lock = RLock()
        self.clear()

    def clear(self) -> None:
        with self._lock:
            self._records: OrderedDict[str, dict[str, Any]] = OrderedDict()
            self._status_counts: Counter[str] = Counter()
            self._sentinels = _new_sentinels()

    def create_dry_run(
        self,
        payload: dict[str, Any],
        *,
        global_dry_run: bool,
        human_approval_required: bool,
        single_printer_only: bool,
        allow_real_commands: bool,
    ) -> dict[str, Any]:
        idempotency_key = _nonempty(payload.get("idempotency_key"))
        if idempotency_key is None:
            raise PlateChangeCommandError("missing_idempotency_key", "idempotency_key is required")
        if payload.get("dry_run") is not True:
            raise PlateChangeCommandError("dry_run_required", "Plate-change command research is dry-run only")
        if not global_dry_run:
            raise PlateChangeCommandError("dry_run_required", "Plate-change command dry-run gate must remain enabled")
        if allow_real_commands:
            raise PlateChangeCommandError(
                "real_commands_not_implemented",
                "Real plate-change commands are not implemented in this Work Package",
            )

        command_sequence = _nonempty(payload.get("command_sequence"))
        if command_sequence not in ALLOWED_COMMAND_SEQUENCES:
            raise PlateChangeCommandError("unsupported_command_sequence", "command_sequence is not allowlisted")

        target_printer_ids = _target_printer_ids(payload.get("target_printer_ids"))
        target_printer_id = target_printer_ids[0] if len(target_printer_ids) == 1 else None
        blockers: list[str] = []
        if not single_printer_only:
            blockers.append("single_printer_gate_disabled")
        if len(target_printer_ids) != 1:
            blockers.append("single_printer_required")

        operator_approved = payload.get("operator_approved") is True
        submitted_phrase = _nonempty(payload.get("operator_approval_phrase"))
        required_phrase = (
            required_plate_change_approval_phrase(target_printer_id, command_sequence)
            if target_printer_id is not None and command_sequence is not None
            else None
        )

        if human_approval_required:
            if not operator_approved:
                return _approval_required_record(
                    idempotency_key,
                    payload,
                    target_printer_ids=target_printer_ids,
                    target_printer_id=target_printer_id,
                    command_sequence=command_sequence,
                    blocked_reasons=["operator_approval_required"],
                    failure_class="operator_approval_required",
                    human_approval_required=human_approval_required,
                    single_printer_only=single_printer_only,
                )
            if submitted_phrase is None:
                return _approval_required_record(
                    idempotency_key,
                    payload,
                    target_printer_ids=target_printer_ids,
                    target_printer_id=target_printer_id,
                    command_sequence=command_sequence,
                    blocked_reasons=["approval_phrase_required"],
                    failure_class="approval_phrase_required",
                    human_approval_required=human_approval_required,
                    single_printer_only=single_printer_only,
                )
            if required_phrase is not None and submitted_phrase != required_phrase:
                blockers.append("approval_phrase_mismatch")

        if blockers:
            return _blocked_record(
                idempotency_key,
                payload,
                target_printer_ids=target_printer_ids,
                target_printer_id=target_printer_id,
                command_sequence=command_sequence,
                blocked_reasons=blockers,
                human_approval_required=human_approval_required,
                single_printer_only=single_printer_only,
                operator_approved=operator_approved,
            )

        payload_fingerprint = _fingerprint(payload)
        with self._lock:
            existing = self._records.get(idempotency_key)
            if existing is not None:
                if existing.get("payload_fingerprint") != payload_fingerprint:
                    return _blocked_record(
                        idempotency_key,
                        payload,
                        target_printer_ids=target_printer_ids,
                        target_printer_id=target_printer_id,
                        command_sequence=command_sequence,
                        blocked_reasons=["idempotency_payload_mismatch"],
                        human_approval_required=human_approval_required,
                        single_printer_only=single_printer_only,
                        operator_approved=operator_approved,
                    )
                return dict(existing)

            record = _base_record(
                idempotency_key,
                payload,
                target_printer_ids=target_printer_ids,
                target_printer_id=target_printer_id,
                command_sequence=command_sequence,
                human_approval_required=human_approval_required,
                single_printer_only=single_printer_only,
                operator_approved=operator_approved,
            )
            record.update(
                {
                    "dry_run_id": _dry_run_id(idempotency_key),
                    "status": DRY_RUN_COMMANDS_READY,
                    "ready_for_real_command": False,
                    "blocked_reasons": [],
                    "failure_class": None,
                    "stored": True,
                    "payload_fingerprint": payload_fingerprint,
                }
            )
            self._records[idempotency_key] = record
            self._status_counts[DRY_RUN_COMMANDS_READY] += 1
            return dict(record)

    def status_snapshot(
        self,
        *,
        enabled: bool = False,
        dry_run: bool = True,
        human_approval_required: bool = True,
        single_printer_only: bool = True,
        allow_real_commands: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            recent = list(self._records.values())[-10:]
            return {
                "mode": "DRY_RUN_ONLY",
                "enabled": enabled,
                "dry_run": dry_run,
                "human_approval_required": human_approval_required,
                "single_printer_only": single_printer_only,
                "allow_real_commands": allow_real_commands,
                "allowed_command_sequences": list(ALLOWED_COMMAND_SEQUENCES),
                "dry_run_commands": len(self._records),
                "status_counts": dict(sorted(self._status_counts.items())),
                "sentinels": dict(self._sentinels),
                "recent_dry_runs": [_public(record) for record in recent],
            }


def required_plate_change_approval_phrase(target_printer_id: str, command_sequence: str) -> str:
    return f"CONFIRM_DRY_RUN_PLATE_CHANGE {target_printer_id} {command_sequence}"


def _approval_required_record(
    idempotency_key: str,
    payload: dict[str, Any],
    *,
    target_printer_ids: list[str],
    target_printer_id: str | None,
    command_sequence: str,
    blocked_reasons: list[str],
    failure_class: str,
    human_approval_required: bool,
    single_printer_only: bool,
) -> dict[str, Any]:
    record = _base_record(
        idempotency_key,
        payload,
        target_printer_ids=target_printer_ids,
        target_printer_id=target_printer_id,
        command_sequence=command_sequence,
        human_approval_required=human_approval_required,
        single_printer_only=single_printer_only,
        operator_approved=False,
    )
    record.update(
        {
            "status": APPROVAL_REQUIRED,
            "blocked_reasons": blocked_reasons,
            "failure_class": failure_class,
            "stored": False,
            "payload_fingerprint": _fingerprint(payload),
        }
    )
    return _public(record)


def _blocked_record(
    idempotency_key: str,
    payload: dict[str, Any],
    *,
    target_printer_ids: list[str],
    target_printer_id: str | None,
    command_sequence: str,
    blocked_reasons: list[str],
    human_approval_required: bool,
    single_printer_only: bool,
    operator_approved: bool,
) -> dict[str, Any]:
    record = _base_record(
        idempotency_key,
        payload,
        target_printer_ids=target_printer_ids,
        target_printer_id=target_printer_id,
        command_sequence=command_sequence,
        human_approval_required=human_approval_required,
        single_printer_only=single_printer_only,
        operator_approved=operator_approved,
    )
    record.update(
        {
            "status": PLATE_CHANGE_BLOCKED,
            "blocked_reasons": blocked_reasons,
            "failure_class": blocked_reasons[0] if blocked_reasons else None,
            "stored": False,
            "payload_fingerprint": _fingerprint(payload),
        }
    )
    return _public(record)


def _base_record(
    idempotency_key: str,
    payload: dict[str, Any],
    *,
    target_printer_ids: list[str],
    target_printer_id: str | None,
    command_sequence: str,
    human_approval_required: bool,
    single_printer_only: bool,
    operator_approved: bool,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "idempotency_key": idempotency_key,
        "dry_run_id": None,
        "target_printer_ids": target_printer_ids,
        "target_printer_id": target_printer_id,
        "command_sequence": command_sequence,
        "dry_run": True,
        "mock_only": True,
        "ready_for_real_command": False,
        "human_approval_required": human_approval_required,
        "single_printer_only": single_printer_only,
        "operator_approved": operator_approved,
        "requested_sequence_is_allowlisted": command_sequence in ALLOWED_COMMAND_SEQUENCES,
        "real_command_action": None,
        "sentinels": _new_sentinels(),
        "metadata_fingerprint": _metadata_fingerprint(payload.get("metadata")),
    }
    for field_name in ACTION_FIELDS:
        record[field_name] = None
    return record


def _target_printer_ids(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [text for item in value if (text := _nonempty(item)) is not None]
    text = _nonempty(value)
    return [text] if text is not None else []


def _new_sentinels() -> dict[str, int]:
    return {effect: 0 for effect in FORBIDDEN_SIDE_EFFECTS}


def _dry_run_id(idempotency_key: str) -> str:
    return f"pcd:{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()[:16]}"


def _fingerprint(payload: dict[str, Any]) -> str:
    safe_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"metadata", "access_token", "api_key", "password"}
    }
    encoded = json.dumps(safe_payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _metadata_fingerprint(value: object) -> str | None:
    if value is None:
        return None
    encoded = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _nonempty(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _public(record: dict[str, Any]) -> dict[str, Any]:
    return dict(record)


plate_change_command_service = PlateChangeCommandDryRunService()
