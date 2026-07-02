# WP-105 Physical Acceptance Evidence Template

## Template Ledger

No physical evidence has been generated or validated by WP-105. The template
generator exists so a later supervised A1 Mini physical acceptance record can be
started from the WP-104 allowlisted field set without moving hardware.

## Current Result

```text
template_run_record=wp105-template-not-yet-used
final_state=MANUAL_REVIEW
reason=no supervised physical evidence row has been completed
operator_present=false
release_verified=false
loaded_verified=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
```

## Required Use

Render a redacted skeleton and preserve the command output or output file path:

```bash
python3 harness/scripts/physical_acceptance_evidence_template.py --canary-key wp103-physical-acceptance-YYYYMMDD-N
```

After a supervised run, keep only the emitted keys, fill the recorded values, and
validate the file with WP-104 before appending evidence to the physical ledger.

## Safety Statement

Bambuddy remains the sole authority for printer state-changing commands.
Evidence template generation is not physical safety evidence, and the skeleton
remains `MANUAL_REVIEW` until a supervised record passes validation.
