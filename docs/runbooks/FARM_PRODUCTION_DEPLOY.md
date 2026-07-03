# Farm Production Deploy

This runbook starts the production farm-layer services around the existing
Bambuddy Docker compose deployment: Prometheus, Grafana, ntfy, and Caddy local
TLS. It does not enable printer automation or change Bambuddy feature flags.

## Scope

Included:

- Prometheus running from `deploy/docker-compose.farm.yml`.
- Grafana with a provisioned Prometheus datasource and baseline dashboard.
- ntfy running locally with health and Prometheus metrics enabled.
- Caddy local TLS for `bambuddy.farm.lan`, `grafana.farm.lan`, and
  `ntfy.farm.lan` using Caddy's internal CA.
- A host backup mount at `/app/data/backups` plus a guarded backup and restore
  drill helper.

Not included:

- Public ACME certificates or internet-facing exposure.
- ERPNext production deployment.
- Physical printer automation or safety-gate changes.

## Prepare

Copy the example environment and edit the Grafana admin password before first
start:

```bash
cp deploy/.env.farm.example deploy/.env.farm
```

Keep the image values pinned as `version@sha256:digest`. Do not replace them
with `latest`.

Create the host backup directory named by `FARM_BACKUP_DIR` and make it writable
by the Bambuddy container user. The default is:

```bash
sudo install -d -m 0750 -o 1000 -g 1000 /srv/bambuddy/backups
```

Map `bambuddy.farm.lan`, `grafana.farm.lan`, and `ntfy.farm.lan` in local DNS
or operator workstation hosts files. Install Caddy's internal root CA on
operator workstations before treating browser TLS warnings as resolved.

## Start

Run from the repository root:

```bash
docker compose --project-directory .   --env-file deploy/.env.farm   -f docker-compose.yml   -f deploy/docker-compose.farm.yml   --profile farm-observability   up -d bambuddy prometheus grafana ntfy caddy
```

Caddy exposes the operator surfaces over local TLS:

- Bambuddy: `https://bambuddy.farm.lan`
- Grafana: `https://grafana.farm.lan`
- ntfy: `https://ntfy.farm.lan`

Prometheus remains loopback-only at `http://127.0.0.1:19090` and is not exposed
through Caddy. Grafana and ntfy keep their loopback debug ports for local admin
use until the operator closes them in a later hardening pass.

Prometheus scrapes Bambuddy at `host.docker.internal:8000`. If the Bambuddy
HTTP port is changed from the upstream default, update
`deploy/observability/prometheus/prometheus.yml` in the same deployment change.

## Bambuddy Settings

Enable Bambuddy's existing Prometheus metrics setting in the application before
expecting `up{job="bambuddy"}` to become healthy. No access code, printer serial,
MQTT password, ERP credential, or customer data belongs in this deploy file.

Configure Bambuddy's existing ntfy notification provider to use:

```text
server: https://ntfy.farm.lan
topic: bambuddy-farm
```

If the operator changes `NTFY_AUTH_DEFAULT_ACCESS` to `deny-all`, create a local
ntfy user credential out of band and store it outside git before updating
Bambuddy's notification provider.

## Validate

Check service health:

```bash
docker compose --project-directory .   --env-file deploy/.env.farm   -f docker-compose.yml   -f deploy/docker-compose.farm.yml   ps
```

Check Prometheus targets:

```bash
curl -fsS http://127.0.0.1:19090/-/ready
curl -fsS 'http://127.0.0.1:19090/api/v1/query?query=up%7Bjob%3D%22ntfy%22%7D'
```

Check Caddy routes from an operator machine that trusts the Caddy internal CA:

```bash
curl -fsS https://bambuddy.farm.lan/health
curl -fsS https://grafana.farm.lan/api/health
curl -fsS https://ntfy.farm.lan/v1/health
```

Open Grafana and confirm the `Farm Production Observability` dashboard loads.
Bambuddy still starts through the existing `bambuddy` service from the upstream
compose file.

## Backup and restore drill

The backup helper is dry-run by default:

```bash
python3 deploy/scripts/farm_backup_drill.py backup --env-file deploy/.env.farm
```

To create a backup ZIP in `/app/data/backups`, run the non-destructive backup
command explicitly:

```bash
python3 deploy/scripts/farm_backup_drill.py backup --env-file deploy/.env.farm --execute
```

For restore drills, do not restore into the live farm stack. Copy a selected
`bambuddy-backup-*.zip` into an isolated restore-drill host or VM and validate
that the selected file is under `FARM_BACKUP_DIR`:

```bash
python3 deploy/scripts/farm_backup_drill.py restore-check   --env-file deploy/.env.farm   --backup-file /srv/bambuddy/backups/bambuddy-backup-YYYYMMDD-HHMMSS.zip   --confirm CONFIRM_FARM_PRODUCTION_RESTORE
```

The exact confirmation phrase is `CONFIRM_FARM_PRODUCTION_RESTORE`. This helper
validates the selected backup and prints manual restore-drill steps; it does not
execute destructive restore commands against the live production stack.

Record restore evidence before calling the drill complete:

- isolated drill stack name and host;
- backup filename and checksum;
- `/health` result after restore;
- login and library/archive visibility check;
- printer list/settings spot check;
- Grafana target scrape check;
- operator name and timestamp.

## Rollback

Stop only the farm-layer services:

```bash
docker compose --project-directory .   --env-file deploy/.env.farm   -f docker-compose.yml   -f deploy/docker-compose.farm.yml   --profile farm-observability   stop caddy prometheus grafana ntfy
```

To remove the containers without deleting persisted metrics, Caddy CA data, or
ntfy state:

```bash
docker compose --project-directory .   --env-file deploy/.env.farm   -f docker-compose.yml   -f deploy/docker-compose.farm.yml   --profile farm-observability   rm -f caddy prometheus grafana ntfy
```

Do not delete Docker volumes, backup files, or Caddy CA material without
explicit human approval.
