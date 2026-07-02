from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy/docker-compose.farm.yml"
ENV_EXAMPLE = ROOT / "deploy/.env.farm.example"
PROMETHEUS_CONFIG = ROOT / "deploy/observability/prometheus/prometheus.yml"
GRAFANA_DATASOURCE = ROOT / "deploy/observability/grafana/provisioning/datasources/prometheus.yml"
GRAFANA_DASHBOARD_PROVIDER = ROOT / "deploy/observability/grafana/provisioning/dashboards/dashboards.yml"
GRAFANA_DASHBOARD = ROOT / "deploy/observability/grafana/dashboards/farm-production.json"
RUNBOOK = ROOT / "docs/runbooks/FARM_PRODUCTION_DEPLOY.md"
EXEC_PLAN = ROOT / "workpacks/exec/WP-109_FARM_PRODUCTION_DEPLOY.md"


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing expected file: {path.relative_to(ROOT)}")
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


def _assert_pinned_image(testcase: unittest.TestCase, image: str) -> None:
    testcase.assertIn(":", image)
    testcase.assertIn("@sha256:", image)
    testcase.assertNotIn(":latest", image)
    testcase.assertNotIn("REPLACE", image)
    testcase.assertRegex(image, r"@sha256:[0-9a-f]{64}$")


class FarmProductionDeployConfigTest(unittest.TestCase):
    def test_farm_compose_adds_only_observability_and_notification_services(self) -> None:
        text = _read(COMPOSE)

        for service in ("prometheus:", "grafana:", "ntfy:"):
            self.assertIn(service, text)
        self.assertNotIn("caddy:", text)
        self.assertNotIn("backup:", text)
        self.assertNotIn("restore:", text)
        self.assertNotIn("network_mode: host", text)
        self.assertNotIn("container_name:", text)

        for image_var in ("PROMETHEUS_IMAGE", "GRAFANA_IMAGE", "NTFY_IMAGE"):
            self.assertIn(f"${{{image_var}:?Set a pinned {image_var}", text)

        for port in (
            "127.0.0.1:${PROMETHEUS_PORT:-19090}:9090",
            "127.0.0.1:${GRAFANA_PORT:-13030}:3000",
            "127.0.0.1:${NTFY_HTTP_PORT:-18080}:80",
        ):
            self.assertIn(port, text)

        self.assertIn('profiles: ["farm-observability"]', text)
        self.assertIn("restart: unless-stopped", text)
        self.assertIn("host.docker.internal:host-gateway", text)
        self.assertIn("NTFY_ENABLE_METRICS: \"true\"", text)
        self.assertIn("NTFY_AUTH_DEFAULT_ACCESS: ${NTFY_AUTH_DEFAULT_ACCESS:-read-write}", text)
        self.assertIn("GF_AUTH_ANONYMOUS_ENABLED: \"false\"", text)
        self.assertIn("GF_USERS_ALLOW_SIGN_UP: \"false\"", text)
        self.assertIn("/v1/health", text)

        for forbidden in (
            "BAMBU_ACCESS_CODE",
            "PRINTER_SERIAL",
            "MQTT_PASSWORD",
            "allow_real_",
            "swapmod_",
            "plate_change",
            "bed_automation",
        ):
            self.assertNotIn(forbidden, text)

    def test_farm_env_example_pins_images_and_uses_local_ports(self) -> None:
        values = _read_env(ENV_EXAMPLE)

        for key in ("PROMETHEUS_IMAGE", "GRAFANA_IMAGE", "NTFY_IMAGE"):
            with self.subTest(key=key):
                _assert_pinned_image(self, values[key])

        self.assertEqual(values["PROMETHEUS_PORT"], "19090")
        self.assertEqual(values["GRAFANA_PORT"], "13030")
        self.assertEqual(values["NTFY_HTTP_PORT"], "18080")
        self.assertEqual(values["GRAFANA_ADMIN_USER"], "admin")
        self.assertNotIn("SECRET", _read(ENV_EXAMPLE).upper())
        self.assertNotIn("TOKEN", _read(ENV_EXAMPLE).upper())

    def test_prometheus_scrapes_bambuddy_and_ntfy_without_committed_credentials(self) -> None:
        text = _read(PROMETHEUS_CONFIG)

        self.assertIn("job_name: prometheus", text)
        self.assertIn("job_name: bambuddy", text)
        self.assertIn("metrics_path: /api/v1/metrics", text)
        self.assertIn("host.docker.internal:8000", text)
        self.assertIn("job_name: ntfy", text)
        self.assertIn("metrics_path: /metrics", text)
        self.assertIn("ntfy:80", text)
        self.assertNotIn("bearer_token", text)
        self.assertNotIn("authorization", text.lower())
        self.assertNotRegex(text, r"(access[_-]?code|serial|password|token)", re.IGNORECASE)

    def test_grafana_provisions_production_dashboard(self) -> None:
        datasource = _read(GRAFANA_DATASOURCE)
        provider = _read(GRAFANA_DASHBOARD_PROVIDER)
        dashboard = json.loads(_read(GRAFANA_DASHBOARD))

        self.assertIn("url: http://prometheus:9090", datasource)
        self.assertIn("uid: farm-production-prometheus", datasource)
        self.assertIn("/var/lib/grafana/dashboards", provider)
        self.assertEqual(dashboard["title"], "Farm Production Observability")

        expressions = {
            target["expr"]
            for panel in dashboard["panels"]
            for target in panel.get("targets", [])
        }
        for expression in (
            'up{job="bambuddy"}',
            'up{job="ntfy"}',
            "bambuddy_build_info",
            "increase(ntfy_messages_published_total[1h])",
        ):
            self.assertIn(expression, expressions)

    def test_runbook_and_exec_plan_record_scope_validation_and_deferred_work(self) -> None:
        runbook = _read(RUNBOOK)
        exec_plan = _read(EXEC_PLAN)

        self.assertIn("docker compose --project-directory .", runbook)
        self.assertIn("-f docker-compose.yml", runbook)
        self.assertIn("-f deploy/docker-compose.farm.yml", runbook)
        self.assertIn("Prometheus", runbook)
        self.assertIn("Grafana", runbook)
        self.assertIn("ntfy", runbook)
        self.assertIn("Caddy TLS is deferred", runbook)
        self.assertIn("Backup and restore drill is deferred", runbook)
        self.assertIn("Rollback", runbook)
        self.assertIn("Bambuddy still starts", runbook)

        for section in (
            "# Purpose",
            "# Current Behavior",
            "# Scope",
            "# Architecture Boundaries",
            "# Milestones",
            "# Progress",
            "# Validation",
            "# Outcomes",
        ):
            self.assertIn(section, exec_plan)


if __name__ == "__main__":
    unittest.main()
