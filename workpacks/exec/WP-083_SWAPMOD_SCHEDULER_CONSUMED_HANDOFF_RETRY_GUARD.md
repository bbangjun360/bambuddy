# WP-083 SwapMod Scheduler Consumed Handoff Retry Guard

## ID and title

WP-083 SwapMod Scheduler Consumed Handoff Retry Guard

## Observable outcome

After Bambuddy scheduler accepts a READY SwapMod handoff and consumes the exact
queue-readiness binding, a watchdog rollback from `printing` back to `pending`
does not allow the same consumed handoff to be retried. The second scheduler
start attempt blocks before FTP settings, upload/delete, queue status mutation,
bed-clear mutation, or printer start with `queue_readiness_binding_consumed`.

## Why now

WP-082 proves scheduler start only proceeds when the latest-print gate and
queue-readiness binding describe the same SwapMod handoff chain. The immediate
remaining retry safety question is what happens when the existing watchdog
returns a started item to `pending`. WP-083 proves the already-consumed binding
prevents an unsafe automatic reuse of the same handoff evidence.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `workpacks/exec/WP-082_SWAPMOD_SCHEDULER_HANDOFF_CHAIN.md`
- `backend/app/services/print_scheduler.py`
- `backend/app/services/swapmod_scheduler_queue_readiness_binding.py`
- `backend/tests/unit/test_scheduler_watchdog.py`
- `backend/tests/unit/services/test_swapmod_scheduler_consumed_handoff_retry.py`

## In scope

- Add `test-swapmod-scheduler-consumed-handoff-retry` and matching harness target.
- Add a no-network scheduler composition test where the first mocked `_start_print`
  consumes a READY queue-readiness binding.
- Invoke the existing scheduler watchdog rollback path so the same queue item
  returns from `printing` to `pending`.
- Prove the second mocked `_start_print` blocks before FTP settings, upload,
  queue status mutation, bed-clear mutation, or printer start because the binding
  is already consumed.
- Add architecture and harness assertions documenting the consumed-binding gate
  and absence of mock dispatch, printer command, or raw G-code routes.

## Out of scope

- Production code changes unless the composition test fails.
- New database schema, UI, API routes, or external service contracts.
- Automatic queue binding creation or background dispatch.
- Physical printer, MQTT, FTPS, raw G-code, actuator, ERP, Obico, or slicer calls.
- Enabling feature flags by default.
- Auto-resume of uncertain physical bed actions after restart.

## Contract changes

No production contract changes. WP-083 validates existing default-off behavior:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

Existing blocked reason reused by this slice:

- `queue_readiness_binding_consumed`

## Harness first

`harness-swapmod-scheduler-consumed-handoff-retry` verifies the Makefile exposes
the focused no-network target and that mock services still do not provide retry
dispatch, printer command, or arbitrary G-code control surfaces.

## Validation commands

- `make test-swapmod-scheduler-consumed-handoff-retry`
- `make test-swapmod-scheduler-handoff-chain`
- `make test-swapmod-scheduler-queue-readiness-binding`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-083_SWAPMOD_SCHEDULER_CONSUMED_HANDOFF_RETRY_GUARD.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

- `make test-swapmod-scheduler-consumed-handoff-retry` passed: harness 2 tests, backend 2 tests.
- `make test-swapmod-scheduler-handoff-chain` passed: harness 2 tests, backend 3 tests.
- `make test-swapmod-scheduler-queue-readiness-binding` passed: harness 2 tests, backend 19 tests.
- `make verify-fast` passed: harness 93 tests, characterization 2 tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-083_SWAPMOD_SCHEDULER_CONSUMED_HANDOFF_RETRY_GUARD.md` passed.
- `git diff --check` passed.
- No-network app import smoke passed: `bambuddy_app_import_ok True`.

## Manual demonstration

No physical printer test is required for WP-083. This slice is a no-network
scheduler retry composition validation that mocks only existing Bambuddy external
boundaries. Physical canary testing remains a later human-gated step.

## Migration and rollback

No migration is added. Rollback is removing the WP-083 tests and target. Runtime
behavior remains controlled by the existing default-off flags and existing
consumed-binding scheduler gate.

## Logs and metrics

The failure-path test asserts the existing scheduler warning includes
`queue_readiness_binding_consumed`. No new log or metric contract is added.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval.

## Done when

- The focused consumed-handoff retry target passes.
- The first mocked start consumes the binding after the mocked Bambuddy start
  command succeeds.
- The watchdog rollback returns the queue item to `pending`.
- The second start attempt blocks before FTP settings, upload/delete, status
  mutation, `awaiting_plate_clear` clearing, or printer start.
- Adjacent WP-081/WP-082 tests, `verify-fast`, workpack check, diff check, and
  app-import smoke pass.
