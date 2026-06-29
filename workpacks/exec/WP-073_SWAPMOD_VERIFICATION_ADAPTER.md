# WP-073 SwapMod Verification Adapter

## Goal

Add a dedicated verification adapter endpoint so operator/manual checks or camera mock checks can advance the SwapMod state machine without exposing raw commands or printer transport.

## Scope

- Add `POST /api/v1/swapmod-state-machine/cycles/{cycle_key}/verifications`.
- Accept only `manual` and `camera_mock` verification sources.
- Accept only `pass` and `fail` verification results.
- Map valid verification states to existing `VERIFY_PASSED` and `VERIFY_FAILED` events.

## Out Of Scope

- Real camera inference.
- Real printer command transport.
- Queue, scheduler, ERP, Obico, MQTT, FTPS, or bed automation mutations.
- UI changes.

## Contracts

- `POST /api/v1/swapmod-state-machine/cycles/{cycle_key}/verifications`

The response is the existing public cycle shape and includes `real_execution_supported=false` and `printer_command_sent=false`.

## Flags

Uses the existing default-off `farm_swapmod_state_machine_enabled` and dry-run `farm_swapmod_state_machine_dry_run` flags.

## Validation

- `make test-swapmod-verification-adapter`
- `make test-swapmod-state-machine`
- `make verify-fast`

## Rollback

Disable `FARM_SWAPMOD_STATE_MACHINE_ENABLED` or remove the verification route. The change only updates SwapMod state-machine records and does not dispatch printer actions.
