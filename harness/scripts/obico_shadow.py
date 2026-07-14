#!/usr/bin/env python3
from __future__ import annotations

import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _resolve_harness_env_file() -> Path:
    selected = Path(os.environ.get("HARNESS_ENV", ".env.harness"))
    return selected if selected.is_absolute() else ROOT / selected


HARNESS_ENV_FILE = _resolve_harness_env_file()
SYNTHETIC_SECRET = "wp070-shadow-secret-not-for-output"


def _read_harness_env(env_file: Path = HARNESS_ENV_FILE) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_file.exists():
        return values
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def _base_url(values: Mapping[str, str], env: Mapping[str, str], override_key: str, port_key: str, default_port: str) -> str:
    override = env.get(override_key) or values.get(override_key, "")
    if override:
        return override.rstrip("/")
    return f"http://127.0.0.1:{env.get(port_key) or values.get(port_key, default_port)}"


def endpoints() -> dict[str, str]:
    values = _read_harness_env()
    env = os.environ
    return {
        "bambuddy": _base_url(values, env, "BAMBUDDY_BASE_URL", "BAMBUDDY_PORT", "18000"),
        "mock": _base_url(values, env, "MOCK_BASE_URL", "MOCK_PORT", "19099"),
    }


def request_json(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as result:
        return json.loads(result.read().decode("utf-8"))


TRANSIENT_READINESS_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionResetError,
    ConnectionAbortedError,
    http.client.RemoteDisconnected,
)


def wait_for_json(url: str, timeout: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            return request_json(url)
        except TRANSIENT_READINESS_ERRORS as exc:
            last_error = str(exc)
            time.sleep(1)
    raise RuntimeError(f"{url} did not become ready: {last_error}")


def request_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=10) as result:
        return result.read().decode("utf-8")


def fetch_event(mock_base: str, scenario: str) -> dict:
    return request_json(f"{mock_base}/obico-shadow/v1/events/{scenario}")


def post_event(bambuddy_base: str, payload: dict) -> dict:
    return request_json(f"{bambuddy_base}/api/v1/obico-shadow/events", method="POST", payload=payload)


def main() -> int:
    urls = endpoints()
    bambuddy = urls["bambuddy"]
    mock = urls["mock"]

    health = wait_for_json(f"{bambuddy}/health")
    healthy = post_event(bambuddy, fetch_event(mock, "healthy"))
    suspected = post_event(bambuddy, fetch_event(mock, "spaghetti"))
    duplicate = post_event(bambuddy, fetch_event(mock, "spaghetti"))
    invalid = post_event(bambuddy, fetch_event(mock, "invalid"))
    timeout = post_event(bambuddy, fetch_event(mock, "timeout"))

    secret_probe = fetch_event(mock, "detachment")
    secret_probe["event_id"] = "shadow-secret-probe-0001"
    secret_probe["metadata"] = {"access_token": SYNTHETIC_SECRET}
    secret_result = post_event(bambuddy, secret_probe)

    status = request_json(f"{bambuddy}/api/v1/obico-shadow/status")
    metrics = request_text(f"{bambuddy}/api/v1/obico-shadow/metrics")
    exposed = json.dumps(status, sort_keys=True) + "\n" + metrics
    if SYNTHETIC_SECRET in exposed:
        raise RuntimeError("synthetic secret leaked through shadow status or metrics")
    if suspected["status"] not in {"REVIEW_RECOMMENDED", "IGNORED_DUPLICATE"}:
        raise RuntimeError(f"suspected event was not review-only: {suspected}")
    if duplicate["status"] != "IGNORED_DUPLICATE":
        raise RuntimeError(f"duplicate event was not idempotent: {duplicate}")
    if invalid["status"] != "INVALID":
        raise RuntimeError(f"invalid event was not classified safely: {invalid}")
    if timeout["status"] != "RETRYABLE_FAILURE":
        raise RuntimeError(f"timeout event was not retryable: {timeout}")
    if secret_result["status"] not in {"REVIEW_RECOMMENDED", "IGNORED_DUPLICATE"}:
        raise RuntimeError(f"secret probe did not remain shadow-only: {secret_result}")

    print(
        json.dumps(
            {
                "healthy": True,
                "bambuddy_health": health,
                "events": {
                    "healthy": healthy["status"],
                    "suspected": suspected["status"],
                    "duplicate": duplicate["status"],
                    "invalid": invalid["status"],
                    "timeout": timeout["status"],
                    "secret_probe": secret_result["status"],
                },
                "stored_observations": status["stored_observations"],
                "metrics_contains_shadow_counter": "bambuddy_obico_shadow_events_total" in metrics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (urllib.error.HTTPError, Exception) as exc:
        print(json.dumps({"healthy": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
