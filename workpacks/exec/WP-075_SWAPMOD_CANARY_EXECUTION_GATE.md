# WP-075 SwapMod Canary Execution Gate

## Goal

Add a default-off SwapMod canary execution gate that evaluates whether a verified SwapMod cycle is ready for supervised canary use without sending any printer command.

## Scope

- Add `POST /api/v1/swapmod-state-machine/cycles/{cycle_key}/canary-execution-gates`.
- Require the SwapMod cycle to be `READY_FOR_NEXT_PRINT`.
- Require a named canary printer alias, operator approval, exact approval phrase, and complete checklist.
- Require the WP-074 transport boundary to remain enabled, dry-run, and non-real.
- Return audit fields proving no real execution occurred.

## Out Of Scope

- Real printer upload, start, G-code, MQTT, FTPS, USB, serial, or network command execution.
- Queue, scheduler, ERP, Obico, or bed automation mutations.
- Automatic retry or automatic resume after uncertain physical state.
- UI changes.

## Contract

- `POST /api/v1/swapmod-state-machine/cycles/{cycle_key}/canary-execution-gates`

Responses include the public cycle shape plus `gate_status`, `ready_for_canary`, `blocked_reasons`, `execution_mode`, `canary_printer_alias`, `required_operator_approval_phrase`, `real_execution_supported=false`, and `real_command_sent=false`.

## Flags

- `farm_swapmod_canary_execution_gate_enabled: bool = False`
- `farm_swapmod_canary_execution_dry_run: bool = True`
- `farm_swapmod_canary_allow_real_execution: bool = False`

## Validation

- `make test-swapmod-canary-execution-gate`
- `make test-swapmod-state-machine`
- `make verify-fast`

## Evidence

2026-06-29 local validation:

- `make test-swapmod-canary-execution-gate` passed.
- `make test-swapmod-state-machine` passed.
- `make verify-fast` passed.
- `git diff --check` passed.
- Implementation scan found no direct printer/network/control transport references.

## Rollback

Disable `FARM_SWAPMOD_CANARY_EXECUTION_GATE_ENABLED` or remove the canary execution gate route. The change is audit-only and never sends printer commands.
