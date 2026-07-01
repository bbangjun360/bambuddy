# WP-086 SwapMod Scheduler Handoff Diagnostics Status

## ID and title

WP-086 SwapMod Scheduler Handoff Diagnostics Status

## Observable outcome

Operators and tests can query a read-only status endpoint for the SwapMod
scheduler handoff diagnostics API. The status payload reports required query
parameters, current default-off gate settings, and no-command sentinels without
opening a handler database session or touching scheduler, queue, printer, ERP, Obico,
FTP, MQTT, raw G-code, slicer, actuator, or physical bed state.

## Why now

WP-085 exposed the diagnostic evaluation endpoint. The next smallest safety
slice is a companion status endpoint that lets operators and clients discover
the API contract and active safety flags before asking for a specific queue
item diagnostic.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `backend/app/api/routes/swapmod_state_machine.py`
- `backend/tests/integration/test_swapmod_scheduler_handoff_diagnostics_api.py`
- `backend/tests/unit/test_swapmod_scheduler_handoff_diagnostics_architecture.py`

## In scope

- Add `GET /api/v1/swapmod-state-machine/scheduler-handoff-diagnostics/status`.
- Require only `PRINTERS_READ` when auth is enabled.
- Return required query parameters for the diagnostic evaluation endpoint.
- Return existing default-off scheduler gate and bed automation settings.
- Add API, architecture, and harness checks proving the status endpoint is
  read-only, no-network, and does not open a handler database session beyond shared auth dependencies.

## Out of scope

- Scheduler `_start_print` behavior changes.
- Diagnostic evaluation behavior changes.
- New database schema, UI, external service contract, or public command surface.
- Queue binding creation or scheduler dispatch.
- Any printer command, FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or
  physical bed call.
- Enabling feature flags by default.
- Auto-resume of uncertain physical bed actions after restart.

## Contract changes

Adds one read-only API contract:

- `GET /api/v1/swapmod-state-machine/scheduler-handoff-diagnostics/status`
- Returns:
  - `mode=SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_API_STATUS`
  - `api_enabled=true`
  - `read_only=true`
  - `required_query_parameters=["queue_item_id", "printer_id"]`
  - `scheduler_next_print_gate_enabled`
  - `scheduler_queue_readiness_binding_enabled`
  - `bed_automation_enabled`
  - no-command sentinels

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-swapmod-scheduler-handoff-diagnostics-status` verifies the Makefile
exposes the focused no-network status target and that mock services still do
not provide status command, dispatch, printer, or G-code routes.

## Validation commands

- `make test-swapmod-scheduler-handoff-diagnostics-status`
- `make test-swapmod-scheduler-handoff-diagnostics-api`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-086_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_STATUS.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

- `make test-swapmod-scheduler-handoff-diagnostics-status` passed: harness 2
  tests, backend 9 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-api` passed: harness 2
  tests, backend 9 tests.
- `make verify-fast` passed: harness 99 tests in contract/unit phases and 2
  characterization tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-086_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_STATUS.md`
  passed.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`.

## Manual demonstration

No physical printer test is required for WP-086. This slice is a no-network,
read-only status API validation and never calls printer, FTP, MQTT, scheduler
dispatch, or bed-actuator boundaries.

## Migration and rollback

No migration is added. Rollback is removing the status endpoint, tests,
Makefile target, and workpack. Runtime scheduler behavior remains controlled by
existing default-off gates.

## Logs and metrics

No new logs or metrics are added. The status payload returns existing settings
and explicit no-command sentinels for troubleshooting.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused diagnostics status target passes.
- Status API reports required query parameters and default-off safety flags.
- Architecture checks prove the status route is read-only and handler DB-free.
- WP-085 diagnostics API target, `verify-fast`, workpack check, diff check, and
  app-import smoke pass.
