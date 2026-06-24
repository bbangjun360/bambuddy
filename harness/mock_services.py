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
DEFAULT_SCENARIO = os.environ.get("MOCK_SCENARIO", "success")

LOCK = threading.Lock()
STATE = {
    "scenario": DEFAULT_SCENARIO,
    "erp_documents": {},
    "bed_cycles": {},
    "request_count": 0,
}


def response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def maybe_fault(handler: BaseHTTPRequestHandler) -> bool:
    with LOCK:
        scenario = STATE["scenario"]
    if scenario == "http_500":
        response(handler, HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "injected failure"})
        return True
    if scenario == "rate_limit":
        handler.send_response(HTTPStatus.TOO_MANY_REQUESTS)
        handler.send_header("Retry-After", "1")
        handler.end_headers()
        return True
    if scenario == "timeout":
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

        if path in {"/health", "/erp/health", "/printflow/health"}:
            response(self, HTTPStatus.OK, {"status": "ok", "scenario": STATE["scenario"]})
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
            score = 0.95 if STATE["scenario"] == "obico_failure" else 0.02
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
            response(self, HTTPStatus.OK, {"status": "reset"})
            return

        if path == "/admin/scenario":
            payload = read_json(self)
            scenario = str(payload.get("scenario", "success"))
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
                    status = "failed" if STATE["scenario"] == "bed_failure" else "completed"
                    existing = {
                        "cycle_id": cycle_id,
                        "idempotency_key": key,
                        "status": status,
                        "dry_run": bool(payload.get("dry_run", True)),
                    }
                    STATE["bed_cycles"][cycle_id] = existing
            response(self, HTTPStatus.ACCEPTED, existing)
            return

        response(self, HTTPStatus.NOT_FOUND, {"error": "not found", "path": path})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(json.dumps({"service": "mock-services", "port": PORT, "status": "starting"}), flush=True)
    server.serve_forever()
