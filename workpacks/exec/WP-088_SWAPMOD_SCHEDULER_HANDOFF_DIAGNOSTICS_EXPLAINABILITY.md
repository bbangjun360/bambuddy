# WP-088 SwapMod Scheduler Handoff Diagnostics Explainability

## ID and title

WP-088 SwapMod Scheduler Handoff Diagnostics Explainability

## Observable outcome

The existing read-only SwapMod scheduler handoff diagnostics evaluation response
includes an additive `diagnostics_summary` object. Operators and future UI/API
consumers can identify the primary blocker, reason source groups, enforced gates,
and handoff identity status without following nested gate payloads. No printer,
scheduler dispatch, queue mutation, FTP, MQTT, raw G-code, ERP, Obico, slicer,
actuator, or physical bed boundary is touched.

## Why now

WP-085 through WP-087 exposed the diagnostics API, status endpoint, and auth
contract. The next smallest useful slice is improving the read-only explanation
contract before any operator workflow or command-bearing automation is added.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `backend/app/services/swapmod_scheduler_handoff_diagnostics.py`
- `backend/tests/unit/services/test_swapmod_scheduler_handoff_diagnostics.py`
- `backend/tests/integration/test_swapmod_scheduler_handoff_diagnostics_api.py`
- `backend/tests/unit/test_swapmod_scheduler_handoff_diagnostics_architecture.py`

## In scope

- Add `diagnostics_summary` to the existing diagnostics evaluation response.
- Summarize primary blocker, blocked reason source groups, enforced gates, and
  handoff identity status.
- Preserve existing nested gate payloads and no-command sentinels.
- Add unit, API, architecture, harness, and Makefile coverage for the summary.

## Out of scope

- New endpoints or route permission changes.
- Scheduler `_start_print` behavior changes.
- Queue binding creation, consumption, or dispatch changes.
- New database schema, UI, external service contract, or public command surface.
- Any printer command, FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or
  physical bed call.
- Enabling feature flags by default.

## Contract changes

The existing `GET /api/v1/swapmod-state-machine/scheduler-handoff-diagnostics`
response gains an additive `diagnostics_summary` object with:

- `contract_version`
- `gate_status`
- `scheduler_start_allowed`
- `primary_blocker`
- `blocked_reason_count`
- `blocked_reason_sources.scheduler_next_print_gate`
- `blocked_reason_sources.scheduler_queue_readiness_binding_gate`
- `blocked_reason_sources.handoff_identity`
- `enforced_gates`
- `handoff_identity_status`
- `read_only`
- `real_command_sent`
- `printer_command_sent`
- `scheduler_dispatch_supported`

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-swapmod-scheduler-handoff-diagnostics-explainability` verifies the
focused no-network Makefile target exists and that mock services do not expose
explainability command, G-code, dispatch, printer-command, or bed-action routes.

## Validation commands

- `make test-swapmod-scheduler-handoff-diagnostics-explainability`
- `make test-swapmod-scheduler-handoff-diagnostics-auth`
- `make test-swapmod-scheduler-handoff-diagnostics-status`
- `make test-swapmod-scheduler-handoff-diagnostics-api`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-088_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_EXPLAINABILITY.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

- `make test-swapmod-scheduler-handoff-diagnostics-explainability` passed:
  harness 2 tests, backend 19 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-auth` passed: harness 2
  tests, backend 15 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-status` passed: harness 2
  tests, backend 15 tests.
- `make test-swapmod-scheduler-handoff-diagnostics-api` passed: harness 2
  tests, backend 15 tests.
- `make verify-fast` passed: harness 103 tests in contract/unit phases and 2
  characterization tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-088_SWAPMOD_SCHEDULER_HANDOFF_DIAGNOSTICS_EXPLAINABILITY.md`
  passed.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`.

## Manual demonstration

No physical printer test is required for WP-088. This slice is a no-network,
read-only response explainability contract and never calls printer, FTP, MQTT,
scheduler dispatch, queue mutation, or bed-actuator boundaries.

## Migration and rollback

No migration is added. Rollback is removing the additive summary field, focused
Makefile target, harness check, tests, and workpack. Runtime scheduler behavior
remains controlled by existing default-off gates.

## Logs and metrics

No new logs or metrics are added. The response now includes structured summary
fields that identify reason sources while retaining existing nested diagnostic
payloads and no-command sentinels.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused diagnostics explainability target passes.
- Ready, consumed-binding, and handoff-identity-mismatch diagnostics include the
  expected summary.
- API responses include the summary and existing no-command sentinels.
- Adjacent auth/status/API targets, `verify-fast`, workpack check, diff check,
  and app-import smoke pass.
