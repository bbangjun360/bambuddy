from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "deploy/docker-compose.farm.yml"
ENV_EXAMPLE = ROOT / "deploy/.env.farm.example"
PROMETHEUS_CONFIG = ROOT / "deploy/observability/prometheus/prometheus.yml"
GRAFANA_DATASOURCE = ROOT / "deploy/observability/grafana/provisioning/datasources/prometheus.yml"
GRAFANA_DASHBOARD_PROVIDER = ROOT / "deploy/observability/grafana/provisioning/dashboards/dashboards.yml"
GRAFANA_DASHBOARD = ROOT / "deploy/observability/grafana/dashboards/farm-production.json"
CADDYFILE = ROOT / "deploy/caddy/Caddyfile"
BACKUP_DRILL = ROOT / "deploy/scripts/farm_backup_drill.py"
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
    def test_farm_compose_adds_farm_services_tls_entry_and_backup_mount(self) -> None:
        text = _read(COMPOSE)

        for service in ("bambuddy:", "prometheus:", "grafana:", "ntfy:", "caddy:"):
            self.assertIn(service, text)
        self.assertNotIn("backup:", text)
        self.assertNotIn("restore:", text)
        self.assertNotIn("network_mode: host", text)
        self.assertNotIn("container_name:", text)

        for image_var in ("PROMETHEUS_IMAGE", "GRAFANA_IMAGE", "NTFY_IMAGE", "CADDY_IMAGE"):
            self.assertIn(f"${{{image_var}:?Set a pinned {image_var}", text)

        for port in (
            "${CADDY_HTTP_PORT:-80}:80",
            "${CADDY_HTTPS_PORT:-443}:443",
            "127.0.0.1:${PROMETHEUS_PORT:-19090}:9090",
            "127.0.0.1:${GRAFANA_PORT:-13030}:3000",
            "127.0.0.1:${NTFY_HTTP_PORT:-18080}:80",
        ):
            self.assertIn(port, text)

        self.assertIn("./deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro", text)
        self.assertIn("${FARM_BACKUP_DIR:?Set FARM_BACKUP_DIR in deploy/.env.farm}:/app/data/backups", text)
        self.assertIn("farm_caddy_data:/data", text)
        self.assertIn("farm_caddy_config:/config", text)
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

        for key in ("PROMETHEUS_IMAGE", "GRAFANA_IMAGE", "NTFY_IMAGE", "CADDY_IMAGE"):
            with self.subTest(key=key):
                self.assertIn(key, values)
                _assert_pinned_image(self, values[key])

        expected_values = {
            "CADDY_HTTP_PORT": "80",
            "CADDY_HTTPS_PORT": "443",
            "PROMETHEUS_PORT": "19090",
            "GRAFANA_PORT": "13030",
            "NTFY_HTTP_PORT": "18080",
            "BAMBUDDY_FARM_HOST": "bambuddy.farm.lan",
            "GRAFANA_FARM_HOST": "grafana.farm.lan",
            "NTFY_FARM_HOST": "ntfy.farm.lan",
            "FARM_BACKUP_DIR": "/srv/bambuddy/backups",
            "GRAFANA_ADMIN_USER": "admin",
        }
        for key, value in expected_values.items():
            with self.subTest(key=key):
                self.assertEqual(values.get(key), value)
        self.assertNotIn("SECRET", _read(ENV_EXAMPLE).upper())
        self.assertNotIn("TOKEN", _read(ENV_EXAMPLE).upper())

    def test_caddyfile_proxies_only_operator_surfaces_with_internal_tls(self) -> None:
        text = _read(CADDYFILE)

        self.assertIn("{$BAMBUDDY_FARM_HOST:bambuddy.farm.lan}", text)
        self.assertIn("{$GRAFANA_FARM_HOST:grafana.farm.lan}", text)
        self.assertIn("{$NTFY_FARM_HOST:ntfy.farm.lan}", text)
        self.assertEqual(text.count("tls internal"), 3)
        self.assertIn("reverse_proxy host.docker.internal:8000", text)
        self.assertIn("reverse_proxy grafana:3000", text)
        self.assertIn("reverse_proxy ntfy:80", text)
        self.assertIn("Strict-Transport-Security", text)
        self.assertNotIn("prometheus.farm.lan", text)
        self.assertNotRegex(text, r"(access[_-]?code|serial|password|token)", re.IGNORECASE)

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
        self.assertIn("Caddy local TLS", runbook)
        self.assertIn("Backup and restore drill", runbook)
        self.assertIn("CONFIRM_FARM_PRODUCTION_RESTORE", runbook)
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


class FarmBackupDrillScriptTest(unittest.TestCase):
    def _load_script(self):
        if not BACKUP_DRILL.exists():
            raise AssertionError(f"missing expected file: {BACKUP_DRILL.relative_to(ROOT)}")
        spec = importlib.util.spec_from_file_location("farm_backup_drill", BACKUP_DRILL)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_backup_drill_script_builds_safe_dry_run_by_default(self) -> None:
        module = self._load_script()
        text = _read(BACKUP_DRILL)

        self.assertIn("DRY RUN", text)
        self.assertIn("create_backup_zip", text)
        self.assertNotIn("dropdb", text)
        self.assertNotIn("docker volume rm", text)
        self.assertNotIn("down -v", text)
        self.assertEqual(module.RESTORE_CONFIRMATION, "CONFIRM_FARM_PRODUCTION_RESTORE")

    def test_restore_drill_rejects_unconfirmed_or_unsafe_backup_paths(self) -> None:
        module = self._load_script()

        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            backup_dir.mkdir()
            safe_backup = backup_dir / "bambuddy-backup-20260702-120000.zip"
            safe_backup.write_bytes(b"zip-fixture")

            with self.assertRaises(ValueError):
                module.validate_restore_request(
                    safe_backup,
                    backup_dir=backup_dir,
                    confirmation="wrong",
                )

            with self.assertRaises(ValueError):
                module.validate_restore_request(
                    Path(tmpdir) / "other.zip",
                    backup_dir=backup_dir,
                    confirmation=module.RESTORE_CONFIRMATION,
                )

            resolved = module.validate_restore_request(
                safe_backup,
                backup_dir=backup_dir,
                confirmation=module.RESTORE_CONFIRMATION,
            )

        self.assertEqual(resolved, safe_backup.resolve())


if __name__ == "__main__":
    unittest.main()
