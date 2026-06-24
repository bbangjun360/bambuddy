#!/usr/bin/env python3
from __future__ import annotations

import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS_ENV_FILE = ROOT / ".env.harness"


def _read_harness_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not HARNESS_ENV_FILE.exists():
        return values
    for line in HARNESS_ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def _base_url_from_env(
    values: dict[str, str],
    *,
    override_key: str,
    health_url_key: str,
    port_key: str,
    default_port: str,
) -> str:
    override = os.environ.get(override_key)
    if override:
        return override.rstrip("/")

    health_url = values.get(health_url_key, "").rstrip("/")
    if health_url.endswith("/health"):
        return health_url.removesuffix("/health")
    if health_url:
        return health_url

    return f"http://127.0.0.1:{values.get(port_key, default_port)}"


_HARNESS_ENV = _read_harness_env()
BAMBUDDY_BASE_URL = _base_url_from_env(
    _HARNESS_ENV,
    override_key="BAMBUDDY_BASE_URL",
    health_url_key="BAMBUDDY_HEALTH_URL",
    port_key="BAMBUDDY_PORT",
    default_port="18000",
)
MOCK_BASE_URL = _base_url_from_env(
    _HARNESS_ENV,
    override_key="MOCK_BASE_URL",
    health_url_key="MOCK_HEALTH_URL",
    port_key="MOCK_PORT",
    default_port="19099",
)

TRANSIENT_READINESS_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionResetError,
    ConnectionAbortedError,
    http.client.RemoteDisconnected,
)

TARGETS = {
    "bambuddy-root": f"{BAMBUDDY_BASE_URL}/",
    "bambuddy-health": f"{BAMBUDDY_BASE_URL}/health",
    "bambuddy-docs": f"{BAMBUDDY_BASE_URL}/docs",
    "mock-services": f"{MOCK_BASE_URL}/health",
}


def wait_for(name: str, url: str, timeout: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as result:
                body = result.read(4096).decode("utf-8", errors="replace")
                if 200 <= result.status < 400:
                    return {"name": name, "url": url, "status": result.status, "body": body[:200]}
                last_error = f"HTTP {result.status}"
        except TRANSIENT_READINESS_ERRORS as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"{name} did not become healthy: {last_error}")


def main() -> int:
    results = []
    for name, url in TARGETS.items():
        results.append(wait_for(name, url))
    print(json.dumps({"healthy": True, "targets": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"healthy": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
