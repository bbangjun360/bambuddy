#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BAMBUDDY_BASE_URL = os.environ.get("BAMBUDDY_BASE_URL", "http://127.0.0.1:18000").rstrip("/")
MOCK_BASE_URL = os.environ.get("MOCK_BASE_URL", "http://127.0.0.1:19099").rstrip("/")
PROMETHEUS_BASE_URL = os.environ.get("PROMETHEUS_BASE_URL", "http://127.0.0.1:19090").rstrip("/")
OBSERVER_BASE_URL = os.environ.get("OBSERVER_BASE_URL", "http://127.0.0.1:19101").rstrip("/")
SYNTHETIC_SECRET = "wp020-access-code-00000000"


def request(url: str, *, method: str = "GET", payload: dict | None = None, headers: dict | None = None) -> tuple[int, str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=10) as result:
        return result.status, result.read().decode("utf-8", errors="replace")


def request_json(url: str, *, method: str = "GET", payload: dict | None = None) -> dict:
    status, body = request(url, method=method, payload=payload)
    if not (200 <= status < 400):
        raise RuntimeError(f"{url} returned HTTP {status}: {body[:200]}")
    return json.loads(body)


def request_text(url: str) -> str:
    status, body = request(url)
    if not (200 <= status < 400):
        raise RuntimeError(f"{url} returned HTTP {status}: {body[:200]}")
    return body


def wait_for_json(url: str, timeout: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            return request_json(url)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(1)
    raise RuntimeError(f"{url} did not become ready: {last_error}")


def prometheus_query(query: str) -> list:
    encoded = urllib.parse.urlencode({"query": query})
    payload = request_json(f"{PROMETHEUS_BASE_URL}/api/v1/query?{encoded}")
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload.get("data", {}).get("result", [])


def wait_for_prometheus_value(query: str, *, minimum: float = 1.0, timeout: float = 60.0) -> list:
    deadline = time.monotonic() + timeout
    last_result: list = []
    while time.monotonic() < deadline:
        try:
            result = prometheus_query(query)
            last_result = result
            for sample in result:
                value = float(sample.get("value", [0, "0"])[1])
                if value >= minimum:
                    return result
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError(f"Prometheus query did not reach {minimum}: {query}; last_result={last_result}")


def enable_bambuddy_metrics() -> str:
    request_json(
        f"{BAMBUDDY_BASE_URL}/api/v1/settings/",
        method="PUT",
        payload={"prometheus_enabled": True, "prometheus_token": ""},
    )
    metrics = request_text(f"{BAMBUDDY_BASE_URL}/api/v1/metrics")
    if "bambuddy_build_info" not in metrics:
        raise RuntimeError("Bambuddy metrics did not include bambuddy_build_info")
    return metrics


def force_mock_failure() -> dict:
    request_json(f"{MOCK_BASE_URL}/admin/reset", method="POST", payload={})
    request_json(f"{MOCK_BASE_URL}/admin/scenario", method="POST", payload={"scenario": "http_500"})
    try:
        request(
            f"{MOCK_BASE_URL}/erp/api/resource/Work%20Order",
            headers={"X-Synthetic-Secret": SYNTHETIC_SECRET},
        )
    except urllib.error.HTTPError as exc:
        if exc.code != 500:
            raise RuntimeError(f"expected HTTP 500 from mock failure, got {exc.code}") from exc
    else:
        raise RuntimeError("forced mock failure unexpectedly succeeded")

    mock_metrics = request_text(f"{MOCK_BASE_URL}/metrics")
    expected = 'farm_harness_mock_failures_total{scenario="http_500"} 1'
    if expected not in mock_metrics:
        raise RuntimeError("mock failure metric did not increment")
    if SYNTHETIC_SECRET in mock_metrics:
        raise RuntimeError("synthetic secret leaked into mock metrics")

    prom_result = wait_for_prometheus_value('farm_harness_mock_failures_total{scenario="http_500"}', minimum=1)
    request_json(f"{MOCK_BASE_URL}/admin/reset", method="POST", payload={})
    return {"direct_metric": expected, "prometheus_samples": prom_result}


def main() -> int:
    health = wait_for_json(f"{BAMBUDDY_BASE_URL}/health")
    system_info = request_json(f"{BAMBUDDY_BASE_URL}/api/v1/system/info")
    bambuddy_metrics = enable_bambuddy_metrics()

    request_text(f"{PROMETHEUS_BASE_URL}/-/ready")
    observer_metrics = request_text(f"{OBSERVER_BASE_URL}/metrics")
    if SYNTHETIC_SECRET in observer_metrics:
        raise RuntimeError("synthetic secret leaked into observer metrics")

    bambuddy_up = wait_for_prometheus_value('up{job="bambuddy"}', minimum=1)
    build_info = wait_for_prometheus_value("bambuddy_build_info", minimum=1)
    observer_up = wait_for_prometheus_value("farm_harness_observer_up", minimum=1)
    mock_failure = force_mock_failure()

    result = {
        "healthy": True,
        "bambuddy_health": health,
        "bambuddy_version": system_info.get("app", {}).get("version"),
        "bambuddy_metrics_contains_build_info": "bambuddy_build_info" in bambuddy_metrics,
        "prometheus_url": PROMETHEUS_BASE_URL,
        "grafana_url": os.environ.get("GRAFANA_BASE_URL", "http://127.0.0.1:13030"),
        "observer_url": OBSERVER_BASE_URL,
        "prometheus_samples": {
            "bambuddy_up": bambuddy_up,
            "build_info": build_info,
            "observer_up": observer_up,
            "mock_failure": mock_failure,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"healthy": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
