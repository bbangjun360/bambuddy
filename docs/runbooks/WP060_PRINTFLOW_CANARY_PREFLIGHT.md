# WP-060 Plate-Change Preflight

## Purpose

This runbook reflects the WP-060 architecture correction. PrintFlow and SwapMod
are treated as 3MF/G-code post-processing workflows, not remote control servers.
There is no PrintFlow server base URL for live operation.

This PR must not execute a real canary, send a printer command, or use a Bambu
printer IP address, access code, serial number, or local printer URL as
`FARM_PRINTFLOW_BASE_URL`.

## Non-Goals

- Do not start, pause, resume, cancel, or dispatch a real printer job.
- Do not execute any server call that claims to be PrintFlow or SwapMod.
- Do not send Bambu MQTT, FTPS, GPIO, serial, USB, BLE, or G-code commands.
- Do not use production printer credentials, ERP tokens, customer data, serial
  numbers, access codes, production URLs, or real network addresses.
- Do not enable automatic rollout, automatic retry, scheduler dispatch, or queue
  auto-dispatch.
- Do not treat this runbook as approval to move hardware.

## Required Roles

- Release owner: confirms branch, scope, and evidence package.
- Operator: confirms local harness setup and records dry-run observations.
- Safety observer: reviews stop conditions before any future hardware canary.
- Reviewer: confirms docs, feature flags, and architecture boundaries.

Use sanitized aliases in repo evidence, for example `CANARY_PRINTER_A`. Keep any
real alias mapping outside the repository.

## Safe Defaults

Confirm these defaults before accepting WP-060 evidence:

- `FARM_PRINTFLOW_REAL_ADAPTER_ENABLED=false`
- `FARM_PRINTFLOW_CANARY_DRY_RUN=true`
- `FARM_PRINTFLOW_CANARY_HUMAN_APPROVAL_REQUIRED=true`
- `FARM_PRINTFLOW_CANARY_SINGLE_PRINTER_ONLY=true`
- `FARM_PRINTFLOW_BASE_URL` unset by default
- `FARM_PRINTFLOW_API_TOKEN` unset by default

`FARM_PRINTFLOW_BASE_URL` and `FARM_PRINTFLOW_API_TOKEN` are legacy
server-adapter settings. They are not configured for live operation and must not
be populated with a printer IP, access code, serial, local URL, or any fake
PrintFlow server endpoint.

## Boundary Review

Confirm these boundaries before running any mock or dry-run check:

- Bambuddy remains the sole authority for printer state-changing commands.
- PrintFlow/SwapMod are treated as 3MF/G-code post-processing workflows.
- External modules do not connect directly to Bambu MQTT or FTPS.
- OrcaSlicer slices only and never starts a printer.
- ERPNext never controls a printer.
- No next print can be dispatched until Bambuddy verifies bed state `READY`.
- Any uncertain physical bed state after restart becomes `MANUAL_REVIEW`.
- ERP inventory and accounting writes remain idempotent and Draft-only.
- No general arbitrary G-code endpoint is introduced.

## Legacy External Adapter Hold

The legacy `/api/v1/printflow-canary/real-canary-runs` path is deprecated and
pending redesign. It remains only to return a blocked audit response with
`external_adapter_pending_redesign`. Do not use it for live operation, do not
configure a base URL, and do not run a fake PrintFlow server canary.

## Future 3MF Post-Process Path

A later Work Package may implement this file-based flow:

- input `.3mf`
- inject reviewed plate-change G-code into the embedded plate G-code
- produce modified `.3mf`
- send/start through the existing Bambuddy flow
- verify with extraction, diff, fixture, and round-trip tests

This preflight does not implement that path.

## Future Bambuddy-Native Supervised Direct Command Path

A later Work Package may implement direct supervised plate exchange only if all
of these are true:

- no 3MF modification for that path
- operator selects exactly one printer
- operator confirms bed and plate state
- Bambuddy sends one predefined allowlisted G-code sequence
- no arbitrary G-code endpoint
- no scheduler trigger
- no queue auto-dispatch
- no repeat or automatic retry
- audit log required
- hardware canary required before enabling

This preflight does not implement that path.

## Dry-Run Readiness Checklist

- [ ] Bambuddy baseline starts in the local harness.
- [ ] `make verify-fast` has fresh evidence for this branch.
- [ ] Mock readiness scenarios pass without external adapter endpoints.
- [ ] Failure, timeout, duplicate, lost-ack, and restart-uncertain cases are
      covered by tests or harness scenarios.
- [ ] Feature flags for bed automation and canary behavior are default-off.
- [ ] Dry-run mode is default-on for any bed automation path.
- [ ] Logs include sanitized aliases, state transition, stop reason when
      applicable, and idempotency key.
- [ ] Logs do not include secrets, access codes, serials, real endpoints, or
      customer data.
- [ ] Automatic rollout remains disabled.
- [ ] Automatic retry remains disabled unless a later approved Work Package
      explicitly adds a bounded, tested policy.

## Evidence Package

The PR should include:

- `git status --short` showing only expected WP-060 code, test, workpack, and
  runbook paths.
- `git diff --check` output.
- `make test-printflow-canary` output.
- `make verify-fast` output.
- `make verify-full` output.
- A statement that Bambuddy still starts from the verification target.
- A statement that no real printer command, credential, serial, access code,
  production URL, or customer data was added.

## Handoff

Proceed to `docs/runbooks/FIRST_PRINTER_CANARY_CHECKLIST.md` only for a later
hardware canary planning record. If any stop condition is met, use
`docs/runbooks/PRINTFLOW_CANARY_STOP_CONDITIONS.md` and do not continue canary
preparation until the release owner records the resolution.
