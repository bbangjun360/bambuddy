# WP-060 Plate-Change Architecture Correction

## Status

Accepted for the WP-060 correction PR on 2026-06-25.

## Context

The earlier WP-060-B server-adapter assumption was wrong. PrintFlow and
SwapMod are treated as product/workflow names for plate-change automation by
3MF/G-code transformation. They are not remote control servers that Bambuddy
should call through `FARM_PRINTFLOW_BASE_URL`.

There is no PrintFlow server base URL for live operation. Do not use a Bambu
printer IP address, access code, serial number, local printer URL, or any other
printer credential as `FARM_PRINTFLOW_BASE_URL`. Do not commit production
printer identifiers, access codes, API tokens, customer data, or real network
addresses while working on WP-060.

## Decision

WP-060 treats PrintFlow/SwapMod as 3MF/G-code post-processing workflows, not as
remote control servers.

The previous `FARM_PRINTFLOW_BASE_URL` plus API-token server-adapter model is
not configured and must not be used for live operation. The legacy
`/api/v1/printflow-canary/real-canary-runs` route remains only as an auditable
blocked compatibility path while the architecture is redesigned. It must not
construct an external adapter, make a network call, or dispatch hardware. The
blocked reason is `external_adapter_pending_redesign`.

No direct Bambu MQTT, FTPS, or G-code command path is implemented by this
correction. Bambuddy remains the sole authority for any future printer
state-changing command.

## Future Path A: 3MF Post-Process

The safer near-term direction is a file transformation workflow:

1. Accept an input `.3mf` file through an approved Bambuddy-controlled flow.
2. Extract the relevant embedded G-code from the 3MF package.
3. Inject a predefined plate-change G-code sequence at a reviewed location.
4. Produce a modified `.3mf` artifact.
5. Send or start that artifact through the existing Bambuddy print flow only.
6. Verify behavior with archive extraction tests, structural diff tests, and
   fixture 3MF round-trip tests before any hardware canary.

This path must not introduce a live PrintFlow server, printer credential use by
external modules, direct MQTT/FTPS access, or a general arbitrary G-code
endpoint.

## Future Path B: Bambuddy-Native Supervised Direct Command

A later Bambuddy-native path may skip 3MF modification, but only with explicit
human supervision and a narrow allowlist:

1. The operator selects exactly one printer.
2. The operator confirms the bed and plate state.
3. Bambuddy sends one predefined allowlisted G-code sequence for plate exchange.
4. No arbitrary G-code endpoint is exposed.
5. No scheduler path may trigger it.
6. No queue auto-dispatch may trigger it.
7. No repeat or automatic retry is allowed.
8. Every request requires an audit log entry with operator, printer, command
   identifier, confirmation, timestamp, and result.
9. Hardware canary evidence and a human checklist are required before the path
   can be enabled.

This path is not implemented in the correction PR.

## Consequences

- `FARM_PRINTFLOW_REAL_ADAPTER_ENABLED` stays default-off.
- `FARM_PRINTFLOW_CANARY_DRY_RUN` stays default-on.
- `FARM_PRINTFLOW_BASE_URL` and `FARM_PRINTFLOW_API_TOKEN` stay unset by
  default and are not live-operation settings.
- `/real-canary-runs` is deprecated/pending redesign and blocked even if legacy
  gates are set.
- Existing mock readiness checks remain dry-run and audit-only.
- Tests must continue proving no printer commands, no arbitrary G-code endpoint,
  no queue or scheduler side effects, and no ERP/Obico/bed mutations.

## Rollback

Rollback is a file-level revert of this correction PR. There is no migration and
no persistent WP-060 table. Rollback must not restore any committed printer
identifier, credential, or fake PrintFlow server canary instruction.
