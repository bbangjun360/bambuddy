#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType


def load_validator_contract() -> ModuleType:
    validator_path = Path(__file__).with_name("physical_acceptance_evidence_validator.py")
    spec = importlib.util.spec_from_file_location("physical_acceptance_evidence_validator_contract", validator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load physical acceptance evidence validator contract")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = load_validator_contract()
TEMPLATE_FIELDS = tuple(VALIDATOR.REQUIRED_FIELDS)
TIMESTAMP_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_canary_key(canary_key: str) -> str:
    value = canary_key.strip()
    if not VALIDATOR.CANARY_KEY_RE.fullmatch(value):
        raise ValueError("canary_key must match wp103-physical-acceptance-YYYYMMDD-N")
    return value


def validate_timestamp(timestamp_utc: str) -> str:
    value = timestamp_utc.strip()
    try:
        if not TIMESTAMP_RE.fullmatch(value):
            raise ValueError
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("timestamp_utc must be strict UTC ISO-8601 seconds ending in Z") from exc
    return value


def build_template_record(canary_key: str, timestamp_utc: str) -> dict[str, str]:
    record = dict.fromkeys(TEMPLATE_FIELDS, "")
    record.update(
        {
            "canary_key": validate_canary_key(canary_key),
            "printer_id_redacted": "A1_MINI_CANARY_REDACTED",
            "release_tag": VALIDATOR.EXPECTED_RELEASE_TAG,
            "release_commit": VALIDATOR.EXPECTED_RELEASE_COMMIT,
            "release_sequence_sha256": "",
            "load_sequence_sha256": "",
            "release_verified": "false",
            "loaded_verified": "false",
            "final_state": VALIDATOR.MANUAL_REVIEW_STATE,
            "rollback_confirmed": "false",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED": "false",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS": "false",
            "FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION": "true",
            "timestamp_utc": validate_timestamp(timestamp_utc),
            "operator_initials": "REDACTED_OPERATOR",
            "log_bundle_ref": "REDACTED_LOG_BUNDLE",
        }
    )

    for field in VALIDATOR.REQUIRED_TRUE_FIELDS:
        record[field] = "false"
    return record


def render_record(record: dict[str, str]) -> str:
    return "\n".join(f"{field}={record[field]}" for field in TEMPLATE_FIELDS) + "\n"


def write_record(record: dict[str, str], output: Path | None) -> int:
    rendered = render_record(record)
    if output is None:
        print(rendered, end="")
        return 0
    output.write_text(rendered, encoding="utf-8")
    print(f"wrote {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a WP-105 physical acceptance evidence template.")
    parser.add_argument("--canary-key", required=True)
    parser.add_argument("--timestamp-utc", default=utc_now())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        record = build_template_record(canary_key=args.canary_key, timestamp_utc=args.timestamp_utc)
        return write_record(record, args.output)
    except OSError as exc:
        print(f"failed to write evidence template: {exc}")
        return 1
    except ValueError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
