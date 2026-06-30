# WP-082 SwapMod Scheduler Handoff Chain

## ID and title

WP-082 SwapMod Scheduler Handoff Chain

## Observable outcome

With the existing SwapMod scheduler gates enabled, Bambuddy scheduler proves the
latest-print READY gate and queue-readiness binding gate describe the same
SwapMod handoff chain before upload, queue status mutation, bed-clear state, or
printer start. A mismatched READY cycle and queue binding are blocked before any
external printer boundary is reached.

## Why now

WP-079 verifies the latest previous print run is READY for the next scheduler
start. WP-080 records the exact queue item binding for a READY SwapMod handoff.
WP-081 consumes that binding only after Bambuddy's existing start command
returns success. WP-082 closes the composition gap: both gates must point to the
same source print run and SwapMod cycle, not merely pass independently.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `workpacks/exec/WP-081_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING.md`
- `backend/app/services/print_scheduler.py`
- `backend/app/services/swapmod_scheduler_next_print_gate.py`
- `backend/app/services/swapmod_queue_readiness_binding.py`
- `backend/app/services/swapmod_scheduler_queue_readiness_binding.py`
- `backend/tests/unit/services/test_swapmod_scheduler_handoff_chain.py`

## In scope

- Add `test-swapmod-scheduler-handoff-chain` and matching harness target.
- Add a no-network scheduler chain test that creates the previous
  `PrintLogEntry`, READY SwapMod cycle, READY bed-readiness record, queue item,
  queue-readiness binding, and then runs `_start_print` with both scheduler gates
  enabled.
- Assert the allowed path uses one shared source print run and cycle, uploads
  through mocked FTP, calls the existing Bambuddy-owned `printer_manager.start_print`,
  marks the queue item `printing`, and consumes the WP-080 binding only after
  start success.
- Add a failure-path test where the latest print run is READY through cycle A
  but the queue binding is READY through cycle B, proving `_start_print` returns
  before upload, queue status mutation, bed clear, or printer start.
- Add a scheduler-side identity guard comparing `latest_print_run_id` and
  `source_cycle_key` from the next-print gate with the binding gate payload.
- Add harness assertions that mock services do not expose handoff dispatch,
  raw G-code, or printer-control routes.
- Record the core scheduler patch in `.fuzzyline/PATCH_LEDGER.yaml`.

## Out of scope

- New database schema, UI, API routes, or external service contracts.
- Automatic queue binding creation or background dispatch.
- Physical printer, MQTT, FTPS, raw G-code, actuator, ERP, Obico, or slicer
  calls.
- Enabling feature flags by default.
- Auto-resume of uncertain physical bed actions after restart.

## Contract changes

No new public API contract. Scheduler logging may now include these blocked
reasons when both gates are enabled but point to different handoff evidence:

- `scheduler_handoff_source_print_run_mismatch`
- `scheduler_handoff_source_cycle_mismatch`

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-swapmod-scheduler-handoff-chain` verifies the Makefile exposes the
focused no-network target and that mock services still do not provide scheduler
dispatch, printer command, or arbitrary G-code control surfaces.

## Validation commands

- `make test-swapmod-scheduler-handoff-chain`
- `make test-swapmod-scheduler-queue-readiness-binding`
- `make test-swapmod-queue-readiness-binding`
- `make test-swapmod-scheduler-next-print-gate`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-082_SWAPMOD_SCHEDULER_HANDOFF_CHAIN.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.
- Core patch ledger review for `.fuzzyline/PATCH_LEDGER.yaml`.

Evidence from this branch:

- `make test-swapmod-scheduler-handoff-chain` passed: harness 2 tests, backend 3 tests.
- `make test-swapmod-scheduler-queue-readiness-binding` passed: harness 2 tests, backend 19 tests.
- `make test-swapmod-queue-readiness-binding` passed: harness 2 tests, backend/API 27 tests.
- `make test-swapmod-scheduler-next-print-gate` passed: harness 2 tests, backend 13 tests.
- `make verify-fast` passed: harness 91 tests, characterization 2 tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-082_SWAPMOD_SCHEDULER_HANDOFF_CHAIN.md` passed.
- `git diff --check` passed.
- Core patch ledger recorded `WP-082-swapmod-scheduler-handoff-chain` in `.fuzzyline/PATCH_LEDGER.yaml`.
- No-network app import smoke passed: `bambuddy_app_import_ok True`.

## Manual demonstration

No physical printer test is required for WP-082. This slice is a no-network
handoff-chain validation that mocks only existing Bambuddy external boundaries.
Physical canary testing remains a later human-gated step.

## Migration and rollback

No migration is added. Rollback is disabling the existing scheduler gates or
reverting the scheduler identity guard and tests. Runtime behavior remains
controlled by the existing default-off flags.

## Logs and metrics

The failure-path test asserts the existing scheduler warning path includes the
handoff-chain blocked reasons. No new metric contract is added.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused handoff-chain target passes.
- The allowed path consumes the readiness binding only after the mocked existing
  Bambuddy start command succeeds.
- The mismatched latest-run/binding path blocks before upload, status mutation,
  `awaiting_plate_clear` clearing, or printer start.
- Adjacent WP-079/WP-080/WP-081 tests, `verify-fast`, workpack check, and diff
  check pass.
