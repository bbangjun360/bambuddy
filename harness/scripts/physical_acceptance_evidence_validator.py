#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

EXPECTED_RELEASE_TAG = "farm-v0.1.0-acceptance"
EXPECTED_RELEASE_COMMIT = "9190b2fc6ac1e111234ad73d8d73e2a487d81be5"
READY_STATE = "READY_FOR_NEXT_PRINT"
MANUAL_REVIEW_STATE = "MANUAL_REVIEW"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CANARY_KEY_RE = re.compile(r"^wp103-physical-acceptance-[0-9]{8}-[0-9]+$")
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
STRICT_REDACTIONS = {
    "printer_id_redacted": "A1_MINI_CANARY_REDACTED",
    "operator_initials": "REDACTED_OPERATOR",
    "log_bundle_ref": "REDACTED_LOG_BUNDLE",
}

REQUIRED_TRUE_FIELDS = (
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

REQUIRED_FIELDS = (
    "canary_key",
    "printer_id_redacted",
    "release_tag",
    "release_commit",
    *REQUIRED_TRUE_FIELDS,
    "release_sequence_sha256",
    "load_sequence_sha256",
    "release_verified",
    "loaded_verified",
    "final_state",
    "rollback_confirmed",
    "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED",
    "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS",
    "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION",
    "timestamp_utc",
    "operator_initials",
    "log_bundle_ref",
)


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    ready_for_next_print: bool
    final_state: str
    reasons: tuple[str, ...]


def normalized(value: str | None) -> str:
    return (value or "").strip()


def normalized_bool(value: str | None) -> str:
    return normalized(value).lower()

def has_strict_utc_timestamp(value: str) -> bool:
    if not TIMESTAMP_RE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def validate_record(record: Mapping[str, str]) -> ValidationResult:
    reasons: list[str] = []

    for field in REQUIRED_FIELDS:
        if not normalized(record.get(field)):
            reasons.append(f"missing {field}")

    for field in sorted(set(record) - set(REQUIRED_FIELDS)):
        reasons.append(f"unexpected field {field}")

    for field in REQUIRED_TRUE_FIELDS:
        if field in record and normalized_bool(record.get(field)) != "true":
            reasons.append(f"{field} must be true")

    if "release_tag" in record and normalized(record.get("release_tag")) != EXPECTED_RELEASE_TAG:
        reasons.append(f"release_tag must be {EXPECTED_RELEASE_TAG}")
    if "release_commit" in record and normalized(record.get("release_commit")) != EXPECTED_RELEASE_COMMIT:
        reasons.append(f"release_commit must be {EXPECTED_RELEASE_COMMIT}")
    if "canary_key" in record and not CANARY_KEY_RE.fullmatch(normalized(record.get("canary_key"))):
        reasons.append("canary_key must match wp103-physical-acceptance-YYYYMMDD-N")

    for field, expected_value in STRICT_REDACTIONS.items():
        if field in record and normalized(record.get(field)) != expected_value:
            reasons.append(f"{field} must be {expected_value}")

    for field in ("release_sequence_sha256", "load_sequence_sha256"):
        value = normalized(record.get(field))
        if value and not SHA256_RE.fullmatch(value):
            reasons.append(f"{field} must be a lowercase SHA-256 hex digest")

    final_state = normalized(record.get("final_state")) or MANUAL_REVIEW_STATE
    if final_state != READY_STATE:
        reasons.append(f"final_state must be {READY_STATE}")

    if "release_verified" in record and normalized_bool(record.get("release_verified")) != "true":
        reasons.append("release_verified must be true for READY_FOR_NEXT_PRINT")
    if "loaded_verified" in record and normalized_bool(record.get("loaded_verified")) != "true":
        reasons.append("loaded_verified must be true for READY_FOR_NEXT_PRINT")
    if "rollback_confirmed" in record and normalized_bool(record.get("rollback_confirmed")) != "true":
        reasons.append("rollback_confirmed must be true for READY_FOR_NEXT_PRINT")

    if (
        "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED" in record
        and normalized_bool(record.get("FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED")) != "false"
    ):
        reasons.append("FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED must be false")
    if (
        "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS" in record
        and normalized_bool(record.get("FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS")) != "false"
    ):
        reasons.append("FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS must be false")
    if (
        "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION" in record
        and normalized_bool(record.get("FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION")) != "true"
    ):
        reasons.append("FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION must be true")

    timestamp_raw = record.get("timestamp_utc")
    timestamp = normalized(timestamp_raw)
    if timestamp and (timestamp_raw != timestamp or not has_strict_utc_timestamp(timestamp)):
        reasons.append("timestamp_utc must be strict UTC ISO-8601 seconds ending in Z")

    valid = not reasons
    return ValidationResult(
        valid=valid,
        ready_for_next_print=valid and final_state == READY_STATE,
        final_state=READY_STATE if valid else MANUAL_REVIEW_STATE,
        reasons=tuple(reasons),
    )


def parse_records(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for line_number, raw_line in enumerate(text.splitlines(), 1):
        stripped_line = raw_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            if not stripped_line and current:
                records.append(current)
                current = {}
            continue
        if "=" not in raw_line:
            raise ValueError(f"line {line_number}: expected key=value")
        key, value = raw_line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"line {line_number}: missing key")
        if key in current:
            raise ValueError(f"line {line_number}: duplicate key {key}")
        current[key] = value if key == "timestamp_utc" else value.strip()

    if current:
        records.append(current)
    return records


def validate_file(path: Path) -> int:
    try:
        records = parse_records(path.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"record 1: {MANUAL_REVIEW_STATE}")
        print(f"- failed to read evidence file: {exc}")
        return 1
    except ValueError as exc:
        print(f"record 1: {MANUAL_REVIEW_STATE}")
        print(f"- {exc}")
        return 1

    if not records:
        print(f"record 1: {MANUAL_REVIEW_STATE}")
        print("- no evidence records found")
        return 1

    exit_code = 0
    canary_key_records: dict[str, int] = {}
    for index, record in enumerate(records, 1):
        result = validate_record(record)
        reasons = list(result.reasons)
        canary_key = normalized(record.get("canary_key"))
        if canary_key:
            previous_index = canary_key_records.get(canary_key)
            if previous_index is None:
                canary_key_records[canary_key] = index
            else:
                reasons.append(f"duplicate canary_key {canary_key} already appeared in record {previous_index}")

        state = READY_STATE if result.ready_for_next_print and not reasons else MANUAL_REVIEW_STATE
        print(f"record {index}: {state}")
        for reason in reasons:
            print(f"- {reason}")
        if reasons:
            exit_code = 1
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate WP-104 physical acceptance evidence records.")
    parser.add_argument("evidence_file", type=Path)
    args = parser.parse_args(argv)
    return validate_file(args.evidence_file)


if __name__ == "__main__":
    raise SystemExit(main())
