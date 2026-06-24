# WP-050 — Bed Automation State Machine and Simulator

## Observable outcome

A completed simulated PrintRun can move through the full bed state machine with a fake
PrintFlow Adapter, including failure and restart recovery, without moving hardware.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `docs/modules/BED_AUTOMATION.md`
- `docs/methodology/HARNESS_ARCHITECTURE.md`

## In scope

- durable BedCycle model
- policy selection
- exclusive lease
- mock adapter contract
- idempotency
- simulator scenarios
- restart recovery
- manual review
- next-job gate
- metrics and audit log

## Out of scope

- real PrintFlow driver
- physical motion
- automatic enablement
- universal 35°C threshold
- custom UI

## Feature flag and default

```text
FARM_BED_AUTOMATION_ENABLED=false
FARM_BED_AUTOMATION_DRY_RUN=true
```

## Done when

- all required invariants have tests,
- restart during uncertain execution becomes MANUAL_REVIEW,
- duplicate requests do not repeat action,
- next job remains blocked until READY,
- no real device credential exists in the test environment.
