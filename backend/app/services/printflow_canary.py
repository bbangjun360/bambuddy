from __future__ import annotations

import http.client
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
REAL_CANARY_BLOCKED = "REAL_CANARY_BLOCKED"
REAL_CANARY_DISPATCHED = "REAL_CANARY_DISPATCHED"

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


@dataclass
class RealPrintFlowCanaryAdapter:
    base_url: str
    api_token: str
    timeout_seconds: float = 5.0
    network_calls_made: int = 0
    hardware_calls_made: int = 0

    def run_canary(
        self,
        *,
        job_id: str,
        target_printer_id: str,
        idempotency_key: str,
        dry_run: bool,
        audit_only: bool,
    ) -> dict[str, object]:
        scheme, host, prefix = _split_printflow_base_url(self.base_url)
        connection_cls = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
        connection = connection_cls(host, timeout=self.timeout_seconds)
        body = json.dumps(
            {
                "job_id": job_id,
                "target_printer_id": target_printer_id,
                "idempotency_key": idempotency_key,
                "dry_run": dry_run,
                "audit_only": audit_only,
            },
            sort_keys=True,
        ).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        self.network_calls_made += 1
        self.hardware_calls_made += 1
        try:
            connection.request("POST", _join_path(prefix, "/printflow/v1/canary/runs"), body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read()
        finally:
            connection.close()

        if response.status < 200 or response.status >= 300:
            raise PrintFlowCanaryError(
                "printflow_canary_failed",
                f"PrintFlow canary endpoint returned HTTP {response.status}",
            )

        try:
            decoded = json.loads(response_body.decode("utf-8")) if response_body.strip() else {}
        except json.JSONDecodeError:
            decoded = {}
        if not isinstance(decoded, dict):
            decoded = {}

        return {
            "status": _nonempty(decoded.get("status")) or REAL_CANARY_DISPATCHED,
            "adapter_run_id": _nonempty(decoded.get("adapter_run_id") or decoded.get("run_id")),
            "job_id": job_id,
            "target_printer_id": target_printer_id,
        }


class PrintFlowCanaryReadinessService:
    def __init__(self) -> None:
        self._lock = RLock()
        self.clear()

    def clear(self) -> None:
        with self._lock:
            self._records: OrderedDict[str, dict[str, Any]] = OrderedDict()
            self._real_canary_records: OrderedDict[str, dict[str, Any]] = OrderedDict()
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

    def create_real_canary(
        self,
        payload: dict[str, Any],
        *,
        adapter_factory,
        real_adapter_enabled: bool,
        global_dry_run: bool,
        human_approval_required: bool,
        single_printer_only: bool,
        base_url: str | None,
        api_token: str | None,
        expected_approval_phrase: str | None = None,
    ) -> dict[str, Any]:
        idempotency_key = _nonempty(payload.get("idempotency_key"))
        job_id = _nonempty(payload.get("job_id"))
        target_printer_ids = _target_printer_ids(payload.get("target_printer_ids"))
        target_printer_id = target_printer_ids[0] if len(target_printer_ids) == 1 else None
        base_url_value = _nonempty(base_url)
        api_token_value = _nonempty(api_token)
        submitted_phrase = _nonempty(payload.get("operator_approval_phrase"))
        expected_phrase = _nonempty(expected_approval_phrase)
        effective_dry_run = global_dry_run or payload.get("dry_run") is not False
        effective_audit_only = payload.get("audit_only") is not False

        blockers: list[str] = []
        if idempotency_key is None:
            blockers.append("missing_idempotency_key")
        if not real_adapter_enabled:
            blockers.append("real_adapter_disabled")
        if global_dry_run:
            blockers.append("global_dry_run_enabled")
        if payload.get("dry_run") is not False:
            blockers.append("request_dry_run")
        if payload.get("audit_only") is not False:
            blockers.append("audit_only")
        if not human_approval_required:
            blockers.append("human_approval_gate_disabled")
        if payload.get("operator_approved") is not True:
            blockers.append("operator_approval_required")
        if not single_printer_only:
            blockers.append("single_printer_gate_disabled")
        if len(target_printer_ids) != 1:
            blockers.append("single_printer_required")
        if job_id is None:
            blockers.append("missing_job_id")
        if target_printer_id is not None and job_id is not None:
            required_phrase = _required_real_canary_phrase(target_printer_id, job_id)
            if expected_phrase is not None and expected_phrase != required_phrase:
                blockers.append("approval_phrase_mismatch")
            if submitted_phrase is None:
                blockers.append("approval_phrase_required")
            elif submitted_phrase != required_phrase:
                blockers.append("approval_phrase_mismatch")
        elif submitted_phrase is None:
            blockers.append("approval_phrase_required")
        if base_url_value is None:
            blockers.append("missing_printflow_base_url")
        if api_token_value is None:
            blockers.append("missing_printflow_api_token")

        payload_fingerprint = _fingerprint(payload)

        with self._lock:
            existing = self._real_canary_records.get(idempotency_key) if idempotency_key is not None else None
            if existing is not None:
                replay_blockers = list(blockers)
                if existing.get("payload_fingerprint") != payload_fingerprint:
                    replay_blockers.append("idempotency_payload_mismatch")
                if replay_blockers:
                    return _public(
                        _real_canary_record(
                            idempotency_key,
                            payload,
                            job_id=job_id,
                            target_printer_ids=target_printer_ids,
                            target_printer_id=target_printer_id,
                            effective_dry_run=effective_dry_run,
                            effective_audit_only=effective_audit_only,
                            status=REAL_CANARY_BLOCKED,
                            ready_for_canary=False,
                            blocked_reasons=replay_blockers,
                            failure_class=replay_blockers[0],
                            stored=False,
                        )
                    )
                return dict(existing)

            if blockers:
                return _public(
                    _real_canary_record(
                        idempotency_key,
                        payload,
                        job_id=job_id,
                        target_printer_ids=target_printer_ids,
                        target_printer_id=target_printer_id,
                        effective_dry_run=effective_dry_run,
                        effective_audit_only=effective_audit_only,
                        status=REAL_CANARY_BLOCKED,
                        ready_for_canary=False,
                        blocked_reasons=blockers,
                        failure_class=blockers[0],
                        stored=False,
                    )
                )

            adapter = None
            try:
                adapter = adapter_factory(base_url=base_url_value, api_token=api_token_value)
                adapter_result = adapter.run_canary(
                    job_id=job_id,
                    target_printer_id=target_printer_id,
                    idempotency_key=idempotency_key,
                    dry_run=False,
                    audit_only=False,
                )
            except PrintFlowCanaryError as exc:
                record = _real_canary_record(
                    idempotency_key,
                    payload,
                    job_id=job_id,
                    target_printer_ids=target_printer_ids,
                    target_printer_id=target_printer_id,
                    effective_dry_run=effective_dry_run,
                    effective_audit_only=effective_audit_only,
                    status=MANUAL_REVIEW_REQUIRED,
                    ready_for_canary=False,
                    blocked_reasons=[exc.code],
                    failure_class=exc.code,
                    stored=True,
                    manual_review_required=True,
                    uncertain_physical_state=True,
                    adapter=adapter,
                )
                self._real_canary_records[idempotency_key] = record
                return dict(record)
            except Exception:
                record = _real_canary_record(
                    idempotency_key,
                    payload,
                    job_id=job_id,
                    target_printer_ids=target_printer_ids,
                    target_printer_id=target_printer_id,
                    effective_dry_run=effective_dry_run,
                    effective_audit_only=effective_audit_only,
                    status=MANUAL_REVIEW_REQUIRED,
                    ready_for_canary=False,
                    blocked_reasons=["real_adapter_exception"],
                    failure_class="real_adapter_exception",
                    stored=True,
                    manual_review_required=True,
                    uncertain_physical_state=True,
                    adapter=adapter,
                )
                self._real_canary_records[idempotency_key] = record
                return dict(record)

            record = _real_canary_record(
                idempotency_key,
                payload,
                job_id=job_id,
                target_printer_ids=target_printer_ids,
                target_printer_id=target_printer_id,
                effective_dry_run=effective_dry_run,
                effective_audit_only=effective_audit_only,
                status=_nonempty(adapter_result.get("status")) or REAL_CANARY_DISPATCHED,
                ready_for_canary=True,
                blocked_reasons=[],
                failure_class=None,
                stored=True,
                adapter_run_id=_nonempty(adapter_result.get("adapter_run_id")),
                adapter=adapter,
            )
            self._real_canary_records[idempotency_key] = record
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
        "adapter_network_calls_made": 0,
        "adapter_hardware_calls_made": 0,
        "payload_fingerprint": _fingerprint(payload),
    }


def _real_canary_record(
    idempotency_key: str | None,
    payload: dict[str, Any],
    *,
    job_id: str | None,
    target_printer_ids: list[str],
    target_printer_id: str | None,
    effective_dry_run: bool,
    effective_audit_only: bool,
    status: str,
    ready_for_canary: bool,
    blocked_reasons: list[str],
    failure_class: str | None,
    stored: bool,
    manual_review_required: bool = False,
    uncertain_physical_state: bool = False,
    adapter_run_id: str | None = None,
    adapter: object | None = None,
) -> dict[str, Any]:
    return {
        "idempotency_key": idempotency_key,
        "run_id": _real_canary_id(idempotency_key) if idempotency_key is not None else None,
        "job_id": job_id,
        "target_printer_ids": target_printer_ids,
        "target_printer_id": target_printer_id,
        "dry_run": effective_dry_run,
        "audit_only": effective_audit_only,
        "mock_only": False,
        "status": status,
        "ready_for_canary": ready_for_canary,
        "blocked_reasons": blocked_reasons,
        "failure_class": failure_class,
        "manual_review_required": manual_review_required,
        "uncertain_physical_state": uncertain_physical_state,
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
        "stored": stored,
        "adapter_run_id": adapter_run_id,
        "adapter_network_calls_made": int(getattr(adapter, "network_calls_made", 0)),
        "adapter_hardware_calls_made": int(getattr(adapter, "hardware_calls_made", 0)),
        "payload_fingerprint": _fingerprint(payload),
    }


def _target_printer_ids(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [text for item in value if (text := _nonempty(item)) is not None]
    text = _nonempty(value)
    return [text] if text is not None else []


def _required_real_canary_phrase(target_printer_id: str, job_id: str) -> str:
    return f"CONFIRM_REAL_PRINTFLOW_CANARY {target_printer_id} {job_id}"


def _real_canary_id(idempotency_key: str) -> str:
    return f"pfc-real:{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()[:16]}"


def _split_printflow_base_url(base_url: str) -> tuple[str, str, str]:
    text = base_url.strip().rstrip("/")
    if text.startswith("https://"):
        scheme = "https"
        rest = text[len("https://") :]
    elif text.startswith("http://"):
        scheme = "http"
        rest = text[len("http://") :]
    else:
        raise PrintFlowCanaryError("invalid_printflow_base_url", "PrintFlow base URL must start with http:// or https://")
    host, _, prefix = rest.partition("/")
    if not host:
        raise PrintFlowCanaryError("invalid_printflow_base_url", "PrintFlow base URL must include a host")
    return scheme, host, f"/{prefix.strip('/')}" if prefix else ""


def _join_path(prefix: str, suffix: str) -> str:
    left = prefix.rstrip("/")
    right = suffix if suffix.startswith("/") else f"/{suffix}"
    return f"{left}{right}" if left else right


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
