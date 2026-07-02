# WP-104 Physical Acceptance Evidence Validator

## Validation Ledger

No physical evidence has been validated by WP-104 yet. The validator exists so a
later supervised A1 Mini physical acceptance record can be checked without
moving hardware.

Release under validation:

```text
release_tag=farm-v0.1.0-acceptance
release_commit=9190b2fc6ac1e111234ad73d8d73e2a487d81be5
```

## Current Result

```text
validator_run_record=wp104-validator-not-yet-run
final_state=MANUAL_REVIEW
reason=no supervised physical evidence row has been provided
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
```

## Required Validation Record

When a supervised evidence row is available, run:

```bash
python3 harness/scripts/physical_acceptance_evidence_validator.py /path/to/redacted-evidence.env
```

Append the command output, timestamp, operator initials, redacted evidence file
reference, and validator exit code to this ledger. No physical printer action is
executed by this validator.

## Safety Statement

Bambuddy remains the sole authority for printer state-changing commands.
Evidence validation is not physical safety evidence, and any failed validation
keeps the attempt in `MANUAL_REVIEW` until an operator performs a new review.
