# WP-000 — Bambuddy Baseline and Harness

## Observable outcome

A developer can clone the Fork, run one command group, open the unchanged Bambuddy UI,
and verify that application, database, logs, and test harness are healthy.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `docs/modules/BAMBUDDY_BASELINE.md`
- `docs/methodology/INCREMENTAL_DELIVERY.md`
- `docs/methodology/HARNESS_ARCHITECTURE.md`
- `docs/methodology/CONTEXT_STRATEGY.md`

## In scope

- pin exact Bambuddy upstream tag/SHA
- run existing tests and record baseline
- bridge-mode harness Compose with PostgreSQL
- deterministic mock-services container
- Makefile command contract
- health and reset scripts
- context-budget and Work Package checks
- Codex hooks installed but not silently trusted
- CI fast gate
- backup/restore smoke procedure
- unchanged Bambuddy UI

## Out of scope

- Orca sidecar
- printer connection
- ERPNext
- bed automation
- Obico
- UI changes
- business data model changes

## Harness first

1. Make context and Work Package checks pass.
2. Make mock services start and answer `/health`.
3. Make PostgreSQL start and pass readiness.
4. Make Bambuddy start from the current Fork.
5. Add a smoke check using the actual Bambuddy health/root endpoint discovered from source.
6. Add a clean reset that never runs against production.

## Implementation milestones

### M0 — Baseline inventory

Record exact upstream SHA, commands, environment requirements, and current failing tests.

### M1 — Local harness

Make `make harness-up`, `make harness-health`, and `make harness-down` work.

### M2 — Fast gate

Make `make verify-fast` run context checks and the smallest reliable upstream tests.

### M3 — Persistence

Create data, restart the application, and prove persistence.

### M4 — Backup and restore

Restore a backup into a clean harness database and prove startup.

## Feature flag and default

No new feature flag.

## Validation commands

```bash
python3 harness/scripts/check_context_budget.py
python3 harness/scripts/check_workpack.py workpacks/WP-000_BASELINE_AND_HARNESS.md
make harness-config
make harness-up
make harness-health
make verify-fast
make harness-down
```

## Done when

- unchanged Bambuddy UI opens,
- no real printer credential is required,
- database survives restart,
- fast gate is deterministic,
- reset is confined to the harness project,
- all observed baseline failures are documented rather than hidden.
