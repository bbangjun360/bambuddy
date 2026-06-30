# WP-079 SwapMod Scheduler Next Print Gate

## Goal

Enforce the WP-078 next-print gate in the Bambuddy queue scheduler before any
next print is uploaded, marked printing, or started. The enforcement is
default-off and tied to the latest durable `PrintLogEntry` for the target
printer to avoid stale bed-readiness records allowing future prints forever.

## Scope

In scope:

- Add `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`.
- Add a read-only scheduler gate service that maps the latest printer run to
  `print_log:{id}` and finds the matching SwapMod cycle.
- Reuse WP-078 evaluation against the matching SwapMod cycle and WP-077 bed
  readiness record.
- Call the scheduler gate before upload, queue status mutation,
  `awaiting_plate_clear` clearing, or `printer_manager.start_print()`.
- Leave disabled behavior unchanged.
- Block inside `_start_print` without mutating queue status when the latest
  print run, matching SwapMod cycle, or bed readiness proof is missing or not READY.

Out of scope:

- Background dispatch enforcement.
- Durable queue-item-to-readiness binding; no safe existing queue-item binding
  exists, so this Work Package gates scheduler dispatch by latest prior
  `PrintLogEntry` identity only.
- Pre-existing scheduler assignment or AMS-mapping mutations that happen before
  `_start_print`; this Work Package prevents upload/status/start side effects.
- Direct printer, MQTT, FTPS, raw G-code, or physical actuator changes.
- ERP, Obico, slicer, or external service calls.
- New database tables or migrations.
- UI changes.

## Flags

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- Existing `FARM_BED_AUTOMATION_ENABLED=false`

## Contract

When enabled, scheduler dispatch for a printer is allowed only when:

1. the printer has a latest `PrintLogEntry`,
2. a SwapMod cycle exists for that printer with
   `source_print_run_id == print_log:{latest_print_log_id}`,
3. the SwapMod cycle is `READY_FOR_NEXT_PRINT`, and
4. the deterministic WP-077 bed readiness record for that cycle is
   `READY_FOR_NEXT_PRINT`.

The gate is read-only. A blocked result logs reasons and returns before upload,
queue `printing` status, `awaiting_plate_clear` clearing, or printer start. The
`_start_print` hook does not alter queue state when it blocks; assignment or
AMS-mapping changes that already happened earlier in `check_queue()` are outside
this slice.

## Validation

Required commands:

- `make test-swapmod-scheduler-next-print-gate`
- `make test-swapmod-next-print-gate`
- `make test-swapmod-bed-readiness`
- `make verify-fast`
- `git diff --check`

## Evidence

- `make test-swapmod-scheduler-next-print-gate` passed: harness 2 tests, backend 13 tests.
- `make test-swapmod-next-print-gate` passed: harness 2 tests, backend 17 tests.
- `make test-swapmod-bed-readiness` passed: harness 2 tests, backend 16 tests.
- `make test-swapmod-state-machine` passed: harness 2 tests, backend 44 tests.
- `make verify-fast` passed: harness 85 tests, characterization 2 tests.
- `git diff --check` passed.
- Bambuddy app import smoke passed in Docker no-network: `bambuddy_app_import_ok True`.

## Rollback

Disable `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED`. There is no migration.
