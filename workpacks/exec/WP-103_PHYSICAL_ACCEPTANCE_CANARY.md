# WP-103 Physical Acceptance Canary

## Observable outcome

The accepted release tag `farm-v0.1.0-acceptance` has a human-gated physical
acceptance canary packet that can be reviewed and tested without moving hardware.
The packet ties the release commit `9190b2fc6ac1e111234ad73d8d73e2a487d81be5`,
manual Security Audit run `28562025959`, and post-tag Security Audit run
`28562152131` to a supervised A1 Mini acceptance runbook and evidence ledger.

No physical printer action is executed by this PR. CI, `verify-fast`, and
`make test-physical-acceptance-canary` validate only the documentation and safety
contract.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `workpacks/exec/WP-076_SWAPMOD_A1_MINI_DIRECT_CANARY.md`
- `docs/runbooks/WP103_PHYSICAL_ACCEPTANCE_CANARY.md`
- `docs/releases/WP103_PHYSICAL_ACCEPTANCE_EVIDENCE.md`
- `harness/tests/test_physical_acceptance_canary.py`
- `Makefile`

## In scope

- Add a WP-103 runbook for supervised physical acceptance of
  `farm-v0.1.0-acceptance`.
- Add a WP-103 evidence ledger that records release gates and the current
  no-new-physical-run status.
- Add a focused harness test and Makefile target:
  `make test-physical-acceptance-canary`.
- Capture required safety gates, confirmation phrases, rollback behavior, and
  evidence fields for later manual execution.

## Out of scope

- No runtime endpoint is added.
- No UI change is added.
- No database migration is added.
- No new production dependency is added.
- No queue, scheduler, ERP, Obico, slicer, MQTT, FTPS, actuator, or raw G-code
  command path is added.
- No automatic resume or retry of an uncertain bed action is added.
- No physical printer action is executed by this PR.

## Done when

- `make test-physical-acceptance-canary` passes.
- `make verify-fast` passes.
- `git diff --check` passes.
- The WP-103 evidence ledger records the release tag, release commit, audit run
  IDs, default-off flags, required physical evidence fields, and current
  no-new-physical-run state.
- The PR description states that Bambuddy still starts and that WP-103 does not
  execute hardware commands.

## Contract changes

No service contract changes are introduced. The only new contract is the
operator-facing acceptance packet:

- `docs/runbooks/WP103_PHYSICAL_ACCEPTANCE_CANARY.md`
- `docs/releases/WP103_PHYSICAL_ACCEPTANCE_EVIDENCE.md`
- `make test-physical-acceptance-canary`

The canary reuses the WP-076 confirmation phrase
`CONFIRM_A1_MINI_DIRECT_PLATE_CHANGE` and adds the WP-103 acceptance phrase
`CONFIRM_WP103_PHYSICAL_ACCEPTANCE_CANARY`.

## Feature flags

The physical canary remains disabled by default:

```dotenv
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
```

## Failure paths

The runbook forces `MANUAL_REVIEW` when operator visibility, emergency stop,
power cutoff, bed clearance, plate stack readiness, sequence hashes, Bambuddy
state, or restart safety cannot be proven. It also states that uncertain
physical bed actions are never automatically resumed after restart.

## Migration and rollback

Migration: none. Rollback is document-only and target-only: remove the WP-103
documents, harness test, and Makefile target. Runtime behavior remains unchanged.

Operational rollback after a supervised attempt means restoring:

```dotenv
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
```

## Logs and metrics

WP-103 requires any later physical acceptance attempt to record canary key,
redacted printer ID, release and load sequence hashes, operator checklist values,
final state, rollback confirmation, timestamp, operator initials, and redacted
log bundle reference. No new runtime metric is emitted by this PR.

## Validation evidence

Initial RED evidence:

- `python3 -m unittest harness.tests.test_physical_acceptance_canary` failed
  because the Makefile target and WP-103 documents did not exist.

GREEN evidence:

- `make test-physical-acceptance-canary COMPOSE_PROJECT_NAME=farm_wp030`
  passed with 6 WP-103 harness tests and a passing workpack check.
- `make verify-fast COMPOSE_PROJECT_NAME=farm_wp030` passed with 140 harness
  tests, 2 characterization tests, and `Fast deterministic gate passed.`
- `git diff --check` passed.
- Placeholder scan passed with no unresolved markers in the WP-103 documents.
- Docker app import smoke printed `bambuddy_app_import_ok True` using
  `farm_wp030-bambuddy:latest` with `--network none`.

## Bambuddy startup statement

Bambuddy still starts. WP-103 does not modify backend startup, frontend startup,
database schema, service configuration, or runtime endpoint behavior.
