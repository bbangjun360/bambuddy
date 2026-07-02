# WP-106 Physical Acceptance Validator Metadata Hardening

## Observable outcome

The local WP-104 physical acceptance evidence validator rejects ambiguous
metadata before a redacted operator evidence file can prove
`READY_FOR_NEXT_PRINT`. It requires strict UTC ISO-8601 seconds ending in Z for
`timestamp_utc` and rejects duplicate canary_key records in the same evidence
file.

No physical printer action is executed by this validator metadata hardening,
this PR, CI, or the focused test target.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `workpacks/exec/WP-105_PHYSICAL_ACCEPTANCE_EVIDENCE_TEMPLATE.md`
- `docs/runbooks/WP106_PHYSICAL_ACCEPTANCE_VALIDATOR_METADATA_HARDENING.md`
- `docs/releases/WP106_PHYSICAL_ACCEPTANCE_VALIDATOR_METADATA_HARDENING.md`
- `harness/scripts/physical_acceptance_evidence_validator.py`
- `harness/tests/test_physical_acceptance_evidence_validator.py`
- `Makefile`

## In scope

- Harden `timestamp_utc` validation in the local WP-104 validator.
- Reject duplicate canary_key records in one evidence file.
- Preserve existing valid `READY_FOR_NEXT_PRINT` evidence behavior.
- Add focused tests for malformed timestamps, impossible dates, newline
  injection, duplicate canary keys, Makefile exposure, and WP-106 documents.
- Add `make test-physical-acceptance-validator-metadata-hardening`.
- Add a WP-106 runbook and validation ledger.

## Out of scope

- No runtime endpoint is added.
- No UI change is added.
- No database migration is added.
- No new production dependency is added.
- No printer, MQTT, FTPS, slicer, ERP, Obico, PrintFlow, actuator, scheduler,
  queue dispatch, or G-code path is added.
- No automatic resume or retry of an uncertain physical bed action is added.
- No physical evidence is generated, validated, modified, or appended.

## Done when

- `make test-physical-acceptance-validator-metadata-hardening` passes.
- `make verify-fast` passes.
- `git diff --check` passes.
- Placeholder scan finds no unresolved markers in WP-106 documents.
- Docker app import smoke proves Bambuddy still starts.

## Contract changes

No service contract changes are introduced. Contract changes are limited to a
local harness validator behavior and operator-facing documents:

- `python3 harness/scripts/physical_acceptance_evidence_validator.py`
- `make test-physical-acceptance-validator-metadata-hardening`
- `docs/runbooks/WP106_PHYSICAL_ACCEPTANCE_VALIDATOR_METADATA_HARDENING.md`
- `docs/releases/WP106_PHYSICAL_ACCEPTANCE_VALIDATOR_METADATA_HARDENING.md`

The local validator now reports `MANUAL_REVIEW` for malformed `timestamp_utc`
metadata and duplicate canary_key records.

## Feature flags

The validator has no runtime feature flag because it is not a runtime feature.
It still requires the physical canary flags to be default-off in valid evidence:

```dotenv
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
```

## Failure paths

The validator returns `MANUAL_REVIEW` when evidence has malformed or ambiguous
`timestamp_utc`, duplicate canary_key records, missing required fields, false
safety gates, unredacted or non-allowlisted sensitive fields, unexpected keys,
bad sequence hashes, failed release/load verification, missing rollback
confirmation, non-ready final state, or enabled real-command flags.

## Migration and rollback

Migration: none. Rollback is file-level: restore the WP-104 validator metadata
checks, remove the WP-106 test additions, Makefile target, runbook, release
ledger, and workpack. Runtime behavior remains unchanged.

## Logs and metrics

No runtime log or metric is emitted. Operator evidence for a later physical run
must preserve validator stdout, exit code, timestamp, redacted evidence file
reference, and operator initials. Duplicate-key or timestamp failures must stay
in the validator output.

## Validation evidence

Initial RED evidence:

- `python3 -m unittest harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_validator_rejects_ambiguous_or_malformed_timestamps harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_validator_cli_rejects_duplicate_canary_key_records`
  failed because malformed timestamps were accepted or reported with the old
  loose reason, and duplicate canary-key records both returned
  `READY_FOR_NEXT_PRINT`.
- `python3 -m unittest harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_makefile_exposes_physical_acceptance_validator_metadata_hardening_target harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_wp106_documents_define_metadata_hardening_scope harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_physical_acceptance_validator_documents_do_not_contain_placeholders`
  failed because the WP-106 Makefile target and documents did not exist.

GREEN evidence:

- `python3 -m unittest harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_validator_rejects_ambiguous_or_malformed_timestamps harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_validator_cli_rejects_duplicate_canary_key_records`
  passed with 2 metadata hardening tests.
- `make test-physical-acceptance-validator-metadata-hardening COMPOSE_PROJECT_NAME=farm_wp030`
  passed with 18 validator harness tests and a passing workpack check.
- Review-driven RED case: `python3 -m unittest harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_validator_rejects_ambiguous_or_malformed_timestamps`
  failed for leading whitespace, trailing whitespace, and boundary newline
  timestamp values before the raw timestamp fix.
- Review-driven CLI RED case: `python3 -m unittest harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_validator_cli_rejects_timestamp_with_trailing_file_whitespace`
  failed before `parse_records` preserved raw `timestamp_utc` values from evidence files.
- After the raw timestamp fix, `python3 -m unittest harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_validator_rejects_ambiguous_or_malformed_timestamps harness.tests.test_physical_acceptance_evidence_validator.PhysicalAcceptanceEvidenceValidatorHarnessTest.test_validator_cli_rejects_duplicate_canary_key_records`
  passed with 2 metadata hardening tests.
- `make verify-fast COMPOSE_PROJECT_NAME=farm_wp030` passed with 167 harness
  tests, 2 characterization tests, and `Fast deterministic gate passed.`
- `git diff --check` passed.
- Placeholder scan passed with no unresolved markers in the WP-106 documents.
- Docker app import smoke printed `bambuddy_app_import_ok True` using
  `farm_wp030-bambuddy:latest` with `--network none`.

## Bambuddy startup statement

Bambuddy still starts. WP-106 does not modify backend startup, frontend startup,
database schema, service configuration, or runtime endpoint behavior.
