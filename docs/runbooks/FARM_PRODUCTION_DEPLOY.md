# Farm Production Deploy

This runbook starts the first production farm-layer services around the existing
Bambuddy Docker compose deployment: Prometheus, Grafana, and ntfy. It does not
enable printer automation or change Bambuddy feature flags.

## Scope

Included in this session:

- Prometheus running from `deploy/docker-compose.farm.yml`.
- Grafana with a provisioned Prometheus datasource and baseline dashboard.
- ntfy running locally with health and Prometheus metrics enabled.
- Localhost-only host port bindings for all new services.

Deferred by operator instruction:

- Caddy TLS is deferred to the next session.
- Backup and restore drill is deferred to the next session.

## Prepare

Copy the example environment and edit the Grafana admin password before first
start:

```bash
cp deploy/.env.farm.example deploy/.env.farm
```

Keep the image values pinned as `version@sha256:digest`. Do not replace them
with `latest`.

## Start

Run from the repository root:

```bash
docker compose --project-directory . \
  --env-file deploy/.env.farm \
  -f docker-compose.yml \
  -f deploy/docker-compose.farm.yml \
  --profile farm-observability \
  up -d bambuddy prometheus grafana ntfy
```

The new service endpoints bind only to loopback until Caddy TLS is added:

- Prometheus: `http://127.0.0.1:19090`
- Grafana: `http://127.0.0.1:13030`
- ntfy: `http://127.0.0.1:18080`

Prometheus scrapes Bambuddy at `host.docker.internal:8000`. If the Bambuddy
HTTP port is changed from the upstream default, update
`deploy/observability/prometheus/prometheus.yml` in the same deployment change.

## Bambuddy Settings

Enable Bambuddy's existing Prometheus metrics setting in the application before
expecting `up{job="bambuddy"}` to become healthy. No access code, printer serial,
MQTT password, ERP token, or customer data belongs in this deploy file.

Configure Bambuddy's existing ntfy notification provider to use:

```text
server: http://127.0.0.1:18080
topic: bambuddy-farm
```

If the operator changes `NTFY_AUTH_DEFAULT_ACCESS` to `deny-all`, create a local
ntfy user/token out of band and store it outside git before updating Bambuddy's
notification provider.

## Validate

Check service health:

```bash
docker compose --project-directory . \
  --env-file deploy/.env.farm \
  -f docker-compose.yml \
  -f deploy/docker-compose.farm.yml \
  ps
```

Check Prometheus targets:

```bash
curl -fsS http://127.0.0.1:19090/-/ready
curl -fsS 'http://127.0.0.1:19090/api/v1/query?query=up%7Bjob%3D%22ntfy%22%7D'
```

Open Grafana locally and confirm the `Farm Production Observability` dashboard
loads. Bambuddy still starts through the existing `bambuddy` service from the
upstream compose file.

## Rollback

Stop only the farm-layer observability services:

```bash
docker compose --project-directory . \
  --env-file deploy/.env.farm \
  -f docker-compose.yml \
  -f deploy/docker-compose.farm.yml \
  --profile farm-observability \
  stop prometheus grafana ntfy
```

To remove the containers without deleting persisted metrics or ntfy state:

```bash
docker compose --project-directory . \
  --env-file deploy/.env.farm \
  -f docker-compose.yml \
  -f deploy/docker-compose.farm.yml \
  --profile farm-observability \
  rm -f prometheus grafana ntfy
```

Do not delete Docker volumes without explicit human approval.
