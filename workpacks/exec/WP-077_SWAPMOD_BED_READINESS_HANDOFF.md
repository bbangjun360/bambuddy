# WP-077 SwapMod Bed Readiness Handoff

## Goal

Add a default-off Bambuddy-owned handoff from a completed SwapMod cycle to the
Bambuddy bed automation readiness record. This lets the next-print gate read a
durable `READY_FOR_NEXT_PRINT` bed record after WP-076 proves a plate change is
complete.

## Scope

In scope:

- Add `GET /api/v1/swapmod-bed-readiness/status`.
- Add `POST /api/v1/swapmod-bed-readiness/cycles/{cycle_key}/records`.
- Add `FARM_SWAPMOD_BED_READINESS_HANDOFF_ENABLED=false`.
- Require an existing SwapMod cycle for the same printer.
- Record bed readiness only when the SwapMod source cycle is already
  `READY_FOR_NEXT_PRINT` with `ready_for_next_print=true`.
- Preserve idempotency by deriving one deterministic bed readiness cycle key
  from the SwapMod cycle key.
- Convert SwapMod manual-review/blocked source cycles into bed automation
  `MANUAL_REVIEW_REQUIRED` records instead of marking the bed ready.

Out of scope:

- Queue dispatch, scheduler dispatch, upload/start, or next-print automation.
- Printer transport, raw G-code, sequence files, MQTT, FTPS, or direct hardware
  commands.
- ERP, Obico, slicer, or external service calls.
- New database tables or migrations.

## Flags

- `FARM_SWAPMOD_BED_READINESS_HANDOFF_ENABLED=false`
- Existing `FARM_BED_AUTOMATION_ENABLED=false`
- Existing `FARM_BED_AUTOMATION_DRY_RUN=true`

## Contract

The request schema accepts only:

- `handoff_key`
- `printer_id`

The response returns redacted source and bed readiness metadata, including
`source_cycle_key`, `bed_cycle_key`, `handoff_status`, `bed_state`,
`ready_for_next_print`, and safety booleans proving no printer command or
dispatch occurred.

## Validation

Required commands:

- `make test-swapmod-bed-readiness`
- `make test-swapmod-state-machine`
- `make verify-fast`
- `git diff --check`

## Evidence

2026-06-30 KST local validation:

- `make test-swapmod-bed-readiness` passed: 2 harness tests and 16 backend unit/architecture/API tests.
- `make test-swapmod-state-machine` passed: 2 harness tests and 44 existing SwapMod backend tests.
- `make verify-fast` passed: context/workpack/hooks checks, 81 harness tests, and 2 characterization tests.
- `git diff --check` passed.
- The handoff route reports safe defaults with `enabled=false`, no real-command support, and no queue or scheduler dispatch support.
- The WP-077 architecture guard confirms the handoff files do not import printer transport, Bambu MQTT/FTPS, queue dispatch, scheduler dispatch, ERP/Obico, or network clients.
- No printer command, physical actuator command, queue dispatch, scheduler dispatch, ERP write, Obico action, or upload/start path was executed as part of this WP.

## Rollback

Disable `FARM_SWAPMOD_BED_READINESS_HANDOFF_ENABLED`. There is no migration.
