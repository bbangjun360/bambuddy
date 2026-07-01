# WP-090 SwapMod Scheduler Handoff Diagnostics Reason Catalog

## ID and title

WP-090 SwapMod Scheduler Handoff Diagnostics Reason Catalog

## Observable outcome

The existing read-only SwapMod scheduler handoff diagnostics API exposes a stable
blocked reason catalog and returns a primary operator action hint in the existing
`diagnostics_summary`. API and future UI consumers can map scheduler handoff
blockers to safe review actions without calling printer, scheduler dispatch,
queue mutation, FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or physical
bed boundaries.

## Why now

WP-089 advertised the diagnostics response contract through the status endpoint.
The next smallest safe slice is making the blocked reason vocabulary discoverable
and giving the existing summary one safe, code-level hint for the primary blocker.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `backend/app/services/swapmod_scheduler_handoff_diagnostics.py`
- `backend/app/api/routes/swapmod_state_machine.py`
- `backend/tests/unit/services/test_swapmod_scheduler_handoff_diagnostics.py`
- `backend/tests/integration/test_swapmod_scheduler_handoff_diagnostics_api.py`
- `backend/tests/unit/test_swapmod_scheduler_handoff_diagnostics_architecture.py`

## In scope

- Add a static, source-qualified blocked reason catalog for the existing
  scheduler handoff diagnostics surface.
- Add additive summary fields for the primary operator action and the source that
  produced it.
- Preserve the existing diagnostics status route and `PRINTERS_READ` permission.
- Keep the status handler DB-free beyond shared auth dependencies.
- Add unit, integration, architecture, harness, and Makefile coverage.

## Out of scope

- New endpoints or route permission changes.
- Scheduler `_start_print` behavior changes.
- Queue binding creation, consumption, or dispatch changes.
- New database schema, UI, external service contract, or public command surface.
- Any printer command, FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or
  physical bed call.
- Enabling feature flags by default.

## Contract changes

The existing `diagnostics_summary` object gains additive fields:

- `primary_operator_action`
- `primary_operator_action_source`

The existing `GET /api/v1/swapmod-state-machine/scheduler-handoff-diagnostics/status`
response gains an additive `blocked_reason_catalog` object with:

- `contract_version`
- `sources`
- source-qualified reason entries containing `reason` and `operator_action`

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-swapmod-scheduler-handoff-diagnostics-reason-catalog` verifies the
focused no-network Makefile target exists and that mock services do not expose
reason-catalog command, G-code, dispatch, printer-command, or bed-action routes.

## Validation commands

- `make test-swapmod-scheduler-handoff-diagnostics-reason-catalog`
- `make test-swapmod-scheduler-handoff-diagnostics-status-contract`
- `make test-swapmod-scheduler-handoff-diagnostics-explainability`
- `make test-swapmod-scheduler-handoff-diagnostics-status`
- `make test-swapmod-scheduler-handoff-diagnostics-auth`
- `make test-swapmod-scheduler-handoff-diagnostics-api`
- `make test-swapmod-scheduler-handoff-diagnostics`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-090_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_REASON_CATALOG.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

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
- `make verify-fast` passed: harness 107 tests in contract/unit phases and 2
  characterization tests.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`. This is the
  Bambuddy still starts statement for this read-only slice.

## Manual demonstration

No physical printer test is required for WP-090. This slice is a no-network,
read-only contract addition and never calls printer, FTP, MQTT, scheduler
dispatch, queue mutation, or bed-actuator boundaries.

## Migration and rollback

No migration is added. Rollback is removing the additive summary fields, status
catalog metadata, focused Makefile target, harness check, tests, and workpack.
Runtime scheduler behavior remains controlled by existing default-off gates.

## Logs and metrics

No new logs or metrics are added. The status response exposes the reason catalog
needed to diagnose client/server contract mismatch, and `diagnostics_summary`
identifies the primary blocked reason and safe operator action code.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused reason-catalog target passes.
- The status endpoint advertises the blocked reason catalog without opening a DB
  session in the handler.
- The diagnostics summary reports a primary operator action for missing latest
  print logs, consumed queue readiness bindings, and handoff identity mismatch.
- The architecture guard verifies current emitted blocker reasons are present in
  the source-qualified catalog.
- The ready path reports no primary operator action.
- Adjacent status-contract/explainability/status/auth/API targets, `verify-fast`,
  workpack check, diff check, and app-import smoke pass.
