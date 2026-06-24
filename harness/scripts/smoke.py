#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

TARGETS = {
    "bambuddy": os.environ.get("BAMBUDDY_HEALTH_URL", "http://127.0.0.1:18000/"),
    "mock-services": os.environ.get("MOCK_HEALTH_URL", "http://127.0.0.1:19099/health"),
}


def wait_for(name: str, url: str, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as result:
                body = result.read(4096).decode("utf-8", errors="replace")
                if 200 <= result.status < 400:
                    return {"name": name, "url": url, "status": result.status, "body": body[:200]}
                last_error = f"HTTP {result.status}"
        except (urllib.error.URLError, TimeoutError) as exc:
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
