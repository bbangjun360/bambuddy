# WP-040 — ERP Draft Production Result

## Observable outcome

A synthetic completed PrintRun creates exactly one Draft ERP document through the Adapter.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `docs/modules/ERP.md`

## In scope

- completion event schema
- outbox delivery
- ERP Draft write
- idempotency
- timeout-after-create lookup
- dead-letter
- reconciliation report

## Out of scope

- document auto-submit
- tax invoice
- production accounting close
- real customer/order data

## Feature flag and default

`FARM_ERP_DRAFT_POSTING_ENABLED=false`.

## Done when

- repeated delivery creates one Draft,
- timeout after creation does not duplicate it,
- failed events enter dead-letter,
- reconciliation detects a deliberately injected mismatch,
- finance review is still required.
