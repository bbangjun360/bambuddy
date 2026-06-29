# WP-071 SwapMod State Machine v1

## Goal

Implement a default-off, dry-run SwapMod plate-change state machine so Bambuddy can split plate replacement into explicit, inspectable steps after a print finishes.

## Scope

- Durable SwapMod cycle model.
- State transition service for mock step completion, verification, retry, timeout, restart, and manual review paths.
- API status, cycle creation, and event application endpoints.
- Focused unit, integration, architecture, and harness contract tests.

## Out Of Scope

- Real printer command transport.
- Queue, scheduler, ERP, Obico, MQTT, FTPS, or bed automation mutation.
- UI changes.
- Arbitrary command input.

## Contracts

- `GET /api/v1/swapmod-state-machine/status`
- `POST /api/v1/swapmod-state-machine/cycles`
- `POST /api/v1/swapmod-state-machine/cycles/{cycle_key}/events`

Every public cycle response includes `real_execution_supported=false` and `printer_command_sent=false`.

## Flags

- `farm_swapmod_state_machine_enabled: bool = False`
- `farm_swapmod_state_machine_dry_run: bool = True`

## Validation

- `make test-swapmod-state-machine`
- `make test-bed-automation`
- `make test-plate-change-command`
- `make verify-fast`

## Rollback

Disable `FARM_SWAPMOD_STATE_MACHINE_ENABLED` or remove the new route registration. The feature owns only the `swapmod_state_machine_cycles` table and does not start prints or dispatch printer actions.
