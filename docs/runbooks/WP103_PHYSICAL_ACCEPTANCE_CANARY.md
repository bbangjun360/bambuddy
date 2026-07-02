# WP-103 Physical Acceptance Canary

This runbook records the human-gated physical acceptance canary for release tag
`farm-v0.1.0-acceptance` at commit `9190b2fc6ac1e111234ad73d8d73e2a487d81be5`.
It is a manual acceptance packet only. No physical printer action is executed by CI,
by the harness target, or by this PR.

## Authority and Scope

Bambuddy remains the sole authority for printer state-changing commands. The
acceptance canary uses the existing WP-076 A1 Mini direct plate-change gate and
does not add a runtime endpoint, queue dispatch, scheduler dispatch, ERP command,
Obico command, slicer command, raw printer transport, or arbitrary G-code path.

Simulation success is not physical safety evidence. Physical evidence is valid
only when a named operator completes the checklist, supervises the A1 Mini canary
device, records the sequence hashes, and confirms the final bed state.

Never automatically resume an uncertain physical bed action after restart. Any
uncertain state is `MANUAL_REVIEW` until a human records the next safe action.

## Release Gate

Before touching the printer, confirm all release gates:

- Tag: `farm-v0.1.0-acceptance`
- Tag commit: `9190b2fc6ac1e111234ad73d8d73e2a487d81be5`
- Manual Security Audit run: `28562025959`
- Post-tag Security Audit run: `28562152131`
- Open PRs against `farm-main`: none at release tagging time
- WP-076 prior physical evidence: supervised A1 Mini cycle
  `wp076-a1mini-20260630-release-2`

## Default-Off Flags

Rollback and idle state must leave the direct canary disabled:

```dotenv
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
```

The real-command flag may be changed only for a supervised local execution window
after the checklist and confirmation phrase are complete. CI and automated tests
must keep it false.

## Human Checklist

Record these values before any direct physical canary action:

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
```

Any false value stops the attempt and records `MANUAL_REVIEW`.

## Confirmation Phrases

The WP-103 acceptance gate phrase is:

```text
CONFIRM_WP103_PHYSICAL_ACCEPTANCE_CANARY PRINTER_ID farm-v0.1.0-acceptance CANARY_KEY
```

Each direct A1 Mini plate-change step must also use the WP-076 phrase:

```text
CONFIRM_A1_MINI_DIRECT_PLATE_CHANGE PRINTER_ID CANARY_KEY STEP SEQUENCE_SHA256
```

Allowed step names for this acceptance packet are `RELEASE_PLATE` and
`LOAD_NEXT_PLATE`. The sequence hash must be the exact SHA-256 for the reviewed
step payload. A missing or mismatched hash stops the attempt with `MANUAL_REVIEW`.

## Execution Record

Record one acceptance row per physical attempt:

```text
canary_key=wp103-physical-acceptance-YYYYMMDD-N
printer_id_redacted=A1_MINI_CANARY_REDACTED
release_tag=farm-v0.1.0-acceptance
release_commit=9190b2fc6ac1e111234ad73d8d73e2a487d81be5
release_sequence_sha256=SHA256_RELEASE_SEQUENCE
load_sequence_sha256=SHA256_LOAD_SEQUENCE
release_verified=true
loaded_verified=true
final_state=READY_FOR_NEXT_PRINT
rollback_confirmed=true
operator_initials=REDACTED_OPERATOR
```

`READY_FOR_NEXT_PRINT` is valid only after manual release verification, manual
load verification, bed-area inspection, and rollback to the default-off flags.
It does not authorize automatic queue dispatch.

## Stop and Rollback

Stop immediately and record `MANUAL_REVIEW` when any of these occur:

- The printer is not continuously visible to the operator.
- Emergency stop or power cutoff access is not ready.
- Bed area is not clear.
- Plate stack is not ready or shifts unexpectedly.
- The sequence hash does not match the reviewed step.
- Bambuddy reports an unexpected printer, bed, or transport state.
- Any restart occurs during an uncertain bed action.

Rollback means restoring:

```dotenv
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
```

After rollback, capture logs, operator notes, final bed state, and whether the
attempt is safe for another supervised attempt.
