# WP-060 PrintFlow Canary Preflight

## Purpose

This runbook prepares WP-060-A PrintFlow canary readiness without authorizing
real device movement. It is a documentation and evidence gate for a later,
separately approved physical canary.

The only acceptable preflight evidence comes from the local mock harness,
dry-run behavior, sanitized logs, and human review. Simulation success is not
evidence that the physical system is safe.

## Non-Goals

- Do not start, pause, resume, cancel, or dispatch a real printer job.
- Do not send a real PrintFlow, ERPNext, Obico, MQTT, FTPS, GPIO, serial, USB,
  BLE, or G-code command.
- Do not use production printer credentials, ERP tokens, customer data, serial
  numbers, access codes, production URLs, or real network addresses.
- Do not enable automatic rollout or automatic retry.
- Do not treat this runbook as approval to move hardware.

## Required Roles

- Release owner: confirms the branch, scope, and evidence package.
- Operator: confirms local harness setup and records dry-run observations.
- Safety observer: reviews stop conditions before any future physical canary.
- Reviewer: confirms docs, feature flags, and architecture boundaries.

Use sanitized aliases in repo evidence, for example `CANARY_PRINTER_A` and
`PRINTFLOW_TEST_DEVICE_A`. Keep any real alias mapping outside the repository.

## Preflight Inputs

Record the following before any canary discussion:

- Branch name and commit under review.
- Work Package identifier: `WP-060-A PrintFlow Canary Readiness`.
- Feature flags and dry-run settings.
- Harness scenario names used.
- Test commands and exit status.
- Redacted log bundle location.
- Human gate approvals or explicit deferrals.

Do not paste secrets, real endpoints, printer identifiers, access codes, or
customer data into the evidence package.

## Boundary Review

Confirm these boundaries before running any mock or dry-run check:

- Bambuddy remains the sole authority for printer state-changing commands.
- PrintFlow Adapter is treated as a bed-device driver only.
- External modules do not connect directly to Bambu MQTT or FTPS.
- OrcaSlicer slices only and never starts a printer.
- ERPNext never controls a printer.
- No next print can be dispatched until Bambuddy verifies bed state `READY`.
- Any uncertain physical bed state after restart becomes `MANUAL_REVIEW`.
- ERP inventory and accounting writes remain idempotent and Draft-only.
- No general arbitrary G-code endpoint is introduced.

## Dry-Run Readiness Checklist

- [ ] Bambuddy baseline starts in the local harness.
- [ ] `make verify-fast` has fresh evidence for this branch.
- [ ] Mock PrintFlow scenarios pass without real adapter endpoints.
- [ ] Failure, timeout, duplicate, lost-ack, and restart-uncertain cases are
      covered by tests or harness scenarios.
- [ ] Feature flags for bed automation and canary behavior are default-off.
- [ ] Dry-run mode is default-on for any bed automation path.
- [ ] Logs include a run identifier, sanitized printer alias, sanitized device
      alias, state transition, stop reason when applicable, and idempotency key.
- [ ] Logs do not include secrets, access codes, serials, real endpoints, or
      customer data.
- [ ] Any canary allow-list is limited to one sanitized printer alias in local
      operator records, not committed files.
- [ ] Automatic rollout remains disabled.
- [ ] Automatic retry remains disabled unless a later approved Work Package
      explicitly adds a bounded, tested policy.

## Human Gates

Before any later physical canary is requested, the release owner must confirm:

- [ ] The mock harness evidence package is complete.
- [ ] The first-printer checklist has an assigned operator and safety observer.
- [ ] Stop conditions are reviewed and printed or otherwise visible to the
      operator.
- [ ] A physical E-stop or equivalent emergency stop path is known to the human
      team.
- [ ] A separate approval record exists for any real hardware action.
- [ ] The exact real canary identifiers remain outside the repository.

This runbook stops at readiness. Any real hardware step must be approved outside
this document and must not be represented by committed commands or fixture data.

## Evidence Package

The parent integration should receive:

- `git status --short` showing only expected documentation paths for this
  subtask.
- `git diff --check` output.
- Fresh validation output selected by the parent, at minimum `make verify-fast`
  if the parent is running full WP validation.
- Redacted dry-run harness logs.
- A completed copy of the first-printer checklist, with real identifiers
  removed before it enters the repo or PR description.
- Any stop condition encountered, even if the run was mock-only.

## Handoff

Proceed to `docs/runbooks/FIRST_PRINTER_CANARY_CHECKLIST.md` only after this
preflight is complete. If any stop condition is met, use
`docs/runbooks/PRINTFLOW_CANARY_STOP_CONDITIONS.md` and do not continue canary
preparation until the release owner records the resolution.
