# WP-078 SwapMod Next Print Gate

## Goal

Add a default-off, evaluate-only next-print gate that combines the completed
SwapMod state machine cycle with the WP-077 bed readiness record. The gate
reports whether the next print may proceed, but it never dispatches a queue item
or starts a printer.

## Scope

In scope:

- Add `GET /api/v1/swapmod-state-machine/next-print-gates/status`.
- Add `POST /api/v1/swapmod-state-machine/cycles/{cycle_key}/next-print-gates`.
- Add `FARM_SWAPMOD_NEXT_PRINT_GATE_ENABLED=false`.
- Require an existing SwapMod cycle for the requested printer.
- Require the SwapMod source cycle to be `READY_FOR_NEXT_PRINT` with
  `ready_for_next_print=true`.
- Require the deterministic WP-077 bed readiness record to be
  `READY_FOR_NEXT_PRINT` with `ready_for_next_print=true`.
- Return blocked reasons for missing bed readiness, manual review, printer
  mismatch, missing printer identity, or non-ready source state.

Out of scope:

- Queue mutation, scheduler mutation, upload/start, or any next-print dispatch.
- Printer transport, raw G-code, MQTT, FTPS, or direct hardware commands.
- ERP, Obico, slicer, or external service calls.
- New database tables or migrations.

## Flags

- `FARM_SWAPMOD_NEXT_PRINT_GATE_ENABLED=false`
- Existing `FARM_SWAPMOD_STATE_MACHINE_ENABLED=false`
- Existing `FARM_BED_AUTOMATION_ENABLED=false`

## Contract

The request schema accepts only:

- `gate_key`
- `printer_id`

The response returns `gate_status`, `next_print_allowed`, source cycle state,
bed readiness state, and blocked reasons. It also returns safety booleans proving
that no real command, printer command, queue dispatch, or scheduler dispatch was
performed.

## Validation

Required commands:

- `make test-swapmod-next-print-gate`
- `make test-swapmod-bed-readiness`
- `make test-swapmod-state-machine`
- `make verify-fast`
- `git diff --check`

## Evidence

- `make test-swapmod-next-print-gate` passed: harness 2 tests, backend 17 tests.
- `make test-swapmod-bed-readiness` passed: harness 2 tests, backend 16 tests.
- `make test-swapmod-state-machine` passed: harness 2 tests, backend 44 tests.
- `make verify-fast` passed: harness 83 tests, characterization 2 tests.
- `git diff --check` passed.
- Bambuddy app import smoke passed in Docker no-network: `bambuddy_app_import_ok True`.

## Rollback

Disable `FARM_SWAPMOD_NEXT_PRINT_GATE_ENABLED`. There is no migration.
