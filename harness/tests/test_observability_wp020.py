from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "harness/docker-compose.observability.yml"
PROMETHEUS_CONFIG = ROOT / "harness/observability/prometheus/prometheus.yml"
GRAFANA_DATASOURCE = ROOT / "harness/observability/grafana/provisioning/datasources/prometheus.yml"
GRAFANA_DASHBOARD_PROVIDER = ROOT / "harness/observability/grafana/provisioning/dashboards/dashboards.yml"
GRAFANA_DASHBOARD = ROOT / "harness/observability/grafana/dashboards/farm-observability.json"
MAKEFILE = ROOT / "Makefile"
EXAMPLE_ENV_FILE = ROOT / ".env.harness.example"
EXPORTER = ROOT / "harness/scripts/observability_exporter.py"
HEALTH_SCRIPT = ROOT / "harness/scripts/observability_health.py"
PORT = 19220
BASE = f"http://127.0.0.1:{PORT}"
SYNTHETIC_SECRET = "wp020-access-code-00000000"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in _read(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def _target_body(text: str, target: str) -> str:
    import re

    match = re.search(rf"^{target}(?:[: ].*)?\n(?P<body>(?:\t.*\n)+)", text, re.MULTILINE)
    assert match is not None, f"missing Makefile target {target}"
    return match.group("body")


def _json_request(path: str, *, method: str = "GET", payload: dict | None = None, headers: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE + quote(path, safe="/?=&"),
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urllib.request.urlopen(request, timeout=3) as result:
        return result.status, json.loads(result.read().decode("utf-8"))


def _text_request(path: str) -> str:
    with urllib.request.urlopen(BASE + quote(path, safe="/?=&"), timeout=3) as result:
        return result.read().decode("utf-8")


class ObservabilityConfigTest(unittest.TestCase):
    def test_compose_override_adds_read_only_observability_services(self) -> None:
        text = _read(COMPOSE)

        for service in ("harness-observer:", "prometheus:", "grafana:"):
            self.assertIn(service, text)
        self.assertIn('profiles: ["observability"]', text)
        self.assertIn("127.0.0.1:${PROMETHEUS_PORT:-19090}:9090", text)
        self.assertIn("127.0.0.1:${GRAFANA_PORT:-13030}:3000", text)
        self.assertIn("127.0.0.1:${HARNESS_OBSERVER_PORT:-19101}:9101", text)
        self.assertNotIn("container_name:", text)
        for forbidden in ("BAMBU_ACCESS_CODE", "PRINTER_SERIAL", "MQTT_PASSWORD", "network_mode: host"):
            self.assertNotIn(forbidden, text)

    def test_prometheus_scrapes_existing_bambuddy_and_harness_metrics(self) -> None:
        text = _read(PROMETHEUS_CONFIG)

        self.assertIn("job_name: bambuddy", text)
        self.assertIn("metrics_path: /api/v1/metrics", text)
        self.assertIn("bambuddy:8000", text)
        self.assertIn("job_name: mock-services", text)
        self.assertIn("mock-services:9099", text)
        self.assertIn("job_name: harness-observer", text)
        self.assertIn("harness-observer:9101", text)
        self.assertIn("prometheus_enabled", text)
        self.assertNotIn("bearer_token: ", text)

    def test_grafana_provisioning_includes_wp020_dashboard(self) -> None:
        datasource = _read(GRAFANA_DATASOURCE)
        provider = _read(GRAFANA_DASHBOARD_PROVIDER)
        dashboard_text = _read(GRAFANA_DASHBOARD)

        self.assertIn("url: http://prometheus:9090", datasource)
        self.assertIn("uid: farm-prometheus", datasource)
        self.assertIn("/var/lib/grafana/dashboards", provider)

        dashboard = json.loads(dashboard_text)
        self.assertEqual(dashboard["title"], "Farm Harness Observability")
        expressions = {
            target["expr"]
            for panel in dashboard["panels"]
            for target in panel.get("targets", [])
        }
        for expression in (
            'up{job="bambuddy"}',
            "bambuddy_build_info",
            "farm_harness_mock_failures_total",
            "farm_harness_orca_last_slice_success",
        ):
            self.assertIn(expression, expressions)

    def test_harness_example_documents_default_observability_ports_and_images(self) -> None:
        values = _read_env(EXAMPLE_ENV_FILE)

        self.assertIn("PROMETHEUS_IMAGE", values)
        self.assertIn("GRAFANA_IMAGE", values)
        self.assertEqual(values["PROMETHEUS_PORT"], "19090")
        self.assertEqual(values["GRAFANA_PORT"], "13030")
        self.assertEqual(values["HARNESS_OBSERVER_PORT"], "19101")

    def test_makefile_exposes_clear_wp020_targets(self) -> None:
        text = _read(MAKEFILE)

        self.assertIn("--profile observability", _target_body(text, "harness-up-observability"))
        self.assertIn("observability_health.py", _target_body(text, "harness-observability-health"))
        self.assertIn("test_observability_*.py", _target_body(text, "test-observability"))

    def test_makefile_observability_health_can_use_defaults_without_harness_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_env = Path(tmpdir) / "missing.env"
            result = subprocess.run(
                ["make", "-n", f"HARNESS_ENV={missing_env}", "harness-observability-health"],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("python3 harness/scripts/observability_health.py", result.stdout)


class ObservabilityHealthEnvResolutionTest(unittest.TestCase):
    def _load_health(self):
        spec = importlib.util.spec_from_file_location("observability_health", HEALTH_SCRIPT)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _write_env(self, tmpdir: str, body: str) -> Path:
        env_file = Path(tmpdir) / ".env.harness"
        env_file.write_text(body, encoding="utf-8")
        return env_file

    def test_health_loads_custom_observability_ports_from_harness_env(self) -> None:
        module = self._load_health()
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = self._write_env(
                tmpdir,
                "\n".join(
                    [
                        "BAMBUDDY_PORT=18131",
                        "MOCK_PORT=19131",
                        "ORCA_API_PORT=13131",
                        "PROMETHEUS_PORT=19091",
                        "GRAFANA_PORT=13031",
                        "HARNESS_OBSERVER_PORT=19132",
                    ]
                ),
            )

            endpoints = module.resolve_endpoints(env_file=env_file, environ={})

        self.assertEqual(endpoints["bambuddy_base_url"], "http://127.0.0.1:18131")
        self.assertEqual(endpoints["mock_base_url"], "http://127.0.0.1:19131")
        self.assertEqual(endpoints["prometheus_base_url"], "http://127.0.0.1:19091")
        self.assertEqual(endpoints["grafana_base_url"], "http://127.0.0.1:13031")
        self.assertEqual(endpoints["observer_base_url"], "http://127.0.0.1:19132")

    def test_health_explicit_endpoint_env_vars_override_harness_env(self) -> None:
        module = self._load_health()
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = self._write_env(
                tmpdir,
                "\n".join(
                    [
                        "BAMBUDDY_PORT=18131",
                        "MOCK_PORT=19131",
                        "PROMETHEUS_PORT=19091",
                        "GRAFANA_PORT=13031",
                        "HARNESS_OBSERVER_PORT=19132",
                    ]
                ),
            )

            with mock.patch.dict(
                os.environ,
                {
                    "BAMBUDDY_BASE_URL": "http://127.0.0.1:28131/",
                    "MOCK_BASE_URL": "http://127.0.0.1:29131/",
                    "PROMETHEUS_BASE_URL": "http://127.0.0.1:29091/",
                    "GRAFANA_BASE_URL": "http://127.0.0.1:23031/",
                    "OBSERVER_BASE_URL": "http://127.0.0.1:29132/",
                },
                clear=True,
            ):
                endpoints = module.resolve_endpoints(env_file=env_file)

        self.assertEqual(endpoints["bambuddy_base_url"], "http://127.0.0.1:28131")
        self.assertEqual(endpoints["mock_base_url"], "http://127.0.0.1:29131")
        self.assertEqual(endpoints["prometheus_base_url"], "http://127.0.0.1:29091")
        self.assertEqual(endpoints["grafana_base_url"], "http://127.0.0.1:23031")
        self.assertEqual(endpoints["observer_base_url"], "http://127.0.0.1:29132")

    def test_health_defaults_remain_available_without_harness_env_file(self) -> None:
        module = self._load_health()
        with tempfile.TemporaryDirectory() as tmpdir:
            endpoints = module.resolve_endpoints(env_file=Path(tmpdir) / "missing.env", environ={})

        self.assertEqual(endpoints["bambuddy_base_url"], "http://127.0.0.1:18000")
        self.assertEqual(endpoints["mock_base_url"], "http://127.0.0.1:19099")
        self.assertEqual(endpoints["prometheus_base_url"], "http://127.0.0.1:19090")
        self.assertEqual(endpoints["grafana_base_url"], "http://127.0.0.1:13030")
        self.assertEqual(endpoints["observer_base_url"], "http://127.0.0.1:19101")

    def test_health_does_not_hardcode_default_observability_ports_when_custom_ports_exist(self) -> None:
        module = self._load_health()
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = self._write_env(
                tmpdir,
                "\n".join(
                    [
                        "PROMETHEUS_PORT=19091",
                        "GRAFANA_PORT=13031",
                        "HARNESS_OBSERVER_PORT=19132",
                    ]
                ),
            )
            endpoints = module.resolve_endpoints(env_file=env_file, environ={})
            probe_urls = module.probe_urls(endpoints)

        rendered = json.dumps({"endpoints": endpoints, "probe_urls": probe_urls}, sort_keys=True)
        self.assertEqual(probe_urls["prometheus-ready"], "http://127.0.0.1:19091/-/ready")
        self.assertEqual(probe_urls["grafana-health"], "http://127.0.0.1:13031/api/health")
        self.assertEqual(probe_urls["observer-metrics"], "http://127.0.0.1:19132/metrics")
        self.assertNotIn("http://127.0.0.1:19090", rendered)
        self.assertNotIn("http://127.0.0.1:13030", rendered)
        self.assertNotIn("http://127.0.0.1:19101", rendered)

    def test_request_failure_message_names_probed_endpoint(self) -> None:
        module = self._load_health()
        target = "http://127.0.0.1:19091/-/ready"

        with mock.patch.object(module.urllib.request, "urlopen", side_effect=module.urllib.error.URLError("boom")):
            with self.assertRaises(RuntimeError) as raised:
                module.request(target)

        self.assertIn(target, str(raised.exception))


class LiveMockService:
    def __init__(self) -> None:
        self.proc: subprocess.Popen[str] | None = None
        self.output = ""

    def __enter__(self):
        env = os.environ.copy()
        env["MOCK_PORT"] = str(PORT)
        self.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "harness/mock_services.py")],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                status, _ = _json_request("/health")
                if status == 200:
                    _json_request("/admin/reset", method="POST", payload={})
                    return self
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("mock service failed to start")

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self.proc is not None
        self.proc.terminate()
        try:
            self.output = self.proc.communicate(timeout=5)[0]
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.output = self.proc.communicate(timeout=5)[0]


class MockServiceObservabilityTest(unittest.TestCase):
    def test_forced_http_failure_is_visible_in_metrics_without_secret_leak(self) -> None:
        server = LiveMockService()
        with server:
            _json_request("/admin/scenario", method="POST", payload={"scenario": "http_500"})

            with self.assertRaises(urllib.error.HTTPError) as raised:
                request = urllib.request.Request(
                    BASE + "/erp/api/resource/Work%20Order",
                    headers={"X-Synthetic-Secret": SYNTHETIC_SECRET},
                )
                urllib.request.urlopen(request, timeout=3)
            self.assertEqual(raised.exception.code, 500)

            metrics = _text_request("/metrics")
            self.assertIn('farm_harness_mock_failures_total{scenario="http_500"} 1', metrics)
            self.assertIn('farm_harness_mock_scenario_info{scenario="http_500"} 1', metrics)
            self.assertNotIn(SYNTHETIC_SECRET, metrics)

        self.assertNotIn(SYNTHETIC_SECRET, server.output)

    def test_unknown_scenario_is_rejected_so_secrets_cannot_become_metric_labels(self) -> None:
        server = LiveMockService()
        with server:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                _json_request("/admin/scenario", method="POST", payload={"scenario": SYNTHETIC_SECRET})

            self.assertEqual(raised.exception.code, 400)
            metrics = _text_request("/metrics")
            self.assertNotIn(SYNTHETIC_SECRET, metrics)

        self.assertNotIn(SYNTHETIC_SECRET, server.output)


class ObserverExporterTest(unittest.TestCase):
    def _load_exporter(self):
        spec = importlib.util.spec_from_file_location("observability_exporter", EXPORTER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_exporter_reports_bambuddy_health_and_orca_slice_evidence(self) -> None:
        module = self._load_exporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            evidence = Path(tmpdir) / "fixture-cube-v1.evidence.json"
            evidence.write_text(
                json.dumps(
                    {
                        "healthy": True,
                        "artifact_size": 12345,
                        "hashes": {"output_sha256": "a" * 64},
                        "secret": SYNTHETIC_SECRET,
                    }
                ),
                encoding="utf-8",
            )

            def probe(url: str) -> tuple[bool, dict]:
                if url.endswith("/health"):
                    return True, {"status": "healthy"}
                return False, {}

            metrics = module.build_metrics(
                bambuddy_base_url="http://bambuddy:8000",
                orca_base_url="http://orca-slicer-api:3000",
                evidence_path=evidence,
                probe_json=probe,
            )

        self.assertIn("farm_harness_bambuddy_health_up 1", metrics)
        self.assertIn("farm_harness_orca_health_up 1", metrics)
        self.assertIn('farm_harness_orca_last_slice_success{fixture="fixture-cube-v1",status="success"} 1', metrics)
        self.assertIn('farm_harness_orca_last_slice_artifact_bytes{fixture="fixture-cube-v1"} 12345', metrics)
        self.assertNotIn(SYNTHETIC_SECRET, metrics)


if __name__ == "__main__":
    unittest.main()
