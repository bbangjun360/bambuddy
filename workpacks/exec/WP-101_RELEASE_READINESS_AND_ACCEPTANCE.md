# WP-101 Release Readiness And Acceptance

## ID and title

WP-101 Release Readiness And Acceptance

## Observable outcome

The repository gains a deterministic release readiness acceptance target and
operator-facing release documents for the WP-000 through WP-100 farm candidate.
The acceptance slice does not enable printer, scheduler dispatch, queue
mutation, FTP, MQTT, raw G-code, ERP, Obico, slicer, actuator, or physical bed
behavior.

## Why now

WP-100 completed the current diagnostics contract hardening sequence. The next
smallest safe slice is to define how the project decides whether that candidate
is acceptable for release, including CI evidence, contract evidence, default-off
feature flags, hardware canary conditions, rollback, and post-release
monitoring.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `docs/runbooks/RELEASE_READINESS_ACCEPTANCE.md`
- `docs/releases/WP101_RELEASE_NOTES_DRAFT.md`
- `harness/tests/test_release_readiness_acceptance.py`

## In scope

- Add `make test-release-readiness-acceptance`.
- Add harness coverage for release readiness acceptance documents.
- Add release readiness runbook.
- Add WP-101 release notes draft.
- Preserve WP-100 runtime behavior and default-off gates.

## Out of scope

- New runtime endpoints or service behavior.
- UI changes.
- Database migrations.
- Feature flag default changes.
- Release tag creation in this PR.
- Physical printer, bed, actuator, queue dispatch, scheduler dispatch, FTP,
  MQTT, raw G-code, ERP, Obico, or slicer execution.
- Hardware canary execution without a later canary Work Package and explicit
  operator approval.

## Contract changes

No API contract changes are added by WP-101. The new contract is a repository
validation target and release documentation contract:

- `make test-release-readiness-acceptance`
- `docs/runbooks/RELEASE_READINESS_ACCEPTANCE.md`
- `docs/releases/WP101_RELEASE_NOTES_DRAFT.md`

Existing default-off settings remain unchanged:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Harness first

`harness-release-readiness-acceptance` verifies that the focused Makefile target
exists, the release readiness runbook covers required code, CI, contract,
safety, hardware canary, tagging, rollback, and monitoring gates, and the
release notes draft identifies scope, candidate commit, validation evidence,
changed contracts, feature flags, rollback, hardware test position, and known
risks.

## Validation commands

- `make test-release-readiness-acceptance`
- `make verify-fast`
- `make verify-full`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-101_RELEASE_READINESS_AND_ACCEPTANCE.md`
- `git diff --check`
- Docker no-network Bambuddy app import smoke.

Evidence from this branch:

- RED check failed for the expected missing release readiness documents:
  release runbook, release notes draft, and WP-101 workpack were absent.
- GREEN focused target passed after adding the release readiness runbook,
  release notes draft, WP-101 workpack, and harness checks.
- `make verify-fast COMPOSE_PROJECT_NAME=farm_wp030` passed with 132 harness
  tests and 2 characterization tests after review feedback was applied.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-101_RELEASE_READINESS_AND_ACCEPTANCE.md`
  passed.
- `git diff --check` passed.
- Placeholder scan across the WP-101 release docs and workpack returned no
  matches.
- Docker no-network Bambuddy app import smoke passed with
  `bambuddy_app_import_ok True`.
- The first `make verify-full COMPOSE_PROJECT_NAME=farm_wp030` run failed at
  integration smoke because the local harness stack was not running. `make
  harness-up` also exposed that the ignored local `.env.harness` contained
  placeholder image digests. The harness was then started with already-present
  local `postgres:16.4-alpine` and `python:3.13-slim` image overrides.
- `make harness-health COMPOSE_PROJECT_NAME=farm_wp030` passed against
  `127.0.0.1:18130` and mock services on `127.0.0.1:19130`.
- `make verify-full COMPOSE_PROJECT_NAME=farm_wp030` passed after the harness
  precondition was satisfied.

## Manual demonstration

No physical printer test is required for WP-101. This slice is a documentation
and harness acceptance addition and never calls printer, FTP, MQTT, scheduler
dispatch, queue mutation, slicer, ERP, Obico, or bed-actuator boundaries.

## Migration and rollback

No migration is added. Rollback is removing the release readiness Makefile
target, harness check, release readiness runbook, release notes draft, and this
workpack. Runtime behavior remains controlled by existing default-off gates.

## Logs and metrics

No new logs or metrics are added. The runbook requires release operators to
record GitHub Actions `Validation`, GitHub Actions `Security Audit`, startup
smoke, diagnostics status checks, and post-release monitoring evidence.

## Risks and human gates

Simulation success is not physical safety evidence. Real printer execution
remains blocked behind named canary hardware, human checklist, and explicit
operator approval. A release tag must not be pushed until the accepted
`farm-main` merge commit has passed post-merge `Security Audit`.

## Done when

- The focused release readiness acceptance target passes.
- The release readiness runbook and release notes draft contain no placeholder
  markers.
- The release docs preserve default-off feature flags and physical safety gates.
- No runtime behavior, service endpoint, UI, database schema, or production
  dependency changes are introduced.
- `verify-fast`, workpack check, diff check, cached diff check, app-import smoke,
  PR checks, and post-merge security audit pass.
