# WP-080 SwapMod Queue Readiness Binding

## Goal

Record a durable, idempotent binding between a verified SwapMod bed-readiness
proof and one specific pending Bambuddy queue item. This closes the next safety
gap after WP-079 by making the READY proof consumable by queue-item identity
instead of only by latest prior printer run identity.

## Scope

In scope:

- Add `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`.
- Add a durable `swapmod_queue_readiness_bindings` table/model.
- Add a record-only service that validates a READY SwapMod cycle, matching READY
  bed-readiness record, and pending queue item for the requested printer.
- Add an API under the existing SwapMod state-machine routes to create a binding.
- Make binding creation idempotent by `binding_key`, unique per queue item, and unique per bed-readiness proof.
- Preserve queue status and avoid scheduler dispatch, upload, printer start, ERP,
  Obico, MQTT, FTPS, or actuator calls.
- Add service, architecture, API, and harness tests including failure paths.

Out of scope:

- Scheduler consumption/enforcement of queue-readiness bindings.
- Background dispatch enforcement.
- Queue creation UI changes.
- Physical printer, MQTT, FTPS, raw G-code, or actuator changes.
- ERP, Obico, slicer, or external service calls.
- Auto-resume or automatic consumption after restart.

## Flags

- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- Existing `FARM_BED_AUTOMATION_ENABLED=false`

## Contract

When enabled, `POST /api/v1/swapmod-state-machine/cycles/{cycle_key}/queue-readiness-bindings`
records one binding only when:

1. the SwapMod cycle exists for the requested printer,
2. the SwapMod cycle is `READY_FOR_NEXT_PRINT`,
3. the deterministic WP-077 bed-readiness record exists and is
   `READY_FOR_NEXT_PRINT`,
4. the queue item exists, is still `pending`, and is assigned to the requested
   printer, and
5. the queue item has an archive or library-file source identity, and
6. the bed-readiness proof has not already been bound to another queue item.

The route is record-only. It returns blocked reasons without creating a binding
when readiness or queue checks fail. It does not dispatch the queue item, mutate
queue status, clear `awaiting_plate_clear`, upload files, or start a printer.

## Database

New table: `swapmod_queue_readiness_bindings`. Fresh installs are covered by
`Base.metadata.create_all`. Existing installs create the missing table during
startup through the same SQLAlchemy model-import path used by other farm tables.
No destructive migration is required.

## Validation

Required commands:

- `make test-swapmod-queue-readiness-binding`
- `make test-swapmod-next-print-gate`
- `make test-swapmod-scheduler-next-print-gate`
- `make verify-fast`
- `git diff --check`

## Evidence

- `make test-swapmod-queue-readiness-binding` passed: harness 2 tests, backend/API 27 tests.
- `make test-swapmod-next-print-gate` passed: harness 2 tests, backend/API 17 tests.
- `make test-swapmod-scheduler-next-print-gate` passed: harness 2 tests, backend 13 tests.
- `make verify-fast` passed: harness 87 tests, characterization 2 tests.
- `git diff --check` passed.
- Bambuddy app import smoke passed in Docker no-network: `bambuddy_app_import_ok True`.

## Rollback

Disable `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED`. Existing binding rows are
record-only evidence and are not consumed by the scheduler in this Work Package.
If a full rollback is required after deployment, drop `swapmod_queue_readiness_bindings`
after confirming no later Work Package consumes it.
