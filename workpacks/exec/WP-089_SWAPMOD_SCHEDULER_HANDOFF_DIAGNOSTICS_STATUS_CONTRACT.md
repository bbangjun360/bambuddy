# WP-089 SwapMod Scheduler Handoff Diagnostics Status Contract

## ID and title

WP-089 SwapMod Scheduler Handoff Diagnostics Status Contract

## Observable outcome

The existing read-only SwapMod scheduler handoff diagnostics status endpoint
advertises the diagnostics response contract. API and future UI consumers can
discover the required permission, response contract version, supported summary
fields, supported handoff identity statuses, supported blocked reason sources,
and no-mutation guarantees without calling the DB-backed evaluation endpoint. No
printer, scheduler dispatch, queue mutation, FTP, MQTT, raw G-code, ERP, Obico,
slicer, actuator, or physical bed boundary is touched.

## Why now

WP-088 added the additive `diagnostics_summary` object to the evaluation
response. The next smallest safe slice is exposing that summary contract through
the existing status endpoint so clients do not need to infer the shape from a
full evaluation call.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `backend/app/api/routes/swapmod_state_machine.py`
- `backend/tests/integration/test_swapmod_scheduler_handoff_diagnostics_api.py`
- `backend/tests/unit/test_swapmod_scheduler_handoff_diagnostics_architecture.py`

## In scope

- Add status metadata for the diagnostics response contract.
- Preserve the existing status route and `PRINTERS_READ` permission.
- Keep the status handler DB-free beyond shared auth dependencies.
- Add integration, architecture, harness, and Makefile coverage.

## Out of scope

- New endpoints or route permission changes.
- Diagnostic evaluation behavior changes.
- Scheduler `_start_print` behavior changes.
- Queue binding creation, consumption, or dispatch changes.
- New database schema, UI, external service contract, or public command surface.
- Any printer command, FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or
  physical bed call.
- Enabling feature flags by default.

## Contract changes

The existing `GET /api/v1/swapmod-state-machine/scheduler-handoff-diagnostics/status`
response gains additive metadata fields:

- `required_permission`
- `response_contract_version`
- `diagnostics_summary_contract_version`
- `mutates_state`
- `supported_summary_fields`
- `supported_handoff_identity_statuses`
- `supported_blocked_reason_sources`

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-swapmod-scheduler-handoff-diagnostics-status-contract` verifies the
focused no-network Makefile target exists and that mock services do not expose
status-contract command, G-code, dispatch, printer-command, or bed-action routes.

## Validation commands

- `make test-swapmod-scheduler-handoff-diagnostics-status-contract`
- `make test-swapmod-scheduler-handoff-diagnostics-status`
- `make test-swapmod-scheduler-handoff-diagnostics-auth`
- `make test-swapmod-scheduler-handoff-diagnostics-api`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-089_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_STATUS_CONTRACT.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

- `make test-swapmod-scheduler-handoff-diagnostics-status-contract` passed:
  harness 2 tests, backend 15 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-status` passed: harness 2
  tests, backend 15 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-auth` passed: harness 2
  tests, backend 15 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-api` passed: harness 2
  tests, backend 15 tests.
- `make verify-fast` passed: harness 105 tests in contract/unit phases and 2
  characterization tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-089_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_STATUS_CONTRACT.md`
  passed.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`.

## Manual demonstration

No physical printer test is required for WP-089. This slice is a no-network,
read-only status contract and never calls printer, FTP, MQTT, scheduler dispatch,
queue mutation, or bed-actuator boundaries.

## Migration and rollback

No migration is added. Rollback is removing the additive status metadata, focused
Makefile target, harness check, tests, and workpack. Runtime scheduler behavior
remains controlled by existing default-off gates.

## Logs and metrics

No new logs or metrics are added. The status response itself exposes the
contract metadata needed to diagnose client/server contract mismatch.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused status-contract target passes.
- The status endpoint advertises required permission, contract versions, supported
  summary fields, supported identity statuses, supported reason sources, and
  `mutates_state=false`.
- The status handler remains route-level DB-free beyond shared auth dependencies.
- Adjacent status/auth/API targets, `verify-fast`, workpack check, diff check,
  and app-import smoke pass.
