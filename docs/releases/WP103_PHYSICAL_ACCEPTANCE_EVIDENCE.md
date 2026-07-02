# WP-103 Physical Acceptance Evidence

## Release Gate Evidence

- Release tag: `farm-v0.1.0-acceptance`
- Release commit: `9190b2fc6ac1e111234ad73d8d73e2a487d81be5`
- WP-101 release readiness PR: `#61`
- WP-102 security dispatch PR: `#62`
- Manual Security Audit run: `28562025959`
- Post-tag Security Audit run: `28562152131`
- Release tag Security Audit run: `28562152131`
- Open PRs against `farm-main` at tagging time: none
- Acceptance tag pushed and verified before WP-103 began

## Physical Canary Record

No physical execution has been recorded by WP-103. This file is the required
evidence ledger for a later supervised A1 Mini acceptance attempt; it is not a
claim that a new physical run has happened.

Current ledger state:

```text
canary_key=wp103-physical-acceptance-pending
printer_id_redacted=A1_MINI_CANARY_REDACTED
release_tag=farm-v0.1.0-acceptance
release_commit=9190b2fc6ac1e111234ad73d8d73e2a487d81be5
release_sequence_sha256=NOT_RECORDED
load_sequence_sha256=NOT_RECORDED
release_verified=false
loaded_verified=false
final_state=MANUAL_REVIEW
rollback_confirmed=true
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
```

## Required Physical Evidence Fields

Every supervised acceptance attempt must append a completed record with:

- `canary_key`
- `printer_id_redacted`
- `operator_present`
- `printer_visible`
- `emergency_stop_ready`
- `power_cutoff_ready`
- `bed_area_clear`
- `a1_mini_confirmed`
- `swapmod_hardware_installed`
- `plate_stack_ready`
- `dry_run_gate_reviewed`
- `no_other_job_running`
- `release_sequence_sha256`
- `load_sequence_sha256`
- `release_verified`
- `loaded_verified`
- `final_state`
- `rollback_confirmed`
- timestamp, operator initials, and redacted log bundle reference

`final_state=READY_FOR_NEXT_PRINT` is valid only after manual verification of
both plate steps and rollback to default-off flags.

## Rollback Evidence

The accepted rollback state is:

```dotenv
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
```

Any record that cannot prove these values after the attempt remains
`final_state=MANUAL_REVIEW`.
