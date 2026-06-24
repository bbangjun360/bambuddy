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
HARNESS_ENV_FILE = ROOT / ".env.harness"


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


def _base_url_from_env(
    values: Mapping[str, str],
    environ: Mapping[str, str],
    *,
    override_key: str,
    health_url_key: str,
    port_key: str,
    default_port: str,
) -> str:
    override = environ.get(override_key)
    if override:
        return override.rstrip("/")

    health_url = values.get(health_url_key, "").rstrip("/")
    if health_url.endswith("/health"):
        return health_url.removesuffix("/health")
    if health_url:
        return health_url

    return f"http://127.0.0.1:{values.get(port_key, default_port)}"


def resolve_base_urls(
    *,
    env_file: Path = HARNESS_ENV_FILE,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = os.environ if environ is None else environ
    values = _read_harness_env(env_file)
    return {
        "bambuddy_base_url": _base_url_from_env(
            values,
            env,
            override_key="BAMBUDDY_BASE_URL",
            health_url_key="BAMBUDDY_HEALTH_URL",
            port_key="BAMBUDDY_PORT",
            default_port="18000",
        ),
        "mock_base_url": _base_url_from_env(
            values,
            env,
            override_key="MOCK_BASE_URL",
            health_url_key="MOCK_HEALTH_URL",
            port_key="MOCK_PORT",
            default_port="19099",
        ),
    }


def resolve_targets(
    *,
    env_file: Path = HARNESS_ENV_FILE,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    base_urls = resolve_base_urls(env_file=env_file, environ=environ)
    bambuddy_base_url = base_urls["bambuddy_base_url"]
    mock_base_url = base_urls["mock_base_url"]
    return {
        "bambuddy-root": f"{bambuddy_base_url}/",
        "bambuddy-health": f"{bambuddy_base_url}/health",
        "bambuddy-docs": f"{bambuddy_base_url}/docs",
        "mock-services": f"{mock_base_url}/health",
    }


_BASE_URLS = resolve_base_urls()
BAMBUDDY_BASE_URL = _BASE_URLS["bambuddy_base_url"]
MOCK_BASE_URL = _BASE_URLS["mock_base_url"]

TRANSIENT_READINESS_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionResetError,
    ConnectionAbortedError,
    http.client.RemoteDisconnected,
)

TARGETS = resolve_targets()


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
