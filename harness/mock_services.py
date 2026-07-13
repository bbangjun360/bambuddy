#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

PORT = int(os.environ.get("MOCK_PORT", "9099"))
PRINTFLOW_CANARY_READY_SCENARIO = "printflow_canary_ready"
PRINTFLOW_CANARY_FAILURES = {
    "printflow_canary_heartbeat_loss": {
        "status": "blocked",
        "failure_class": "adapter_heartbeat_loss",
        "manual_review_required": False,
        "uncertain_physical_state": False,
        "bed_state": "UNKNOWN",
    },
    "printflow_canary_camera_unavailable": {
        "status": "blocked",
        "failure_class": "camera_unavailable",
        "manual_review_required": False,
        "uncertain_physical_state": False,
        "bed_state": "UNKNOWN",
    },
    "printflow_canary_estop_active": {
        "status": "manual_review",
        "failure_class": "e_stop_active",
        "manual_review_required": True,
        "uncertain_physical_state": True,
        "bed_state": "UNKNOWN",
    },
    "printflow_canary_motion_timeout": {
        "status": "manual_review",
        "failure_class": "motion_timeout",
        "manual_review_required": True,
        "uncertain_physical_state": True,
        "bed_state": "UNKNOWN",
    },
    "printflow_canary_reply_lost": {
        "status": "manual_review",
        "failure_class": "command_reply_lost",
        "manual_review_required": True,
        "uncertain_physical_state": True,
        "bed_state": "UNKNOWN",
    },
    "printflow_canary_object_detected": {
        "status": "manual_review",
        "failure_class": "object_detected",
        "manual_review_required": True,
        "uncertain_physical_state": True,
        "bed_state": "OCCUPIED",
    },
}
PRINTFLOW_CANARY_SCENARIOS = frozenset({
    PRINTFLOW_CANARY_READY_SCENARIO,
    *PRINTFLOW_CANARY_FAILURES,
})
PRINTFLOW_CANARY_STATUSES = ("blocked", "manual_review", "ready")
PRINTFLOW_CANARY_FORBIDDEN_SENTINELS = (
    "actuator_commands_sent",
    "queue_dispatches",
    "scheduler_dispatches",
    "erp_submit_calls",
    "erp_inventory_post_calls",
    "erp_accounting_post_calls",
    "obico_calls",
    "bed_cycle_mutations",
)
ALLOWED_SCENARIOS = frozenset({
    "success",
    "http_500",
    "rate_limit",
    "timeout",
    "obico_failure",
    "bed_failure",
    "bed_timeout",
    "erp_missing_artifact",
    "erp_missing_profile",
    "erp_invalid_payload",
    "erp_expired_token",
    "erp_draft_timeout_after_create",
    "erp_draft_invalid_payload",
    "erp_draft_reconciliation_mismatch",
}) | PRINTFLOW_CANARY_SCENARIOS
DEFAULT_SCENARIO = os.environ.get("MOCK_SCENARIO", "success")
if DEFAULT_SCENARIO not in ALLOWED_SCENARIOS:
    DEFAULT_SCENARIO = "success"

OBICO_SHADOW_EVENTS = {
    "healthy": {
        "event_id": "shadow-healthy-0001",
        "event_type": "PRINT_HEALTH_OK",
        "printer_id": "printer-fixture-001",
        "print_id": "print-fixture-cube-001",
        "observed_at": "2026-06-24T10:00:00Z",
        "confidence": 0.02,
        "metadata": {"scenario": "healthy", "synthetic": True},
    },
    "spaghetti": {
        "event_id": "shadow-spaghetti-0001",
        "event_type": "POSSIBLE_SPAGHETTI",
        "printer_id": "printer-fixture-001",
        "print_id": "print-fixture-cube-001",
        "observed_at": "2026-06-24T10:01:00Z",
        "confidence": 0.95,
        "metadata": {"scenario": "spaghetti", "synthetic": True},
    },
    "layer-shift": {
        "event_id": "shadow-layer-shift-0001",
        "event_type": "POSSIBLE_LAYER_SHIFT",
        "printer_id": "printer-fixture-001",
        "print_id": "print-fixture-cube-001",
        "observed_at": "2026-06-24T10:02:00Z",
        "confidence": 0.88,
        "metadata": {"scenario": "layer-shift", "synthetic": True},
    },
    "detachment": {
        "event_id": "shadow-detachment-0001",
        "event_type": "POSSIBLE_DETACHMENT",
        "printer_id": "printer-fixture-001",
        "print_id": "print-fixture-cube-001",
        "observed_at": "2026-06-24T10:03:00Z",
        "confidence": 0.82,
        "metadata": {"scenario": "detachment", "synthetic": True},
    },
    "camera-unavailable": {
        "event_id": "shadow-camera-unavailable-0001",
        "event_type": "CAMERA_UNAVAILABLE",
        "printer_id": "printer-fixture-001",
        "print_id": "print-fixture-cube-001",
        "observed_at": "2026-06-24T10:04:00Z",
        "confidence": None,
        "metadata": {"scenario": "camera-unavailable", "synthetic": True},
    },
    "timeout": {
        "event_id": "shadow-timeout-0001",
        "event_type": "MONITORING_TIMEOUT",
        "printer_id": "printer-fixture-001",
        "print_id": "print-fixture-cube-001",
        "observed_at": "2026-06-24T10:05:00Z",
        "confidence": None,
        "metadata": {"scenario": "timeout", "synthetic": True},
    },
    "invalid": {
        "event_type": "POSSIBLE_SPAGHETTI",
        "printer_id": "",
        "metadata": {"scenario": "invalid", "synthetic": True},
    },
}

def new_printflow_canary_sentinels() -> dict[str, int]:
    return {key: 0 for key in PRINTFLOW_CANARY_FORBIDDEN_SENTINELS}


LOCK = threading.Lock()
STATE = {
    "scenario": DEFAULT_SCENARIO,
    "erp_documents": {},
    "erp_draft_documents": {},
    "erp_submit_calls": 0,
    "erp_inventory_post_calls": 0,
    "erp_accounting_post_calls": 0,
    "bed_cycles": {},
    "printflow_canary_checks": {},
    "printflow_canary_sentinels": new_printflow_canary_sentinels(),
    "printflow_canary_status_counts": {status: 0 for status in PRINTFLOW_CANARY_STATUSES},
    "request_count": 0,
    "failure_counts": {scenario: 0 for scenario in sorted(ALLOWED_SCENARIOS)},
}


def response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, status: int, body: str, content_type: str) -> None:
    encoded = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def record_failure(scenario: str) -> None:
    with LOCK:
        STATE["failure_counts"][scenario] = STATE["failure_counts"].get(scenario, 0) + 1


def maybe_fault(handler: BaseHTTPRequestHandler) -> bool:
    with LOCK:
        scenario = STATE["scenario"]
    if scenario == "http_500":
        record_failure(scenario)
        response(handler, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "injected failure"})
        return True
    if scenario == "rate_limit":
        record_failure(scenario)
        handler.send_response(HTTPStatus.TOO_MANY_REQUESTS)
        handler.send_header("Retry-After", "1")
        handler.end_headers()
        return True
    if scenario == "timeout":
        record_failure(scenario)
        time.sleep(5)
    return False


def erp_work_order_payload(work_order_id: str, scenario: str) -> dict:
    payload = {
        "name": work_order_id,
        "production_item": "SKU-HARNESS",
        "qty": 1,
        "status": "Submitted",
        "customer": "Customer HARNESS",
        "custom_artifact_reference": "fixture-cube-v1",
        "custom_profile_set_id": "p1p-pla-fixture-v1",
    }
    if scenario == "erp_missing_artifact":
        payload["custom_artifact_reference"] = "missing-artifact-v1"
    elif scenario == "erp_missing_profile":
        payload["custom_profile_set_id"] = None
    elif scenario == "erp_invalid_payload":
        payload.pop("name")
    return payload


def erp_draft_result_payload(event_id: str, payload: dict, sequence: int) -> dict:
    return {
        "name": f"FDR-HARNESS-{sequence:04d}",
        "doctype": "Farm Draft Result",
        "docstatus": 0,
        "status": "Draft",
        "farm_event_id": event_id,
        "production_request_id": payload.get("production_request_id"),
        "external_work_order_id": payload.get("external_work_order_id"),
        "production_item": payload.get("production_item"),
        "quantity_completed": payload.get("quantity_completed"),
        "completed_at": payload.get("completed_at"),
    }


def lookup_erp_draft_document(event_id: str, scenario: str) -> dict | None:
    with LOCK:
        existing = STATE["erp_draft_documents"].get(event_id)
        if existing is None:
            return None
        document = json.loads(json.dumps(existing))
    if scenario == "erp_draft_reconciliation_mismatch":
        document["quantity_completed"] = int(document.get("quantity_completed") or 0) + 1
    return document


def prometheus_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def printflow_canary_sentinels_snapshot() -> dict[str, int]:
    return dict(STATE["printflow_canary_sentinels"])


def printflow_canary_readiness_payload(scenario: str) -> dict:
    payload = {
        "adapter_id": "printflow-canary-mock",
        "canary_device_id": "printflow-canary-fixture-001",
        "scenario": scenario,
        "synthetic": True,
        "canary_enabled": False,
        "dry_run": True,
        "audit_only": True,
        "status": "blocked",
        "blocked_reasons": ["feature_disabled"],
        "failure_class": None,
        "manual_review_required": False,
        "uncertain_physical_state": False,
        "bed_state": "UNKNOWN",
        "sentinels": printflow_canary_sentinels_snapshot(),
    }
    if scenario == PRINTFLOW_CANARY_READY_SCENARIO:
        payload.update({
            "canary_enabled": True,
            "status": "ready",
            "blocked_reasons": [],
            "bed_state": "READY",
        })
    elif scenario in PRINTFLOW_CANARY_FAILURES:
        failure = PRINTFLOW_CANARY_FAILURES[scenario]
        payload.update({
            "canary_enabled": True,
            "status": failure["status"],
            "blocked_reasons": [failure["failure_class"]],
            "failure_class": failure["failure_class"],
            "manual_review_required": failure["manual_review_required"],
            "uncertain_physical_state": failure["uncertain_physical_state"],
            "bed_state": failure["bed_state"],
        })
    return payload


def printflow_canary_check_payload(request_payload: dict, scenario: str) -> dict:
    readiness = printflow_canary_readiness_payload(scenario)
    return {
        **readiness,
        "check_id": f"pfc-{len(STATE['printflow_canary_checks']) + 1:04d}",
        "idempotency_key": request_payload.get("idempotency_key"),
        "printer_id": request_payload.get("printer_id"),
        "cycle_id": request_payload.get("cycle_id"),
    }


def metrics_payload() -> str:
    with LOCK:
        scenario = str(STATE["scenario"])
        request_count = int(STATE["request_count"])
        failure_counts = dict(STATE["failure_counts"])
        printflow_canary_checks_total = len(STATE["printflow_canary_checks"])
        printflow_canary_status_counts = dict(STATE["printflow_canary_status_counts"])
        printflow_canary_sentinels = printflow_canary_sentinels_snapshot()

    lines = [
        "# HELP farm_harness_mock_up Mock service exporter availability.",
        "# TYPE farm_harness_mock_up gauge",
        "farm_harness_mock_up 1",
        "",
        "# HELP farm_harness_mock_requests_total Requests handled by mock services.",
        "# TYPE farm_harness_mock_requests_total counter",
        f"farm_harness_mock_requests_total {request_count}",
        "",
        "# HELP farm_harness_mock_scenario_info Current deterministic mock scenario.",
        "# TYPE farm_harness_mock_scenario_info gauge",
    ]
    for candidate in sorted(ALLOWED_SCENARIOS):
        value = 1 if candidate == scenario else 0
        lines.append(f'farm_harness_mock_scenario_info{{scenario="{prometheus_escape(candidate)}"}} {value}')

    lines.extend([
        "",
        "# HELP farm_harness_mock_failures_total Injected mock-service failures by scenario.",
        "# TYPE farm_harness_mock_failures_total counter",
    ])
    for candidate in sorted(ALLOWED_SCENARIOS):
        count = int(failure_counts.get(candidate, 0))
        lines.append(f'farm_harness_mock_failures_total{{scenario="{prometheus_escape(candidate)}"}} {count}')

    lines.extend([
        "",
        "# HELP farm_harness_printflow_canary_readiness_checks_total Mock PrintFlow canary readiness checks created.",
        "# TYPE farm_harness_printflow_canary_readiness_checks_total counter",
        f"farm_harness_printflow_canary_readiness_checks_total {printflow_canary_checks_total}",
        "",
        "# HELP farm_harness_printflow_canary_status_total Mock PrintFlow canary readiness checks by status.",
        "# TYPE farm_harness_printflow_canary_status_total counter",
    ])
    for status in PRINTFLOW_CANARY_STATUSES:
        count = int(printflow_canary_status_counts.get(status, 0))
        lines.append(f'farm_harness_printflow_canary_status_total{{status="{prometheus_escape(status)}"}} {count}')

    lines.extend([
        "",
        "# HELP farm_harness_printflow_forbidden_side_effects_total Sentinel counters for forbidden WP-060-A side effects.",
        "# TYPE farm_harness_printflow_forbidden_side_effects_total counter",
    ])
    for effect in PRINTFLOW_CANARY_FORBIDDEN_SENTINELS:
        count = int(printflow_canary_sentinels.get(effect, 0))
        lines.append(f'farm_harness_printflow_forbidden_side_effects_total{{effect="{prometheus_escape(effect)}"}} {count}')

    lines.append("")
    return "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    server_version = "FarmHarnessMock/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(json.dumps({
            "service": "mock-services",
            "message": fmt % args,
            "path": self.path,
        }, ensure_ascii=False), flush=True)

    def do_GET(self) -> None:
        with LOCK:
            STATE["request_count"] += 1

        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/metrics":
            text_response(self, HTTPStatus.OK, metrics_payload(), "text/plain; version=0.0.4; charset=utf-8")
            return

        if path in {"/health", "/erp/health", "/printflow/health"}:
            with LOCK:
                scenario = STATE["scenario"]
            response(self, HTTPStatus.OK, {"status": "ok", "scenario": scenario})
            return

        if path == "/printflow/v1/canary/readiness":
            with LOCK:
                scenario = STATE["scenario"]
                payload = printflow_canary_readiness_payload(scenario)
            response(self, HTTPStatus.OK, payload)
            return

        if path in {"/api/resource/Work Order", "/erp/api/resource/Work Order"}:
            if maybe_fault(self):
                return
            with LOCK:
                scenario = STATE["scenario"]
            response(self, HTTPStatus.OK, {"data": [erp_work_order_payload("WO-HARNESS-0001", scenario)]})
            return

        if path in {"/api/resource/Farm Draft Result", "/erp/api/resource/Farm Draft Result"}:
            query = parse_qs(parsed.query)
            event_id = (query.get("farm_event_id") or [None])[0]
            if not event_id:
                try:
                    filters = json.loads((query.get("filters") or ["[]"])[0])
                except json.JSONDecodeError:
                    response(self, HTTPStatus.BAD_REQUEST, {"error": "invalid filters"})
                    return
                for item in filters if isinstance(filters, list) else []:
                    if isinstance(item, list) and len(item) == 3 and item[:2] == ["farm_event_id", "="]:
                        event_id = item[2]
                        break
            with LOCK:
                scenario = STATE["scenario"]
            if scenario == "erp_expired_token" or self.headers.get("Authorization") == "token expired-token":
                response(self, HTTPStatus.UNAUTHORIZED, {"error": "expired token"})
                return
            if maybe_fault(self):
                return
            if not event_id:
                response(self, HTTPStatus.BAD_REQUEST, {"error": "missing farm_event_id"})
                return
            document = lookup_erp_draft_document(event_id, scenario)
            if path.startswith("/api/"):
                response(self, HTTPStatus.OK, {"data": [] if document is None else [document]})
                return
            if document is None:
                response(self, HTTPStatus.NOT_FOUND, {"error": "draft not found"})
                return
            response(self, HTTPStatus.OK, {"data": document})
            return

        match = re.fullmatch(r"/(?:erp/)?api/resource/Work Order/([^/]+)", path)
        if match:
            with LOCK:
                scenario = STATE["scenario"]
            if scenario == "erp_expired_token" or self.headers.get("Authorization") == "token expired-token":
                response(self, HTTPStatus.UNAUTHORIZED, {"error": "expired token"})
                return
            if maybe_fault(self):
                return
            response(self, HTTPStatus.OK, {"data": erp_work_order_payload(match.group(1), scenario)})
            return

        match = re.fullmatch(r"/printflow/v1/cycles/([^/]+)", path)
        if match:
            cycle_id = match.group(1)
            with LOCK:
                cycle = STATE["bed_cycles"].get(cycle_id)
            if cycle is None:
                response(self, HTTPStatus.NOT_FOUND, {"error": "cycle not found"})
                return
            response(self, HTTPStatus.OK, cycle)
            return

        if path == "/obico/p/":
            query = parse_qs(parsed.query)
            with LOCK:
                scenario = STATE["scenario"]
            score = 0.95 if scenario == "obico_failure" else 0.02
            response(self, HTTPStatus.OK, {
                "detections": [] if score < 0.5 else [{"label": "failure", "score": score}],
                "image_received": bool(query.get("img")),
            })
            return

        match = re.fullmatch(r"/obico-shadow/v1/events/([^/]+)", path)
        if match:
            scenario_name = match.group(1)
            payload = OBICO_SHADOW_EVENTS.get(scenario_name)
            if payload is None:
                response(self, HTTPStatus.NOT_FOUND, {"error": "unknown obico shadow scenario", "allowed": sorted(OBICO_SHADOW_EVENTS)})
                return
            response(self, HTTPStatus.OK, json.loads(json.dumps(payload)))
            return

        if path == "/admin/state":
            with LOCK:
                snapshot = json.loads(json.dumps(STATE))
            response(self, HTTPStatus.OK, snapshot)
            return

        response(self, HTTPStatus.NOT_FOUND, {"error": "not found", "path": path})

    def do_POST(self) -> None:
        with LOCK:
            STATE["request_count"] += 1

        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/admin/reset":
            with LOCK:
                STATE["scenario"] = DEFAULT_SCENARIO
                STATE["erp_documents"].clear()
                STATE["erp_draft_documents"].clear()
                STATE["erp_submit_calls"] = 0
                STATE["erp_inventory_post_calls"] = 0
                STATE["erp_accounting_post_calls"] = 0
                STATE["bed_cycles"].clear()
                STATE["printflow_canary_checks"].clear()
                STATE["printflow_canary_sentinels"] = new_printflow_canary_sentinels()
                STATE["printflow_canary_status_counts"] = {status: 0 for status in PRINTFLOW_CANARY_STATUSES}
                STATE["request_count"] = 0
                STATE["failure_counts"] = {scenario: 0 for scenario in sorted(ALLOWED_SCENARIOS)}
            response(self, HTTPStatus.OK, {"status": "reset"})
            return

        if path == "/admin/scenario":
            payload = read_json(self)
            scenario = str(payload.get("scenario", "success"))
            if scenario not in ALLOWED_SCENARIOS:
                response(self, HTTPStatus.BAD_REQUEST, {
                    "error": "unknown scenario",
                    "allowed": sorted(ALLOWED_SCENARIOS),
                })
                return
            with LOCK:
                STATE["scenario"] = scenario
            response(self, HTTPStatus.OK, {"scenario": scenario})
            return

        match = re.fullmatch(r"/(?:erp/)?api/resource/Farm Draft Result/([^/]+)/submit", path)
        if match:
            with LOCK:
                STATE["erp_submit_calls"] += 1
            response(self, HTTPStatus.METHOD_NOT_ALLOWED, {"error": "submit disabled in harness"})
            return

        if path in {"/api/resource/Farm Draft Result", "/erp/api/resource/Farm Draft Result"}:
            with LOCK:
                scenario = STATE["scenario"]
            if scenario == "erp_expired_token" or self.headers.get("Authorization") == "token expired-token":
                response(self, HTTPStatus.UNAUTHORIZED, {"error": "expired token"})
                return
            if maybe_fault(self):
                return
            payload = read_json(self)
            key = self.headers.get("Idempotency-Key") or payload.get("farm_event_id")
            if not key:
                response(self, HTTPStatus.BAD_REQUEST, {"error": "missing idempotency key"})
                return
            with LOCK:
                existing = STATE["erp_draft_documents"].get(key)
                if existing is None:
                    existing = erp_draft_result_payload(key, payload, len(STATE["erp_draft_documents"]) + 1)
                    if scenario == "erp_draft_invalid_payload":
                        existing = {"name": existing["name"], "farm_event_id": key}
                    STATE["erp_draft_documents"][key] = existing
            if scenario == "erp_draft_timeout_after_create":
                record_failure(scenario)
                time.sleep(5)
            response(self, HTTPStatus.OK, {"data": existing})
            return

        if path == "/erp/api/resource/Stock Entry":
            if maybe_fault(self):
                return
            payload = read_json(self)
            key = self.headers.get("Idempotency-Key") or payload.get("farm_event_id")
            if not key:
                response(self, HTTPStatus.BAD_REQUEST, {"error": "missing idempotency key"})
                return
            with LOCK:
                STATE["erp_inventory_post_calls"] += 1
                existing = STATE["erp_documents"].get(key)
                if existing is None:
                    existing = {
                        "name": f"STE-HARNESS-{len(STATE['erp_documents']) + 1:04d}",
                        "docstatus": 0,
                        "farm_event_id": key,
                    }
                    STATE["erp_documents"][key] = existing
            response(self, HTTPStatus.OK, {"data": existing})
            return

        if path in {"/erp/api/resource/GL Entry", "/erp/api/resource/Sales Invoice", "/erp/api/resource/Payment Entry"}:
            with LOCK:
                STATE["erp_accounting_post_calls"] += 1
            response(self, HTTPStatus.METHOD_NOT_ALLOWED, {"error": "accounting posting disabled in harness"})
            return

        if path == "/printflow/v1/cycles":
            if maybe_fault(self):
                return
            payload = read_json(self)
            key = payload.get("idempotency_key")
            if not key:
                response(self, HTTPStatus.BAD_REQUEST, {"error": "missing idempotency_key"})
                return
            with LOCK:
                existing = next(
                    (c for c in STATE["bed_cycles"].values()
                     if c.get("idempotency_key") == key),
                    None,
                )
                if existing is None:
                    cycle_id = payload.get("cycle_id") or str(uuid.uuid4())
                    scenario = STATE["scenario"]
                    if scenario == "bed_failure":
                        existing = {
                            "cycle_id": cycle_id,
                            "idempotency_key": key,
                            "status": "failed",
                            "dry_run": bool(payload.get("dry_run", True)),
                            "failure_class": "simulated_failure",
                            "manual_review_required": True,
                        }
                    elif scenario == "bed_timeout":
                        existing = {
                            "cycle_id": cycle_id,
                            "idempotency_key": key,
                            "status": "timeout",
                            "dry_run": bool(payload.get("dry_run", True)),
                            "failure_class": "simulated_timeout",
                            "manual_review_required": True,
                        }
                    else:
                        existing = {
                            "cycle_id": cycle_id,
                            "idempotency_key": key,
                            "status": "completed",
                            "dry_run": bool(payload.get("dry_run", True)),
                            "manual_review_required": False,
                        }
                    STATE["bed_cycles"][cycle_id] = existing
            response(self, HTTPStatus.ACCEPTED, existing)
            return

        if path == "/printflow/v1/canary/readiness/check":
            payload = read_json(self)
            key = payload.get("idempotency_key")
            if not key:
                response(self, HTTPStatus.BAD_REQUEST, {"error": "missing idempotency_key"})
                return
            if payload.get("dry_run") is not True:
                response(self, HTTPStatus.BAD_REQUEST, {"error": "dry_run_required"})
                return
            if payload.get("audit_only") is not True:
                response(self, HTTPStatus.BAD_REQUEST, {"error": "audit_only_required"})
                return
            with LOCK:
                existing = STATE["printflow_canary_checks"].get(key)
                if existing is None:
                    scenario = STATE["scenario"]
                    existing = printflow_canary_check_payload(payload, scenario)
                    STATE["printflow_canary_checks"][key] = existing
                    status = existing["status"]
                    STATE["printflow_canary_status_counts"][status] = (
                        STATE["printflow_canary_status_counts"].get(status, 0) + 1
                    )
            response(self, HTTPStatus.ACCEPTED, existing)
            return

        response(self, HTTPStatus.NOT_FOUND, {"error": "not found", "path": path})


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    server = ReusableThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(json.dumps({"service": "mock-services", "port": PORT, "status": "starting"}), flush=True)
    server.serve_forever()
