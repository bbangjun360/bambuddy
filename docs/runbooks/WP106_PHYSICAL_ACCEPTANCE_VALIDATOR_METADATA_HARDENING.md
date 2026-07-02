# WP-106 Physical Acceptance Validator Metadata Hardening

This runbook defines the metadata hardening added to the local WP-104 physical
acceptance evidence validator. No physical printer action is executed by this
validator metadata hardening. It only tightens local parsing and review output
for redacted operator evidence records.

## Authority and Limits

Bambuddy remains the sole authority for printer state-changing commands. The
validator does not call Bambuddy runtime APIs, Bambu MQTT, FTPS, slicer APIs,
ERP, Obico, PrintFlow, shell actuator commands, scheduler paths, queue dispatch,
or G-code paths.

Evidence validation is not physical safety evidence. It only reports whether a
human-recorded evidence row is complete enough for review after a supervised A1
Mini acceptance attempt. A `READY_FOR_NEXT_PRINT` validator result does not
start the next print.

Never automatically resume an uncertain physical bed action after restart.
Uncertain state remains `MANUAL_REVIEW`.

## Hardened Metadata Rules

The validator now requires `timestamp_utc` to be strict UTC ISO-8601 seconds
ending in Z:

```text
2026-07-02T03:45:00Z
```

The validator rejects ambiguous or malformed values such as free text, missing
`Z`, local offsets, spaces instead of `T`, impossible dates, fractional seconds,
and newline injection.

The validator also rejects duplicate canary_key records inside the same
evidence file. A repeated key keeps the later record in `MANUAL_REVIEW` even if
all other fields are valid.

## Required Command

Run the validator against a redacted evidence file:

```bash
python3 harness/scripts/physical_acceptance_evidence_validator.py /path/to/redacted-evidence.env
```

Run the WP-106 focused harness gate:

```bash
make test-physical-acceptance-validator-metadata-hardening COMPOSE_PROJECT_NAME=farm_wp030
```

## Failure Handling

Any malformed timestamp, duplicate canary key, missing required field, false
safety gate, unredacted or non-allowlisted sensitive field, unexpected evidence
key, bad sequence hash, enabled real-command flag, missing rollback
confirmation, or non-ready final state returns `MANUAL_REVIEW`.

No runtime endpoint is added. No physical evidence is generated, modified, or
appended by this hardening.
