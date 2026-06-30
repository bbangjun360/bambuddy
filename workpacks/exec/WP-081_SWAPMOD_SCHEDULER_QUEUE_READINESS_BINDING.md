# WP-081 SwapMod Scheduler Queue Readiness Binding

## ID and title

WP-081 SwapMod Scheduler Queue Readiness Binding

## Observable outcome

With `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=true`, Bambuddy
scheduler `_start_print` refuses to upload, mark `printing`, clear
`awaiting_plate_clear`, or start a printer unless the queue item has an existing
READY WP-080 queue-readiness binding. When the existing Bambuddy start command
returns success, the binding is marked consumed.

## Why now

WP-079 gates scheduler dispatch by latest prior printer run, and WP-080 records
a durable READY proof for one queue item. WP-081 connects those slices so the
scheduler must verify the exact queue item binding before the next print starts.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `workpacks/exec/WP-080_SWAPMOD_QUEUE_READINESS_BINDING.md`
- `backend/app/services/print_scheduler.py`
- `backend/app/services/swapmod_queue_readiness_binding.py`
- `backend/app/models/swapmod_queue_readiness_binding.py`
- `backend/tests/unit/services/test_swapmod_scheduler_next_print_gate.py`

## In scope

- Add `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`.
- Add a scheduler-side gate service that requires an existing WP-080 binding for
  the current queue item and target printer.
- Reuse WP-080 replay checks for SwapMod cycle readiness, bed readiness, queue
  pending status, source identity, printer identity, and queue fingerprint drift.
- Block `_start_print` before source resolution, upload, queue `printing` status,
  `awaiting_plate_clear` clearing, or `printer_manager.start_print()` when the
  binding is missing, stale, consumed, or otherwise blocked.
- Mark the binding consumed only after `printer_manager.start_print()` returns
  success.
- Add service, architecture, scheduler, and harness tests including failure
  paths.

## Out of scope

- Creating queue-readiness bindings automatically from the scheduler.
- Background dispatch enforcement outside `_start_print`.
- Queue creation UI changes.
- Physical printer, MQTT, FTPS, raw G-code, or actuator changes beyond the
  existing Bambuddy-owned start path.
- ERP, Obico, slicer, or external service calls.
- New database tables or destructive migrations.
- Auto-resume of uncertain physical bed actions after restart.

## Existing behavior to characterize

- Existing WP-079 scheduler gate runs after printer existence/connectivity checks
  and before upload/status/start.
- Disabled WP-079 preserves the existing upload/start path.
- Blocked WP-079 returns `False` without upload, queue status mutation,
  `awaiting_plate_clear` clearing, or printer start.
- WP-080 binding replay rechecks queue status, bed readiness, source identity,
  printer identity, and queue fingerprint drift.

## Contract changes

New default-off setting:

- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`

When enabled, scheduler `_start_print` is allowed only when:

1. the queue item has an existing WP-080 `swapmod_queue_readiness_bindings` row,
2. the binding is for the same queue item and target printer,
3. the binding is not already consumed,
4. the source SwapMod cycle still exists and is `READY_FOR_NEXT_PRINT`,
5. the deterministic WP-077 bed-readiness record for that cycle still exists and
   is `READY_FOR_NEXT_PRINT`,
6. the queue item is still `pending`, assigned to the target printer, and has an
   archive or library-file source, and
7. the queue fingerprint still matches the binding fingerprint.

The gate does not create bindings and does not dispatch the queue item. A blocked
result logs reasons and returns before upload, queue `printing` status,
`awaiting_plate_clear` clearing, or printer start. Consumption is recorded only
after the existing Bambuddy printer start command returns success.

## Harness first

Add `harness-swapmod-scheduler-queue-readiness-binding` and
`test-swapmod-scheduler-queue-readiness-binding` targets. Harness assertions
verify no mock route or fixture exposes scheduler dispatch, printer command, or
raw G-code control.

Failure scenarios covered before product behavior was added:

- missing scheduler binding service,
- missing default-off flag,
- missing pre-upload scheduler hook,
- missing post-success consumption hook.

## Implementation milestones

1. Add failing WP-081 service, scheduler, architecture, and harness tests.
2. Expose a read-only WP-080 existing-binding replay evaluator.
3. Add the WP-081 scheduler binding gate service.
4. Hook `_start_print` before upload/status/start and after successful start for
   consumption.
5. Run focused WP-081 tests, adjacent WP-079/WP-080 tests, fast verification, and
   no-network app import smoke.

## Feature flag and default

- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- Existing `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- Existing `FARM_BED_AUTOMATION_ENABLED=false`

Default-off behavior preserves existing scheduler upload/start flow.

## Validation commands

- `make test-swapmod-scheduler-queue-readiness-binding`
- `make test-swapmod-scheduler-next-print-gate`
- `make test-swapmod-queue-readiness-binding`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-081_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

- `make test-swapmod-scheduler-queue-readiness-binding` passed: harness 2 tests, backend 19 tests.
- `make test-swapmod-scheduler-next-print-gate` passed: harness 2 tests, backend 13 tests.
- `make test-swapmod-queue-readiness-binding` passed: harness 2 tests, backend/API 27 tests.
- `make verify-fast` passed: harness 89 tests, characterization 2 tests.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`.

## Manual demonstration

No physical printer test is required for WP-081. The slice is default-off and
covered by no-network unit/harness tests that mock the existing Bambuddy start
path. Physical canary testing remains a later human-gated step.

## Migration and rollback

No new table is added. WP-081 reuses `swapmod_queue_readiness_bindings` from
WP-080 and writes only `consumed_at` after a successful existing Bambuddy start
path.

Rollback: disable `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED`.
Existing WP-080 binding rows remain durable evidence. Rows with `consumed_at` set
only record that the scheduler accepted the binding after the Bambuddy start
command succeeded.

## Logs and metrics

Blocked scheduler attempts log:

- queue item id,
- printer id,
- blocked reasons,
- binding id when present,
- source cycle key when present,
- bed state when present.

Consumption failures after a successful start log a warning but do not introduce
additional printer, ERP, Obico, slicer, MQTT, or FTPS calls.

## Risks and human gates

- Simulation success is not physical safety evidence.
- Real printer canary remains blocked behind existing human checklist and named
  canary requirements.
- The new gate is default-off and should be enabled only after WP-080 binding
  creation is integrated into the operator workflow.

## Done when

- Disabled flag preserves existing `_start_print` upload/start behavior.
- Enabled flag blocks before upload/status/start when the binding is missing,
  stale, consumed, or mismatched.
- Enabled flag allows the existing start path when the binding is READY and then
  marks it consumed only after start success.
- Focused, adjacent, fast, workpack, diff, and app-import validations pass.
