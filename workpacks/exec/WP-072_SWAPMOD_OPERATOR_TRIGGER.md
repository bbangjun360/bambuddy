# WP-072 SwapMod Operator Trigger

## Goal

Allow an operator command, after print completion, to start a SwapMod state-machine cycle without executing any printer action.

## Scope

- Add `POST /api/v1/swapmod-state-machine/operator-triggers`.
- Accept only the allowlisted `START_SWAPMOD_PLATE_CHANGE` intent.
- Create or reuse a SwapMod cycle and apply the internal `PRINT_FINISHED` event to reach `READY_TO_RELEASE`.
- Preserve the dry-run/no-command boundary from WP-071.

## Out Of Scope

- Real printer command transport.
- Starting release/load steps automatically.
- Queue, scheduler, ERP, Obico, MQTT, FTPS, or bed automation mutations.
- UI changes.

## Contracts

- `POST /api/v1/swapmod-state-machine/operator-triggers`

The response is the existing public cycle shape and includes `real_execution_supported=false` and `printer_command_sent=false`.

## Flags

Uses the existing default-off `farm_swapmod_state_machine_enabled` and dry-run `farm_swapmod_state_machine_dry_run` flags.

## Validation

- `make test-swapmod-operator-trigger`
- `make test-swapmod-state-machine`
- `make verify-fast`

## Rollback

Disable `FARM_SWAPMOD_STATE_MACHINE_ENABLED` or remove the operator trigger route. The change only advances SwapMod state-machine records and does not dispatch printer actions.
