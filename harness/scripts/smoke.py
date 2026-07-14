#!/usr/bin/env python3
from __future__ import annotations

import http.client
import ipaddress
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]


def _resolve_harness_env_file() -> Path:
    selected = Path(os.environ.get("HARNESS_ENV", ".env.harness"))
    return selected if selected.is_absolute() else ROOT / selected


HARNESS_ENV_FILE = _resolve_harness_env_file()
LOCAL_HOSTNAMES = {"localhost"}


class HarnessNotRunningError(RuntimeError):
    """Raised when local smoke targets are not listening at all."""


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


def _loopback_address(url: str) -> tuple[str, int] | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    hostname = parsed.hostname
    is_loopback = hostname in LOCAL_HOSTNAMES
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_loopback = False
    if not is_loopback:
        return None
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return hostname, port


def preflight_harness_targets(
    targets: Mapping[str, str] | None = None,
    *,
    connector: Callable[[tuple[str, int], float], object] = socket.create_connection,
    timeout: float = 1.0,
) -> None:
    selected_targets = TARGETS if targets is None else targets
    failures: list[str] = []
    for name, url in selected_targets.items():
        address = _loopback_address(url)
        if address is None:
            continue
        connection = None
        try:
            connection = connector(address, timeout)
        except OSError as exc:
            failures.append(f"{name} at {url} is not listening: {exc}")
        finally:
            close = getattr(connection, "close", None)
            if callable(close):
                close()
    if failures:
        details = "; ".join(failures)
        raise HarnessNotRunningError(
            "Harness is not reachable before smoke readiness checks: "
            f"{details}. Start it with `make harness-up` or set "
            "BAMBUDDY_BASE_URL/MOCK_BASE_URL to a running harness."
        )


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
    preflight_harness_targets(TARGETS)
    results = []
    for name, url in TARGETS.items():
        results.append(wait_for(name, url))
    print(json.dumps({"healthy": True, "targets": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HarnessNotRunningError as exc:
        print(
            json.dumps(
                {"healthy": False, "reason": "harness_not_running", "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)
    except Exception as exc:
        print(json.dumps({"healthy": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
