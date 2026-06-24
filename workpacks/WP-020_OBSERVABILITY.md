# WP-020 — Observability Baseline

## Observable outcome

A developer can identify service health, current build SHA, slice failures, and integration
mock failures without opening container internals.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `docs/modules/OBSERVABILITY.md`

## In scope

- structured correlation IDs
- Prometheus scrape configuration
- initial Grafana dashboard
- alert for application down and backup failure
- log redaction test

## Out of scope

- business KPI perfection
- InfluxDB
- custom UI dashboard

## Harness first

Create metric assertions and a secret-redaction fixture before adding dashboards.

## Done when

- harness can scrape metrics,
- a forced failure is visible in logs and metrics,
- no synthetic secret appears in emitted logs,
- WP-000 and WP-010 remain green.
