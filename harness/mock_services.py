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
})
DEFAULT_SCENARIO = os.environ.get("MOCK_SCENARIO", "success")
if DEFAULT_SCENARIO not in ALLOWED_SCENARIOS:
    DEFAULT_SCENARIO = "success"

LOCK = threading.Lock()
STATE = {
    "scenario": DEFAULT_SCENARIO,
    "erp_documents": {},
    "bed_cycles": {},
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


def prometheus_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def metrics_payload() -> str:
    with LOCK:
        scenario = str(STATE["scenario"])
        request_count = int(STATE["request_count"])
        failure_counts = dict(STATE["failure_counts"])

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

        if path == "/erp/api/resource/Work Order":
            if maybe_fault(self):
                return
            with LOCK:
                scenario = STATE["scenario"]
            response(self, HTTPStatus.OK, {"data": [erp_work_order_payload("WO-HARNESS-0001", scenario)]})
            return

        match = re.fullmatch(r"/erp/api/resource/Work Order/([^/]+)", path)
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
                STATE["bed_cycles"].clear()
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

        if path == "/erp/api/resource/Stock Entry":
            if maybe_fault(self):
                return
            payload = read_json(self)
            key = self.headers.get("Idempotency-Key") or payload.get("farm_event_id")
            if not key:
                response(self, HTTPStatus.BAD_REQUEST, {"error": "missing idempotency key"})
                return
            with LOCK:
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

        response(self, HTTPStatus.NOT_FOUND, {"error": "not found", "path": path})


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    server = ReusableThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(json.dumps({"service": "mock-services", "port": PORT, "status": "starting"}), flush=True)
    server.serve_forever()
