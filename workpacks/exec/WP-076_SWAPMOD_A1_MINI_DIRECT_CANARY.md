# WP-076 SwapMod A1 Mini Direct Canary

## Goal

Add a default-off Bambuddy-owned direct canary transport boundary for A1 Mini
SwapMod plate-change control. This prepares the software for a supervised
physical test but does not run any printer command by default.

## WP-06x vs WP-07x Comparison

WP-06x validates artifact-oriented 3MF paths: postprocess review, real-sample
output review, and one supervised upload/start canary. It proves Bambuddy can
run a reviewed 3MF artifact, but it does not directly execute plate-change
motion.

WP-07x validates runtime orchestration: SwapMod state-machine cycle, operator
trigger, dry-run transport, manual/camera verification, and dry-run canary
execution gate. WP-075 explicitly stops before printer control.

WP-076 fills the gap by adding a separate direct canary transport that consumes
WP-07x cycle state and sends only a server-side allowlisted A1 Mini sequence
file whose SHA-256 matches configuration. It does not accept raw G-code or an
arbitrary path from the API.

## Scope

In scope:

- Add `GET /api/v1/swapmod-a1-mini-direct-canary/status`.
- Add `POST /api/v1/swapmod-a1-mini-direct-canary/cycles/{cycle_key}/transport-steps`.
- Add default-off flags for A1 Mini direct canary execution.
- Require one printer id, one cycle, one transport step, exact phrase, and all
  checklist fields.
- Require configured server-side release/load sequence files and exact SHA-256
  matches.
- Require the current printer to be known idle: `IDLE`, or `FINISH` with no
  active file.
- Advance the SwapMod state machine to verification after a successful direct
  canary send.
- Block to manual review without retry when sending fails.

Out of scope:

- 3MF upload/start, queue dispatch, scheduler dispatch, batch mode, or next
  print automation.
- Arbitrary raw G-code request bodies, editable command text, or API-provided
  sequence paths.
- Multi-printer execution.
- Automatic retry or resume after restart.
- ERP, Obico, or bed automation mutation.

## Flags

- `FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false`
- `FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false`
- `FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true`
- `FARM_SWAPMOD_A1MINI_DIRECT_CANARY_SEQUENCE_ROOT` unset
- `FARM_SWAPMOD_A1MINI_DIRECT_CANARY_RELEASE_SEQUENCE_FILE` unset
- `FARM_SWAPMOD_A1MINI_DIRECT_CANARY_RELEASE_SEQUENCE_SHA256` unset
- `FARM_SWAPMOD_A1MINI_DIRECT_CANARY_LOAD_SEQUENCE_FILE` unset
- `FARM_SWAPMOD_A1MINI_DIRECT_CANARY_LOAD_SEQUENCE_SHA256` unset

## Contract

The direct canary endpoint requires the phrase:

```text
CONFIRM_A1_MINI_DIRECT_PLATE_CHANGE <printer_id> <cycle_key> <step> <sequence_sha256>
```

The request schema accepts only:

- `canary_key`
- `printer_id`
- `step`: `RELEASE_PLATE` or `LOAD_NEXT_PLATE`
- `operator_approved`
- `operator_approval_phrase`
- `checklist`

All responses are redacted and return sequence SHA/line count, not raw command
content.

## Validation

Required commands:

- `make test-swapmod-a1mini-direct-canary`
- `make test-swapmod-state-machine`
- `make verify-fast`
- `git diff --check`

## Evidence

2026-06-29 KST local validation:

- `make test-swapmod-a1mini-direct-canary` passed: 2 harness tests and 14 unit/architecture/API tests.
- `make test-swapmod-state-machine` passed: 2 harness tests and 44 existing WP-07x tests.
- `make verify-fast` passed: context/workpack/hooks checks, 79 harness tests, and 2 characterization tests.
- `git diff --check` passed.
- Proof checks showed no tracked or worktree `.3mf`, `.gcode`, or `.gcode.3mf` artifacts in the repository.
- Local port 18000 health passed with the direct canary route visible and disabled: `enabled=false`, `allow_real_commands=false`.

## Rollback

Disable either `FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED` or
`FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS`. There is no migration.

## Human Gate

The physical test must still be started manually tomorrow. The software must
remain disabled until the operator confirms printer visibility, emergency stop,
power cutoff, A1 Mini identity, SwapMod hardware, bed area, plate stack, no
other job, and reviewed dry-run gate.
