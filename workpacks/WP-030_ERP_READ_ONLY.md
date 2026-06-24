# WP-030 — ERP Read-Only Integration

## Observable outcome

A mock or sandbox ERP Work Order can be fetched and shown as a non-executable production
request for human review. It cannot start a printer.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `docs/modules/ERP.md`

## In scope

- ERP Adapter skeleton
- token-based API client
- Work Order mapping
- external ID mapping
- idempotent import
- retry/backoff
- review-only status
- mock and ERPNext sandbox contract tests

## Out of scope

- automatic queue
- inventory posting
- accounting posting
- printer dispatch
- ERP UI customization beyond required fixtures

## Feature flag and default

`FARM_ERP_IMPORT_ENABLED=false`.

## Done when

- duplicate fetch creates one local request,
- missing artifact becomes blocked,
- expired token and transient errors are visible and retry safely,
- no printer action route is reachable from ERP Adapter,
- prior Work Packages remain green.
