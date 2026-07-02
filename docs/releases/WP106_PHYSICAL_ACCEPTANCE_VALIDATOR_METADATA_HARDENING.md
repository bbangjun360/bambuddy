# WP-106 Physical Acceptance Validator Metadata Hardening

## Validation Ledger

No physical evidence has been validated by WP-106. The change hardens local
metadata validation for future redacted WP-103 physical acceptance records.

## Current Result

```text
validator_metadata_hardening_record=wp106-not-yet-used
final_state=MANUAL_REVIEW
reason=no supervised physical evidence row has been provided
strict_timestamp_required=true
duplicate_canary_key_records_allowed=false
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
executed by this validator metadata hardening.

## Safety Statement

Bambuddy remains the sole authority for printer state-changing commands.
Evidence validation is not physical safety evidence, and any failed validation
keeps the attempt in `MANUAL_REVIEW` until an operator performs a new review.
