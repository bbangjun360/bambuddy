# WP-104 Physical Acceptance Evidence Validator

This runbook defines the human-gated evidence validator for the
`farm-v0.1.0-acceptance` physical acceptance packet at commit
`9190b2fc6ac1e111234ad73d8d73e2a487d81be5`.

No physical printer action is executed by this validator. It reads a local
operator evidence record, checks required fields, and returns either
`READY_FOR_NEXT_PRINT` or `MANUAL_REVIEW`.

## Authority and Limits

Bambuddy remains the sole authority for printer state-changing commands. The
validator does not call Bambuddy runtime APIs, Bambu MQTT, FTPS, slicer APIs,
ERP, Obico, PrintFlow, shell actuator commands, or G-code paths.

Evidence validation is not physical safety evidence. It only checks whether a
human-recorded evidence row is complete enough for review after a supervised A1
Mini acceptance attempt.

Never automatically resume an uncertain physical bed action after restart.
Uncertain state remains `MANUAL_REVIEW`.

## Required Command

Run the validator against a single key=value evidence file:

```bash
python3 harness/scripts/physical_acceptance_evidence_validator.py /path/to/redacted-evidence.env
```

The command exits `0` only when the record proves `READY_FOR_NEXT_PRINT`. It exits
`1` and prints reasons when the record must remain `MANUAL_REVIEW`.

## Required Evidence Fields

The evidence record must include release identity, operator safety gates, sequence
hashes, post-action verification, rollback flags, and redacted audit references.

Required booleans that must be true:

```text
operator_present=true
printer_visible=true
emergency_stop_ready=true
power_cutoff_ready=true
a1_mini_confirmed=true
swapmod_hardware_installed=true
bed_area_clear=true
plate_stack_ready=true
no_other_job_running=true
dry_run_gate_reviewed=true
release_verified=true
loaded_verified=true
rollback_confirmed=true
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
```

Required default-off flags:

```dotenv
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
```

Required WP-103 provenance, state, and release values:

```text
canary_key=wp103-physical-acceptance-YYYYMMDD-N
release_tag=farm-v0.1.0-acceptance
release_commit=9190b2fc6ac1e111234ad73d8d73e2a487d81be5
final_state=READY_FOR_NEXT_PRINT
```

Required exact redaction values:

```text
printer_id_redacted=A1_MINI_CANARY_REDACTED
operator_initials=REDACTED_OPERATOR
log_bundle_ref=REDACTED_LOG_BUNDLE
```

Both `release_sequence_sha256` and `load_sequence_sha256` must be lowercase
64-character SHA-256 hex digests.

## Failure Handling

Any missing required field, false safety gate, unredacted or non-allowlisted
sensitive field, unexpected evidence key, bad sequence hash, enabled
real-command flag, missing rollback confirmation, or non-ready final state
returns `MANUAL_REVIEW`. Partially redacted sensitive fields also fail.
No additional evidence keys are accepted.

A `READY_FOR_NEXT_PRINT` validator result does not dispatch the next print. It is
only evidence that a human can review before any separately gated queue decision.
