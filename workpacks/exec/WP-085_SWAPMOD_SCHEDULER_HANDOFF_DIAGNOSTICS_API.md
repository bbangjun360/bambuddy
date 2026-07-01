# WP-085 SwapMod Scheduler Handoff Diagnostics API

## ID and title

WP-085 SwapMod Scheduler Handoff Diagnostics API

## Observable outcome

Operators and tests can query the WP-084 SwapMod scheduler handoff diagnostics
through a read-only Bambuddy API endpoint without starting the print or
mutating queue, readiness binding, scheduler, printer, ERP, Obico, FTP, MQTT,
raw G-code, or physical bed state.

## Why now

WP-084 added the internal no-command diagnostic payload. The next smallest
safety slice is exposing that same payload through Bambuddy's existing
SwapMod API router so operators can inspect a blocked scheduler handoff through
the control plane before any future UI or scheduler automation work.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `backend/app/services/swapmod_scheduler_handoff_diagnostics.py`
- `backend/app/api/routes/swapmod_state_machine.py`
- `backend/tests/integration/test_swapmod_scheduler_handoff_diagnostics_api.py`

## In scope

- Add `GET /api/v1/swapmod-state-machine/scheduler-handoff-diagnostics`.
- Require only `PRINTERS_READ` when auth is enabled.
- Reuse the WP-084 diagnostic service and existing default-off scheduler gate
  settings.
- Add a safe-default API test where disabled gates return an allowed,
  unenforced, no-command diagnostic payload.
- Add a consumed-binding API failure-path test that returns
  `queue_readiness_binding_consumed` without mutating queue or binding state.
- Add harness and architecture checks proving the endpoint remains read-only
  and the focused target runs with Docker `--network none`.

## Out of scope

- Scheduler `_start_print` behavior changes.
- New database schema, UI, external service contract, or public command surface.
- Queue binding creation through this endpoint.
- Any printer command, FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or
  physical bed call.
- Enabling feature flags by default.
- Auto-resume of uncertain physical bed actions after restart.

## Contract changes

Adds one read-only API contract:

- `GET /api/v1/swapmod-state-machine/scheduler-handoff-diagnostics`
- Query parameters:
  - `queue_item_id`
  - `printer_id`
- Returns the WP-084 payload with `mode=SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS`,
  nested scheduler gate payloads, blocked reasons, and no-command sentinels.

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-swapmod-scheduler-handoff-diagnostics-api` verifies the Makefile
exposes the focused no-network API target and that mock services still do not
provide scheduler handoff diagnostics command, dispatch, printer, or G-code
routes.

## Validation commands

- `make test-swapmod-scheduler-handoff-diagnostics-api`
- `make test-swapmod-scheduler-handoff-diagnostics`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-085_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_API.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

- `make test-swapmod-scheduler-handoff-diagnostics-api` passed: harness 2
  tests, backend 7 tests.
- `make test-swapmod-scheduler-handoff-diagnostics` passed: harness 2 tests,
  backend 7 tests.
- `make verify-fast` passed: harness 97 tests in contract/unit phases and 2
  characterization tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-085_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_API.md`
  passed.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`.

## Manual demonstration

No physical printer test is required for WP-085. This slice is a no-network,
read-only API validation over existing Bambuddy database state and never calls
printer, FTP, MQTT, scheduler dispatch, or bed-actuator boundaries.

## Migration and rollback

No migration is added. Rollback is removing the read-only endpoint, tests,
Makefile target, and workpack. Runtime scheduler behavior remains controlled by
existing default-off gates.

## Logs and metrics

No new logs or metrics are added. The diagnostic API returns existing blocked
reason strings and explicit no-command sentinels for troubleshooting.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused API diagnostics target passes.
- Disabled gates return an allowed, unenforced, no-command API payload.
- Consumed-binding diagnostics return `queue_readiness_binding_consumed` without
  queue or binding mutation.
- WP-084 diagnostics target, `verify-fast`, workpack check, diff check, and
  app-import smoke pass.
