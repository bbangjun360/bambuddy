#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

PORT = int(os.environ.get("OBSERVER_PORT", "9101"))
BAMBUDDY_BASE_URL = os.environ.get("BAMBUDDY_BASE_URL", "http://bambuddy:8000").rstrip("/")
ORCA_BASE_URL = os.environ.get("ORCA_BASE_URL", "http://orca-slicer-api:3000").rstrip("/")
ORCA_EVIDENCE_PATH = Path(
    os.environ.get("ORCA_EVIDENCE_PATH", "/app/harness/artifacts/orca/fixture-cube-v1.evidence.json")
)
Probe = Callable[[str], tuple[bool, dict]]


def probe_json(url: str) -> tuple[bool, dict]:
    try:
        with urllib.request.urlopen(url, timeout=2) as result:
            body = result.read(8192).decode("utf-8", errors="replace")
            if not (200 <= result.status < 400):
                return False, {"status_code": result.status}
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                payload = {"raw": body[:200]}
            return True, payload
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, {"error": exc.__class__.__name__}


def escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def metric_line(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    if labels:
        rendered = ",".join(f'{key}="{escape_label(str(val))}"' for key, val in sorted(labels.items()))
        return f"{name}{{{rendered}}} {value}"
    return f"{name} {value}"


def _extract_orca_version(payload: dict) -> str:
    checks = payload.get("checks") if isinstance(payload, dict) else None
    if not isinstance(checks, dict):
        return "unknown"
    for key, value in checks.items():
        if key == "dataPath":
            continue
        if isinstance(value, dict) and value.get("version"):
            return str(value["version"])
    return "unknown"


def read_orca_evidence(path: Path) -> tuple[int, int, str]:
    if not path.exists():
        return 0, 0, "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0, 0, "invalid"
    healthy = bool(data.get("healthy"))
    artifact_size = int(data.get("artifact_size") or 0)
    status = "success" if healthy else "failure"
    return 1 if healthy else 0, artifact_size, status


def build_metrics(
    *,
    bambuddy_base_url: str = BAMBUDDY_BASE_URL,
    orca_base_url: str = ORCA_BASE_URL,
    evidence_path: Path = ORCA_EVIDENCE_PATH,
    probe_json: Probe = probe_json,
) -> str:
    bambuddy_ok, _bambuddy_payload = probe_json(f"{bambuddy_base_url.rstrip('/')}/health")
    orca_ok, orca_payload = probe_json(f"{orca_base_url.rstrip('/')}/health")
    orca_version = _extract_orca_version(orca_payload) if orca_ok else "unknown"
    slice_success, artifact_bytes, slice_status = read_orca_evidence(evidence_path)

    lines = [
        "# HELP farm_harness_observer_up Harness observer exporter availability.",
        "# TYPE farm_harness_observer_up gauge",
        "farm_harness_observer_up 1",
        "",
        "# HELP farm_harness_bambuddy_health_up Bambuddy root health endpoint availability.",
        "# TYPE farm_harness_bambuddy_health_up gauge",
        metric_line("farm_harness_bambuddy_health_up", 1 if bambuddy_ok else 0),
        "",
        "# HELP farm_harness_orca_health_up OrcaSlicer API health endpoint availability.",
        "# TYPE farm_harness_orca_health_up gauge",
        metric_line("farm_harness_orca_health_up", 1 if orca_ok else 0),
        "",
        "# HELP farm_harness_orca_health_info OrcaSlicer API version identity when health is available.",
        "# TYPE farm_harness_orca_health_info gauge",
        metric_line("farm_harness_orca_health_info", 1 if orca_ok else 0, {"version": orca_version}),
        "",
        "# HELP farm_harness_orca_last_slice_success Last recorded Orca fixture slice result.",
        "# TYPE farm_harness_orca_last_slice_success gauge",
        metric_line(
            "farm_harness_orca_last_slice_success",
            slice_success,
            {"fixture": "fixture-cube-v1", "status": slice_status},
        ),
        "",
        "# HELP farm_harness_orca_last_slice_artifact_bytes Last recorded Orca fixture slice artifact size.",
        "# TYPE farm_harness_orca_last_slice_artifact_bytes gauge",
        metric_line(
            "farm_harness_orca_last_slice_artifact_bytes",
            artifact_bytes,
            {"fixture": "fixture-cube-v1"},
        ),
        "",
    ]
    return "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    server_version = "FarmHarnessObserver/1.0"

    def _send(self, status: int, body: str, content_type: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(HTTPStatus.OK, json.dumps({"status": "ok"}), "application/json; charset=utf-8")
            return
        if self.path == "/metrics":
            self._send(HTTPStatus.OK, build_metrics(), "text/plain; version=0.0.4; charset=utf-8")
            return
        self._send(HTTPStatus.NOT_FOUND, json.dumps({"error": "not found"}), "application/json; charset=utf-8")

    def log_message(self, fmt: str, *args: object) -> None:
        print(json.dumps({"service": "harness-observer", "message": fmt % args, "path": self.path}), flush=True)


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    server = ReusableThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(json.dumps({"service": "harness-observer", "port": PORT, "status": "starting"}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
