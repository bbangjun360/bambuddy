#!/usr/bin/env python3
from __future__ import annotations

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


_HARNESS_ENV = _read_harness_env()
ORCA_BASE_URL = os.environ.get(
    "ORCA_BASE_URL",
    f"http://127.0.0.1:{_HARNESS_ENV.get('ORCA_API_PORT', '13003')}",
).rstrip("/")


def wait_for_health(timeout: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{ORCA_BASE_URL}/health", timeout=5) as result:
                body = result.read(8192).decode("utf-8", errors="replace")
                if 200 <= result.status < 400:
                    try:
                        payload = json.loads(body)
                    except json.JSONDecodeError:
                        payload = {"raw": body[:500]}
                    return {
                        "healthy": True,
                        "url": f"{ORCA_BASE_URL}/health",
                        "status": result.status,
                        "response": payload,
                    }
                last_error = f"HTTP {result.status}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"Orca sidecar did not become healthy: {last_error}")


def main() -> int:
    print(json.dumps(wait_for_health(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"healthy": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
