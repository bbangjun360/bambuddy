# WP-095 SwapMod Scheduler Handoff Diagnostics Summary Count Contract

## ID and title

WP-095 SwapMod Scheduler Handoff Diagnostics Summary Count Contract

## Observable outcome

The existing read-only SwapMod scheduler handoff diagnostics status response
advertises which `diagnostics_summary` fields are count/integer values. API and
future UI consumers can discover that `blocked_reason_count` is the supported
summary count field without calling printer, scheduler dispatch, queue mutation,
FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or physical bed
boundaries.

## Why now

WP-094 exposed the summary boolean field set. The next smallest safe slice is
exposing the summary count field set so clients can validate count state without
inferring it from examples or live diagnostics evaluations.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `backend/app/api/routes/swapmod_state_machine.py`
- `backend/tests/integration/test_swapmod_scheduler_handoff_diagnostics_api.py`
- `backend/tests/unit/test_swapmod_scheduler_handoff_diagnostics_architecture.py`

## In scope

- Add additive status response field `supported_summary_count_fields`.
- Preserve the existing diagnostics status route and `PRINTERS_READ` permission.
- Keep the status handler DB-free beyond shared auth dependencies.
- Add integration, architecture, harness, and Makefile coverage.

## Out of scope

- New endpoints or route permission changes.
- Scheduler `_start_print` behavior changes.
- Queue binding creation, consumption, or dispatch changes.
- Diagnostics summary evaluation behavior changes.
- New database schema, UI, external service contract, or public command surface.
- Any printer command, FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or
  physical bed call.
- Enabling feature flags by default.

## Contract changes

The existing diagnostics status response gains additive field:

- `supported_summary_count_fields`

The supported summary count field list is:

- `blocked_reason_count`

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-swapmod-scheduler-handoff-diagnostics-summary-count-contract` verifies
the focused no-network Makefile target exists and that mock services do not
expose summary-count-contract command, G-code, dispatch, printer-command, or
bed-action routes.

## Validation commands

- `make test-swapmod-scheduler-handoff-diagnostics-summary-count-contract`
- `make test-swapmod-scheduler-handoff-diagnostics-summary-boolean-contract`
- `make test-swapmod-scheduler-handoff-diagnostics-gate-status-contract`
- `make test-swapmod-scheduler-handoff-diagnostics-detail-contract`
- `make test-swapmod-scheduler-handoff-diagnostics-blocker-details`
- `make test-swapmod-scheduler-handoff-diagnostics-reason-catalog`
- `make test-swapmod-scheduler-handoff-diagnostics-status-contract`
- `make test-swapmod-scheduler-handoff-diagnostics-explainability`
- `make test-swapmod-scheduler-handoff-diagnostics-status`
- `make test-swapmod-scheduler-handoff-diagnostics-auth`
- `make test-swapmod-scheduler-handoff-diagnostics-api`
- `make test-swapmod-scheduler-handoff-diagnostics`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-095_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_SUMMARY_COUNT_CONTRACT.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

- RED check failed for the expected missing contract field and focused Makefile
  target: missing `supported_summary_count_fields` and missing
  `harness-swapmod-scheduler-handoff-diagnostics-summary-count-contract`.
- `make test-swapmod-scheduler-handoff-diagnostics-summary-count-contract`
  passed: harness 2 tests, backend 16 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-summary-boolean-contract`
  passed: harness 2 tests, backend 16 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-gate-status-contract` passed:
  harness 2 tests, backend 16 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-detail-contract` passed:
  harness 2 tests, backend 16 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-blocker-details` passed:
  harness 2 tests, backend 20 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-reason-catalog` passed:
  harness 2 tests, backend 20 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-status-contract` passed:
  harness 2 tests, backend 16 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-explainability` passed:
  harness 2 tests, backend 20 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-status` passed: harness 2
  tests, backend 16 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-auth` passed: harness 2
  tests, backend 16 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-api` passed: harness 2
  tests, backend 16 tests.
- `make test-swapmod-scheduler-handoff-diagnostics` passed: harness 2 tests,
  backend 10 tests.
- `make verify-fast` passed: harness 117 tests in contract/unit phases and 2
  characterization tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-095_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_SUMMARY_COUNT_CONTRACT.md`
  passed.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`. This is the
  Bambuddy still starts statement for this read-only slice.

## Manual demonstration

No physical printer test is required for WP-095. This slice is a no-network,
read-only contract addition and never calls printer, FTP, MQTT, scheduler
dispatch, queue mutation, or bed-actuator boundaries.

## Migration and rollback

No migration is added. Rollback is removing the additive status field, focused
Makefile target, harness check, tests, and this workpack. Runtime scheduler
behavior remains controlled by existing default-off gates.

## Logs and metrics

No new logs or metrics are added. The read-only diagnostics status response
exposes static summary count fields needed to diagnose and render summary state
consistently.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused summary-count-contract target passes.
- The status response reports the supported summary count fields in order.
- The status handler remains read-only, DB-free, and permission-preserving.
- Existing diagnostics summary and blocker detail behavior is unchanged.
- Adjacent diagnostics targets, `verify-fast`, workpack check, diff check, and
  app-import smoke pass.
