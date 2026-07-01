# WP-084 SwapMod Scheduler Handoff Diagnostics

## ID and title

WP-084 SwapMod Scheduler Handoff Diagnostics

## Observable outcome

Operators and tests can evaluate whether a pending queue item would pass the
SwapMod scheduler handoff gates without starting the print. The diagnostic
returns the existing next-print gate, queue-readiness binding gate, handoff
identity mismatch reasons, and default-off/no-command sentinels while leaving
the queue item and readiness binding unchanged.

## Why now

WP-083 proved a consumed handoff cannot be automatically retried after watchdog
rollback. The next smallest safety slice is read-only visibility into the same
gate chain so blocked scheduler starts can be diagnosed without exercising FTP,
MQTT, queue status mutation, bed-clear mutation, printer start, ERP, Obico, or
physical bed hardware.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `backend/app/services/swapmod_scheduler_handoff_diagnostics.py`
- `backend/app/services/swapmod_scheduler_next_print_gate.py`
- `backend/app/services/swapmod_scheduler_queue_readiness_binding.py`
- `backend/tests/unit/services/test_swapmod_scheduler_handoff_diagnostics.py`

## In scope

- Add `test-swapmod-scheduler-handoff-diagnostics` and matching harness target.
- Add a no-network service test for a READY handoff that reports scheduler start
  allowed while keeping the queue item `pending` and the binding unconsumed.
- Add a failure-path test for an already consumed binding that reports
  `queue_readiness_binding_consumed` without mutating queue or binding state.
- Add a failure-path test for mismatched latest-run/binding handoff identity that
  reports `scheduler_handoff_source_print_run_mismatch` and
  `scheduler_handoff_source_cycle_mismatch`.
- Add architecture and harness assertions that the diagnostic service does not
  import scheduler dispatch, FTP/MQTT, printer command, ERP, Obico, raw G-code,
  or network/client surfaces.

## Out of scope

- Scheduler `_start_print` behavior changes.
- New database schema, UI, API route, or external service contract.
- Automatic queue binding creation or background dispatch.
- Physical printer, MQTT, FTPS, raw G-code, actuator, ERP, Obico, or slicer
  calls.
- Enabling feature flags by default.
- Auto-resume of uncertain physical bed actions after restart.

## Contract changes

No public API contract changes. WP-084 adds an internal read-only service payload:

- `mode=SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS`
- `gate_status=allowed|blocked`
- `scheduler_start_allowed=true|false`
- `blocked_reasons=[...]`
- nested `scheduler_next_print_gate`
- nested `scheduler_queue_readiness_binding_gate`
- `handoff_identity_blocked_reasons=[...]`

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-swapmod-scheduler-handoff-diagnostics` verifies the Makefile exposes
the focused no-network target and that mock services still do not provide
diagnostic dispatch, printer command, or arbitrary G-code control surfaces.

## Validation commands

- `make test-swapmod-scheduler-handoff-diagnostics`
- `make test-swapmod-scheduler-consumed-handoff-retry`
- `make test-swapmod-scheduler-handoff-chain`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-084_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

- `make test-swapmod-scheduler-handoff-diagnostics` passed: harness 2 tests, backend 6 tests.
- `make test-swapmod-scheduler-consumed-handoff-retry` passed: harness 2 tests, backend 2 tests.
- `make test-swapmod-scheduler-handoff-chain` passed: harness 2 tests, backend 3 tests.
- `make verify-fast` passed: harness 95 tests and characterization 2 tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-084_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS.md` passed.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`.

## Manual demonstration

No physical printer test is required for WP-084. This slice is a no-network
read-only diagnostics validation that mocks only existing Bambuddy database
state and never calls printer, FTP, MQTT, or bed-actuator boundaries. Physical
canary testing remains a later human-gated step.

## Migration and rollback

No migration is added. Rollback is removing the WP-084 diagnostic service,
tests, Makefile target, and workpack. Runtime scheduler behavior remains
controlled by existing default-off gates.

## Logs and metrics

No new logs or metrics are added. The diagnostic payload returns existing
blocked reason strings and explicit no-command sentinels for troubleshooting.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused handoff diagnostics target passes.
- READY handoff diagnostics report start allowed while leaving the queue item
  `pending` and the binding unconsumed.
- Consumed-binding diagnostics report `queue_readiness_binding_consumed` without
  queue mutation.
- Mismatched latest-run/binding diagnostics report both handoff identity blocked
  reasons.
- Adjacent WP-082/WP-083 tests, `verify-fast`, workpack check, diff check, and
  app-import smoke pass.
