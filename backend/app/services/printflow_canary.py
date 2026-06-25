from __future__ import annotations

import hashlib
import json
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

READINESS_PASSED = "READINESS_PASSED"
READINESS_BLOCKED = "READINESS_BLOCKED"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"

FORBIDDEN_SIDE_EFFECTS = (
    "printer_commands",
    "printflow_external_calls",
    "queue_dispatches",
    "scheduler_dispatches",
    "erp_submit_calls",
    "erp_inventory_post_calls",
    "erp_accounting_post_calls",
    "obico_mutations",
    "bed_cycle_mutations",
)


class PrintFlowCanaryError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PrintFlowCanaryProbeResult:
    status: str
    failure_class: str | None = None
    blocked_reasons: tuple[str, ...] = ()
    manual_review_required: bool = False
    uncertain_physical_state: bool = False
    bed_state: str = "UNKNOWN"
    retryable: bool = False


_SCENARIOS = {
    "ready": PrintFlowCanaryProbeResult(status=READINESS_PASSED, bed_state="READY"),
    "heartbeat_loss": PrintFlowCanaryProbeResult(
        status=READINESS_BLOCKED,
        failure_class="adapter_heartbeat_loss",
        blocked_reasons=("adapter_heartbeat_loss",),
        retryable=True,
    ),
    "camera_unavailable": PrintFlowCanaryProbeResult(
        status=READINESS_BLOCKED,
        failure_class="camera_unavailable",
        blocked_reasons=("camera_unavailable",),
        retryable=True,
    ),
    "estop_active": PrintFlowCanaryProbeResult(
        status=MANUAL_REVIEW_REQUIRED,
        failure_class="e_stop_active",
        blocked_reasons=("e_stop_active",),
        manual_review_required=True,
        uncertain_physical_state=True,
    ),
    "motion_timeout": PrintFlowCanaryProbeResult(
        status=MANUAL_REVIEW_REQUIRED,
        failure_class="motion_timeout",
        blocked_reasons=("motion_timeout",),
        manual_review_required=True,
        uncertain_physical_state=True,
    ),
    "reply_lost": PrintFlowCanaryProbeResult(
        status=MANUAL_REVIEW_REQUIRED,
        failure_class="command_reply_lost",
        blocked_reasons=("command_reply_lost",),
        manual_review_required=True,
        uncertain_physical_state=True,
    ),
    "object_detected": PrintFlowCanaryProbeResult(
        status=MANUAL_REVIEW_REQUIRED,
        failure_class="object_detected",
        blocked_reasons=("object_detected",),
        manual_review_required=True,
        uncertain_physical_state=True,
        bed_state="OCCUPIED",
    ),
}


@dataclass
class MockPrintFlowCanaryReadinessAdapter:
    scenario: str = "ready"
    probes: list[dict[str, object]] = field(default_factory=list)
    network_calls_made: int = 0
    hardware_calls_made: int = 0

    def __post_init__(self) -> None:
        if self.scenario not in _SCENARIOS:
            raise ValueError(f"unsupported mock PrintFlow canary scenario: {self.scenario}")

    def probe(self, *, check_key: str, dry_run: bool, audit_only: bool) -> PrintFlowCanaryProbeResult:
        self.probes.append({"check_key": check_key, "dry_run": dry_run, "audit_only": audit_only})
        return _SCENARIOS[self.scenario]


class PrintFlowCanaryReadinessService:
    def __init__(self) -> None:
        self._lock = RLock()
        self.clear()

    def clear(self) -> None:
        with self._lock:
            self._records: OrderedDict[str, dict[str, Any]] = OrderedDict()
            self._status_counts: Counter[str] = Counter()
            self._sentinels = _new_sentinels()

    def create_check(
        self,
        payload: dict[str, Any],
        *,
        adapter: MockPrintFlowCanaryReadinessAdapter,
        human_approval_required: bool = True,
    ) -> dict[str, Any]:
        check_key = _nonempty(payload.get("check_key"))
        if check_key is None:
            raise PrintFlowCanaryError("missing_check_key", "check_key is required")
        if payload.get("dry_run") is not True:
            raise PrintFlowCanaryError("dry_run_required", "PrintFlow canary readiness is dry-run only")
        if payload.get("audit_only") is not True:
            raise PrintFlowCanaryError("audit_only_required", "PrintFlow canary readiness is audit-only")

        operator_approved = payload.get("operator_approved") is True
        if human_approval_required and not operator_approved:
            return self._approval_required_payload(check_key, payload, adapter)

        with self._lock:
            existing = self._records.get(check_key)
            if existing is not None:
                return dict(existing)

            result = adapter.probe(check_key=check_key, dry_run=True, audit_only=True)
            record = self._record_from_probe(
                check_key,
                payload,
                result,
                adapter=adapter,
                human_approval_required=human_approval_required,
                operator_approved=operator_approved,
            )
            self._records[check_key] = record
            self._status_counts[record["status"]] += 1
            return dict(record)

    def status_snapshot(self) -> dict[str, Any]:
        with self._lock:
            recent = list(self._records.values())[-10:]
            return {
                "mode": "MOCK_READINESS_ONLY",
                "readiness_checks": len(self._records),
                "status_counts": dict(sorted(self._status_counts.items())),
                "sentinels": dict(self._sentinels),
                "recent_checks": [_public(record) for record in recent],
            }

    def render_metrics(self) -> str:
        with self._lock:
            total = len(self._records)
            status_counts = dict(self._status_counts)
            sentinels = dict(self._sentinels)

        lines = [
            "# HELP bambuddy_printflow_canary_readiness_checks_total Mock-only PrintFlow canary readiness checks.",
            "# TYPE bambuddy_printflow_canary_readiness_checks_total counter",
            f"bambuddy_printflow_canary_readiness_checks_total {total}",
            "",
            "# HELP bambuddy_printflow_canary_status_total Mock-only PrintFlow canary readiness checks by status.",
            "# TYPE bambuddy_printflow_canary_status_total counter",
        ]
        for status, count in sorted(status_counts.items()):
            lines.append(f'bambuddy_printflow_canary_status_total{{status="{_escape(status)}"}} {count}')

        lines.extend(
            [
                "",
                "# HELP bambuddy_printflow_forbidden_side_effects_total Sentinel counters for forbidden WP-060-A side effects.",
                "# TYPE bambuddy_printflow_forbidden_side_effects_total counter",
            ]
        )
        for effect, count in sorted(sentinels.items()):
            lines.append(f'bambuddy_printflow_forbidden_side_effects_total{{effect="{_escape(effect)}"}} {count}')
        lines.append("")
        return "\n".join(lines)

    def _approval_required_payload(
        self,
        check_key: str,
        payload: dict[str, Any],
        adapter: MockPrintFlowCanaryReadinessAdapter,
    ) -> dict[str, Any]:
        return _public(
            {
                **_base_record(check_key, payload),
                "status": APPROVAL_REQUIRED,
                "ready_for_canary": False,
                "blocked_reasons": ["human_approval_required"],
                "failure_class": "human_approval_required",
                "human_approval_required": True,
                "operator_approved": False,
                "stored": False,
                "adapter_network_calls_made": adapter.network_calls_made,
                "adapter_hardware_calls_made": adapter.hardware_calls_made,
            }
        )

    def _record_from_probe(
        self,
        check_key: str,
        payload: dict[str, Any],
        result: PrintFlowCanaryProbeResult,
        *,
        adapter: MockPrintFlowCanaryReadinessAdapter,
        human_approval_required: bool,
        operator_approved: bool,
    ) -> dict[str, Any]:
        return {
            **_base_record(check_key, payload),
            "check_id": _check_id(check_key),
            "status": result.status,
            "ready_for_canary": result.status == READINESS_PASSED,
            "blocked_reasons": list(result.blocked_reasons),
            "failure_class": result.failure_class,
            "manual_review_required": result.manual_review_required,
            "uncertain_physical_state": result.uncertain_physical_state,
            "bed_state": result.bed_state,
            "retryable": result.retryable,
            "human_approval_required": human_approval_required,
            "operator_approved": operator_approved,
            "stored": True,
            "adapter_network_calls_made": adapter.network_calls_made,
            "adapter_hardware_calls_made": adapter.hardware_calls_made,
        }


def _base_record(check_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_key": check_key,
        "printer_alias": _nonempty(payload.get("printer_alias")),
        "cycle_alias": _nonempty(payload.get("cycle_alias")),
        "dry_run": True,
        "audit_only": True,
        "mock_only": True,
        "ready_for_canary": False,
        "manual_review_required": False,
        "uncertain_physical_state": False,
        "bed_state": "UNKNOWN",
        "retryable": False,
        "printflow_action": None,
        "printer_action": None,
        "queue_action": None,
        "scheduler_action": None,
        "erp_action": None,
        "obico_action": None,
        "bed_action": None,
        "sentinels": _new_sentinels(),
        "payload_fingerprint": _fingerprint(payload),
    }


def _new_sentinels() -> dict[str, int]:
    return {effect: 0 for effect in FORBIDDEN_SIDE_EFFECTS}


def _check_id(check_key: str) -> str:
    return f"pfc:{hashlib.sha256(check_key.encode('utf-8')).hexdigest()[:16]}"


def _fingerprint(payload: dict[str, Any]) -> str:
    safe_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"metadata", "access_token", "api_key", "password"}
    }
    encoded = json.dumps(safe_payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _nonempty(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _public(record: dict[str, Any]) -> dict[str, Any]:
    return dict(record)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


printflow_canary_service = PrintFlowCanaryReadinessService()
