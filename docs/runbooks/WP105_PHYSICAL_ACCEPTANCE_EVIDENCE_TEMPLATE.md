# WP-105 Physical Acceptance Evidence Template

This runbook defines the local evidence template generator for supervised
WP-103 physical acceptance records. No physical printer action is executed by
this template generator. It emits only the exact key set accepted by the WP-104
validator.

## Authority and Limits

Bambuddy remains the sole authority for printer state-changing commands. The
template generator does not call Bambuddy runtime APIs, Bambu MQTT, FTPS, slicer
APIs, ERP, Obico, PrintFlow, shell actuator commands, scheduler paths, queue
dispatch, or G-code paths.

Evidence template generation is not physical safety evidence. The generated
record starts in `MANUAL_REVIEW` and does not claim that any operator checklist,
release step, load step, rollback, or bed state has been verified.

Never automatically resume an uncertain physical bed action after restart.
Uncertain state remains `MANUAL_REVIEW`.

## Required Command

Render a redacted skeleton to stdout:

```bash
python3 harness/scripts/physical_acceptance_evidence_template.py --canary-key wp103-physical-acceptance-YYYYMMDD-N
```

Render a redacted skeleton to a local file:

```bash
python3 harness/scripts/physical_acceptance_evidence_template.py --canary-key wp103-physical-acceptance-YYYYMMDD-N --output /path/to/redacted-evidence.env
```

The command exits `0` only when the canary key and timestamp format are valid.
It exits `1` and prints a reason when the request is malformed.

## Default Template State

The template is deliberately not ready for the next print:

```text
canary_key=wp103-physical-acceptance-YYYYMMDD-N
operator_present=false
printer_visible=false
emergency_stop_ready=false
power_cutoff_ready=false
a1_mini_confirmed=false
swapmod_hardware_installed=false
bed_area_clear=false
plate_stack_ready=false
no_other_job_running=false
dry_run_gate_reviewed=false
release_verified=false
loaded_verified=false
final_state=MANUAL_REVIEW
rollback_confirmed=false
```

Required default-off flags remain:

```dotenv
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
```

The redacted audit fields are always emitted as:

```text
printer_id_redacted=A1_MINI_CANARY_REDACTED
operator_initials=REDACTED_OPERATOR
log_bundle_ref=REDACTED_LOG_BUNDLE
```

No additional evidence keys are emitted. Operators must fill only the existing
keys after a supervised physical attempt and then run the WP-104 validator.

## Failure Handling

Any malformed canary key, malformed timestamp, output write failure, or manual
editing that adds unknown keys keeps the evidence in `MANUAL_REVIEW`.

A completed evidence row can prove `READY_FOR_NEXT_PRINT` only after the human
operator records the real checklist results, reviewed sequence hashes, manual
release verification, manual load verification, and rollback confirmation.
