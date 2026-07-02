# WP-104 Physical Acceptance Evidence Validator

## Observable outcome

A deterministic, local validator checks a redacted WP-103 physical acceptance
evidence record and reports whether it proves `READY_FOR_NEXT_PRINT` or must stay
`MANUAL_REVIEW`. The validator is a harness/documentation tool only.

No physical printer action is executed by this validator, this PR, CI, or the
focused test target.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `workpacks/exec/WP-103_PHYSICAL_ACCEPTANCE_CANARY.md`
- `docs/runbooks/WP104_PHYSICAL_ACCEPTANCE_EVIDENCE_VALIDATOR.md`
- `docs/releases/WP104_PHYSICAL_ACCEPTANCE_EVIDENCE_VALIDATION.md`
- `harness/scripts/physical_acceptance_evidence_validator.py`
- `harness/tests/test_physical_acceptance_evidence_validator.py`
- `Makefile`

## In scope

- Add `harness/scripts/physical_acceptance_evidence_validator.py`.
- Add focused tests for complete evidence, missing fields, false verification,
  WP-103 canary-key provenance, unexpected evidence keys, unredacted or
  partially redacted sensitive fields, enabled real-command flags,
  READY-state safety failures, and CLI failure output.
- Add `make test-physical-acceptance-evidence-validator`.
- Add a WP-104 runbook and validation ledger.

## Out of scope

- No runtime endpoint is added.
- No UI change is added.
- No database migration is added.
- No new production dependency is added.
- No printer, MQTT, FTPS, slicer, ERP, Obico, PrintFlow, actuator, scheduler,
  queue dispatch, or G-code path is added.
- No automatic resume or retry of an uncertain physical bed action is added.

## Done when

- `make test-physical-acceptance-evidence-validator` passes.
- `make verify-fast` passes.
- `git diff --check` passes.
- Placeholder scan finds no unresolved markers in WP-104 documents.
- Docker app import smoke proves Bambuddy still starts.

## Contract changes

No service contract changes are introduced. Contract changes are limited to a
new local harness command and operator-facing documents:

- `python3 harness/scripts/physical_acceptance_evidence_validator.py`
- `make test-physical-acceptance-evidence-validator`
- `docs/runbooks/WP104_PHYSICAL_ACCEPTANCE_EVIDENCE_VALIDATOR.md`
- `docs/releases/WP104_PHYSICAL_ACCEPTANCE_EVIDENCE_VALIDATION.md`

## Feature flags

The validator has no runtime feature flag because it is not a runtime feature.
It still requires the physical canary flags to be default-off in valid evidence:

```dotenv
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
```

## Failure paths

The validator returns `MANUAL_REVIEW` when evidence is missing required fields,
contains false safety gates, contains an unredacted or non-allowlisted sensitive
field, uses a non-WP-103 canary key, contains unexpected keys, contains bad
sequence hashes, fails release/load verification, lacks rollback confirmation,
or leaves real-command flags enabled.

## Migration and rollback

Migration: none. Rollback is file-level: remove the WP-104 validator script,
harness test, Makefile target, runbook, evidence ledger, and workpack.
Runtime behavior remains unchanged.

## Logs and metrics

No runtime log or metric is emitted. Operator evidence for a later physical run
must preserve validator stdout, exit code, timestamp, redacted evidence file
reference, and operator initials.

## Validation evidence

Initial RED evidence:

- `python3 -m unittest harness.tests.test_physical_acceptance_evidence_validator`
  failed because the Makefile target, validator script, and WP-104 documents did
  not exist.

GREEN evidence:

- `make test-physical-acceptance-evidence-validator COMPOSE_PROJECT_NAME=farm_wp030`
  passed with 13 WP-104 harness tests and a passing workpack check.
- `make verify-fast COMPOSE_PROJECT_NAME=farm_wp030` passed with 153 harness
  tests, 2 characterization tests, and `Fast deterministic gate passed.`
- `git diff --check` passed.
- Placeholder scan passed with no unresolved markers in the WP-104 documents.
- Docker app import smoke printed `bambuddy_app_import_ok True` using
  `farm_wp030-bambuddy:latest` with `--network none`.

## Bambuddy startup statement

Bambuddy still starts. WP-104 does not modify backend startup, frontend startup,
database schema, service configuration, or runtime endpoint behavior.
