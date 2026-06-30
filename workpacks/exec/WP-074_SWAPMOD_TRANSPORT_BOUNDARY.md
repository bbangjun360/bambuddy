# WP-074 SwapMod Transport Boundary

## Goal

Add a dry-run transport boundary for SwapMod release/load steps so Bambuddy can exercise step dispatch flow without real printer transport.

## Scope

- Add `POST /api/v1/swapmod-state-machine/cycles/{cycle_key}/transport-steps`.
- Accept only `RELEASE_PLATE` and `LOAD_NEXT_PLATE` steps.
- Accept only mock `success`, `failure`, and `timeout` results.
- Apply existing state-machine events: `START_STEP`, `STEP_MOCK_SUCCEEDED`, `STEP_MOCK_FAILED`, and `TIMEOUT`.
- Return audit flags proving real transport did not run.

## Out Of Scope

- Real printer command transport.
- Network, MQTT, FTPS, USB, serial, or arbitrary command clients.
- Queue, scheduler, ERP, Obico, or bed automation mutations.
- UI changes.

## Contracts

- `POST /api/v1/swapmod-state-machine/cycles/{cycle_key}/transport-steps`

Responses include the public cycle shape plus `transport_mode`, `transport_status`, `real_transport_supported=false`, and `real_command_sent=false`.

## Flags

- `farm_swapmod_transport_enabled: bool = False`
- `farm_swapmod_transport_dry_run: bool = True`
- `farm_swapmod_allow_real_transport: bool = False`

## Validation

- `make test-swapmod-transport-boundary`
- `make test-swapmod-state-machine`
- `make verify-fast`

## Evidence

2026-06-30 local validation:

- `make test-swapmod-transport-boundary` passed: harness 2 tests, Docker unit/architecture/integration 44 tests.
- `make test-swapmod-state-machine` passed: harness 2 tests, Docker unit/architecture/integration 44 tests.
- `make verify-fast` passed: context/workpack/hooks, harness contract/unit, and characterization gates.
- `git diff --check` passed.
- Implementation scan found no direct printer/network/control transport references.

## Rollback

Disable `FARM_SWAPMOD_TRANSPORT_ENABLED` or remove the transport route. The change only updates SwapMod state-machine records and never sends printer commands.
