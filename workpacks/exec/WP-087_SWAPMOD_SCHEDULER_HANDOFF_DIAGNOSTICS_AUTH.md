# WP-087 SwapMod Scheduler Handoff Diagnostics Auth Contract

## ID and title

WP-087 SwapMod Scheduler Handoff Diagnostics Auth Contract

## Observable outcome

When Bambuddy auth is enabled, the SwapMod scheduler handoff diagnostics status
and evaluation endpoints enforce the existing `PRINTERS_READ` permission. An
unauthenticated request is rejected, a read-status user can call both read-only
endpoints, and a user without `PRINTERS_READ` cannot call either diagnostics endpoint.
No printer, scheduler, queue mutation, FTP, MQTT, raw G-code, ERP, Obico,
slicer, actuator, or physical bed boundary is touched.

## Why now

WP-085 and WP-086 exposed read-only diagnostics endpoints. The next smallest
safety slice is verifying the runtime authorization contract, not just the route
source text, before adding any broader operator workflow around these endpoints.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `backend/tests/integration/test_swapmod_scheduler_handoff_diagnostics_api.py`
- `backend/app/api/routes/swapmod_state_machine.py`
- `backend/tests/unit/test_swapmod_scheduler_handoff_diagnostics_architecture.py`

## In scope

- Add auth-enabled integration tests for diagnostics status and evaluation.
- Assert no-token requests are rejected when auth is enabled.
- Assert a JWT user with only `PRINTERS_READ` can call both diagnostics endpoints.
- Assert a JWT user without `PRINTERS_READ` is rejected by both diagnostics endpoints.
- Add focused Makefile and harness targets for this auth contract.

## Out of scope

- New auth behavior or route permission changes unless the tests reveal a real
  contract gap.
- Scheduler `_start_print` behavior changes.
- Diagnostic evaluation behavior changes.
- New database schema, UI, external service contract, or public command surface.
- Queue binding creation or scheduler dispatch.
- Any printer command, FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or
  physical bed call.
- Enabling feature flags by default.

## Contract changes

No public API contract changes. WP-087 validates the existing route contract:

- `GET /api/v1/swapmod-state-machine/scheduler-handoff-diagnostics/status`
  requires `PRINTERS_READ` when auth is enabled.
- `GET /api/v1/swapmod-state-machine/scheduler-handoff-diagnostics` requires
  `PRINTERS_READ` when auth is enabled.

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-swapmod-scheduler-handoff-diagnostics-auth` verifies the Makefile
exposes the focused no-network auth target and that mock services still do not
provide auth-bypass, dispatch, printer, or G-code routes.

## Validation commands

- `make test-swapmod-scheduler-handoff-diagnostics-auth`
- `make test-swapmod-scheduler-handoff-diagnostics-status`
- `make test-swapmod-scheduler-handoff-diagnostics-api`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-087_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_AUTH.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

- `make test-swapmod-scheduler-handoff-diagnostics-auth` passed: harness 2
  tests, backend 15 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-status` passed: harness 2
  tests, backend 15 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-api` passed: harness 2
  tests, backend 15 tests.
- `make verify-fast` passed: harness 101 tests in contract/unit phases and 2
  characterization tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-087_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_AUTH.md`
  passed.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`.

## Manual demonstration

No physical printer test is required for WP-087. This slice is a no-network,
read-only authorization contract validation and never calls printer, FTP, MQTT,
scheduler dispatch, or bed-actuator boundaries.

## Migration and rollback

No migration is added. Rollback is removing the auth contract tests, Makefile
target, harness check, and workpack. Runtime scheduler behavior remains
controlled by existing default-off gates.

## Logs and metrics

No new logs or metrics are added. The tests assert existing HTTP authorization
status codes and explicit no-command sentinels in successful responses.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused diagnostics auth target passes.
- Auth-enabled no-token requests are rejected.
- A `PRINTERS_READ` token can read status and evaluation diagnostics.
- A token without `PRINTERS_READ` is rejected by both diagnostics endpoints.
- Adjacent status/API targets, `verify-fast`, workpack check, diff check, and
  app-import smoke pass.
