# WP-105 Physical Acceptance Evidence Template

## Observable outcome

A deterministic, local template generator emits the exact WP-104 validator field
set for a future redacted WP-103 physical acceptance evidence record. The
generated skeleton starts in `MANUAL_REVIEW` and never claims physical safety.

No physical printer action is executed by this template generator, this PR, CI,
or the focused test target.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `workpacks/exec/WP-104_PHYSICAL_ACCEPTANCE_EVIDENCE_VALIDATOR.md`
- `docs/runbooks/WP105_PHYSICAL_ACCEPTANCE_EVIDENCE_TEMPLATE.md`
- `docs/releases/WP105_PHYSICAL_ACCEPTANCE_EVIDENCE_TEMPLATE.md`
- `harness/scripts/physical_acceptance_evidence_validator.py`
- `harness/scripts/physical_acceptance_evidence_template.py`
- `harness/tests/test_physical_acceptance_evidence_template.py`
- `Makefile`

## In scope

- Add `harness/scripts/physical_acceptance_evidence_template.py`.
- Add focused tests for Makefile exposure, document scope, exact WP-104 field
  compatibility, false-by-default human claims, validator completion path, CLI
  stdout/file output, bad canary key failure, and placeholder scan.
- Add `make test-physical-acceptance-evidence-template`.
- Add a WP-105 runbook and template ledger.

## Out of scope

- No runtime endpoint is added.
- No UI change is added.
- No database migration is added.
- No new production dependency is added.
- No printer, MQTT, FTPS, slicer, ERP, Obico, PrintFlow, actuator, scheduler,
  queue dispatch, or G-code path is added.
- No automatic resume or retry of an uncertain physical bed action is added.
- No physical evidence is generated, validated, or appended.

## Done when

- `make test-physical-acceptance-evidence-template` passes.
- `make verify-fast` passes.
- `git diff --check` passes.
- Placeholder scan finds no unresolved markers in WP-105 documents.
- Docker app import smoke proves Bambuddy still starts.

## Contract changes

No service contract changes are introduced. Contract changes are limited to a
new local harness command and operator-facing documents:

- `python3 harness/scripts/physical_acceptance_evidence_template.py`
- `make test-physical-acceptance-evidence-template`
- `docs/runbooks/WP105_PHYSICAL_ACCEPTANCE_EVIDENCE_TEMPLATE.md`
- `docs/releases/WP105_PHYSICAL_ACCEPTANCE_EVIDENCE_TEMPLATE.md`

## Feature flags

The template generator has no runtime feature flag because it is not a runtime
feature. It still emits the physical canary flags in default-safe values:

```dotenv
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
```

## Failure paths

The template generator exits non-zero when the requested WP-103 canary key is
malformed, the timestamp is malformed, or the output file cannot be written. The
generated skeleton remains `MANUAL_REVIEW` until a human completes and validates
the evidence.

## Migration and rollback

Migration: none. Rollback is file-level: remove the WP-105 template script,
harness test, Makefile target, runbook, template ledger, and workpack. Runtime
behavior remains unchanged.

## Logs and metrics

No runtime log or metric is emitted. Operator evidence for a later physical run
must preserve template stdout or output file path, validator stdout, exit code,
timestamp, redacted evidence file reference, and operator initials.

## Validation evidence

Initial RED evidence:

- `python3 -m unittest harness.tests.test_physical_acceptance_evidence_template`
  failed because the Makefile target, template script, and WP-105 documents did
  not exist.

GREEN evidence:

- `make test-physical-acceptance-evidence-template COMPOSE_PROJECT_NAME=farm_wp030`
  passed with 9 WP-105 harness tests and a passing workpack check.
- `make verify-fast COMPOSE_PROJECT_NAME=farm_wp030` passed with 162 harness
  tests, 2 characterization tests, and `Fast deterministic gate passed.`

## Bambuddy startup statement

Bambuddy still starts. WP-105 does not modify backend startup, frontend startup,
database schema, service configuration, or runtime endpoint behavior.
