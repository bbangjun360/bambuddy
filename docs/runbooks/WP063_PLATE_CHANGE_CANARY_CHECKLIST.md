# WP-063 Plate-Change Command Canary Checklist

## Purpose

This checklist is for a later human-supervised plate-change command canary. It
is not a command procedure and does not authorize real hardware movement.
WP-063-A only proves the dry-run API boundary.

## Identity Rules

- Use sanitized aliases such as `CANARY_PRINTER_A` in repo material.
- Keep real printer names, network addresses, access codes, serial numbers,
  locations, and operator notes outside this repository.
- Keep the canary scope to exactly one printer until a later Work Package changes
  the rollout policy.
- Do not use customer data, production print files, or production credentials in
  checklist evidence.

## Pre-Approval

- [ ] Release owner assigned.
- [ ] Operator assigned.
- [ ] Safety observer assigned.
- [ ] Reviewer assigned.
- [ ] WP-063-A dry-run evidence reviewed.
- [ ] Stop conditions reviewed by operator and safety observer.
- [ ] The team understands that dry-run success does not prove physical safety.
- [ ] A separate approval record exists outside this repo for any real action.
- [ ] Repo-facing evidence is fully redacted.

## Dry-Run Gate

- [ ] `FARM_PLATE_CHANGE_COMMAND_ENABLED=true` only in the selected non-production
      test environment.
- [ ] `FARM_PLATE_CHANGE_COMMAND_DRY_RUN=true`.
- [ ] `FARM_PLATE_CHANGE_HUMAN_APPROVAL_REQUIRED=true`.
- [ ] `FARM_PLATE_CHANGE_SINGLE_PRINTER_ONLY=true`.
- [ ] `FARM_PLATE_CHANGE_ALLOW_REAL_COMMANDS=false`.
- [ ] `GET /api/v1/plate-change/status` reports `DRY_RUN_ONLY`.
- [ ] `POST /api/v1/plate-change/dry-run-commands` succeeds only with exactly
      one sanitized printer alias.
- [ ] The request uses `command_sequence=supervised_plate_change_v1`.
- [ ] The approval phrase exactly matches
      `CONFIRM_DRY_RUN_PLATE_CHANGE <printer-alias> supervised_plate_change_v1`.
- [ ] The response has `ready_for_real_command=false`.
- [ ] All action fields are `None`.
- [ ] All sentinels are zero.
- [ ] No arbitrary command body field is accepted.

## Stop Conditions

Stop immediately if any of the following occur:

- More than one printer is selected.
- The approval phrase is missing or wrong.
- `FARM_PLATE_CHANGE_ALLOW_REAL_COMMANDS=true`.
- `FARM_PLATE_CHANGE_COMMAND_DRY_RUN=false`.
- Any arbitrary command text is accepted.
- Any Bambu MQTT command method is called during dry-run evidence collection.
- Any FTPS helper is called during dry-run evidence collection.
- Any queue, scheduler, or background dispatch path runs.
- Any ERP submit/posting, Obico mutation, or bed automation mutation occurs.
- A real printer identifier, access code, serial number, network address, API key,
  customer name, or production URL appears in evidence.

## Physical Canary Hold Point

Before a later Work Package can request real execution:

- [ ] Exact command sequence reviewed and versioned outside arbitrary user input.
- [ ] Dedicated printer-manager execution method implemented and tested.
- [ ] Audit record design reviewed.
- [ ] Printer is idle and visually inspected by a human.
- [ ] Bed and plate state are physically confirmed.
- [ ] Emergency stop or power cutoff is reachable.
- [ ] Manual recovery path is assigned.
- [ ] No automatic retry exists.
- [ ] Restart from uncertain state requires manual review.
- [ ] No next print starts until bed state is verified `READY`.

## Result Record

Record sanitized values only:

- Dry-run id:
- Sanitized printer alias:
- Command sequence id:
- Approval phrase status:
- Sentinel status:
- Stop condition encountered:
- Human owner:
- Follow-up required:

Keep real identifiers and sensitive notes outside the repository.
