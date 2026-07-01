# WP-091 SwapMod Scheduler Handoff Diagnostics Blocker Details

## ID and title

WP-091 SwapMod Scheduler Handoff Diagnostics Blocker Details

## Observable outcome

The existing read-only SwapMod scheduler handoff diagnostics response includes a
source-qualified `blocked_reason_details` ledger in `diagnostics_summary`. API
and future UI consumers can explain every current blocked reason, not only the
primary blocker, without calling printer, scheduler dispatch, queue mutation,
FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or physical bed boundaries.

## Why now

WP-090 exposed a blocked reason catalog and a primary operator action. The next
smallest safe slice is deriving an ordered per-blocker detail list from that
catalog and the existing blocked reason source buckets.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `backend/app/services/swapmod_scheduler_handoff_diagnostics.py`
- `backend/app/api/routes/swapmod_state_machine.py`
- `backend/tests/unit/services/test_swapmod_scheduler_handoff_diagnostics.py`
- `backend/tests/integration/test_swapmod_scheduler_handoff_diagnostics_api.py`
- `backend/tests/unit/test_swapmod_scheduler_handoff_diagnostics_architecture.py`

## In scope

- Add additive `diagnostics_summary.blocked_reason_details` entries derived from
  existing `blocked_reasons`, `blocked_reason_sources`, and the WP-090 catalog.
- Preserve existing primary blocker and primary operator action behavior.
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

The existing `diagnostics_summary` object gains additive field:

- `blocked_reason_details`

Each detail contains:

- `reason`
- `sources`
- `operator_action`
- `operator_action_source`

The existing status response adds `blocked_reason_details` to
`supported_summary_fields` through the existing `_diagnostics_summary()` contract
reflection test.

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-swapmod-scheduler-handoff-diagnostics-blocker-details` verifies the
focused no-network Makefile target exists and that mock services do not expose
blocker-details command, G-code, dispatch, printer-command, or bed-action routes.

## Validation commands

- `make test-swapmod-scheduler-handoff-diagnostics-blocker-details`
- `make test-swapmod-scheduler-handoff-diagnostics-reason-catalog`
- `make test-swapmod-scheduler-handoff-diagnostics-status-contract`
- `make test-swapmod-scheduler-handoff-diagnostics-explainability`
- `make test-swapmod-scheduler-handoff-diagnostics-status`
- `make test-swapmod-scheduler-handoff-diagnostics-auth`
- `make test-swapmod-scheduler-handoff-diagnostics-api`
- `make test-swapmod-scheduler-handoff-diagnostics`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-091_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_BLOCKER_DETAILS.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

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
- `make verify-fast` passed: harness 109 tests in contract/unit phases and 2
  characterization tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-091_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_BLOCKER_DETAILS.md`
  passed.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`. This is the
  Bambuddy still starts statement for this read-only slice.

## Manual demonstration

No physical printer test is required for WP-091. This slice is a no-network,
read-only contract addition and never calls printer, FTP, MQTT, scheduler
dispatch, queue mutation, or bed-actuator boundaries.

## Migration and rollback

No migration is added. Rollback is removing the additive summary field, focused
Makefile target, harness check, tests, and workpack. Runtime scheduler behavior
remains controlled by existing default-off gates.

## Logs and metrics

No new logs or metrics are added. The read-only diagnostics response exposes the
per-blocker detail ledger needed to diagnose why a scheduler handoff is blocked.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused blocker-details target passes.
- The ready path reports an empty `blocked_reason_details` list.
- Missing latest print logs, consumed queue readiness bindings, and handoff
  identity mismatch report ordered source-qualified blocker details.
- Existing primary blocker/action behavior is unchanged.
- Adjacent reason-catalog/status-contract/explainability/status/auth/API targets,
  `verify-fast`, workpack check, diff check, and app-import smoke pass.
