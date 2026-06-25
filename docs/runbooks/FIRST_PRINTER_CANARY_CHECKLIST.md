# First Printer Canary Checklist

## Purpose

This checklist defines the human review gates for the first PrintFlow canary
printer. It is not a command procedure and does not authorize real hardware
movement. Use it to decide whether a later, separately approved physical canary
request is ready.

This PR must not execute a real PrintFlow call. Treat every item below as
readiness evidence for a later approval record, not as permission to move
hardware.

## Canary Identity Rules

- Use sanitized aliases in repo material, such as `CANARY_PRINTER_A`.
- Store real printer names, serial numbers, access codes, locations, and device
  mappings only in the approved private operations record.
- Do not copy production URLs, IP addresses, customer names, or secrets into
  this checklist.
- Keep the canary set to one printer and one PrintFlow test device until a
  later rollout Work Package changes the policy.

## Pre-Approval

- [ ] Release owner assigned.
- [ ] Operator assigned.
- [ ] Safety observer assigned.
- [ ] Reviewer assigned.
- [ ] WP-060 preflight runbook completed with mock harness evidence.
- [ ] Stop conditions reviewed by the operator and safety observer.
- [ ] The operator understands that simulation success does not prove physical
      safety.
- [ ] Any future real action has a separate approval record outside this repo.
- [ ] The checklist copy intended for repo or PR evidence is fully redacted.

## Bambuddy Control Plane

- [ ] Bambuddy starts and responds in the local harness or staging environment
      selected by the parent integration owner.
- [ ] Bambuddy remains the only component allowed to approve printer
      state-changing commands.
- [ ] No external module has Bambu MQTT or FTPS credentials.
- [ ] No arbitrary G-code endpoint is present.
- [ ] No scheduler path can dispatch the next print unless bed state is verified
      `READY`.
- [ ] A restart from `EXECUTING`, `VERIFYING`, or any uncertain bed state enters
      `MANUAL_REVIEW` instead of resuming automatically.

## Safe Defaults

- [ ] `FARM_PRINTFLOW_REAL_ADAPTER_ENABLED=false`
- [ ] `FARM_PRINTFLOW_CANARY_DRY_RUN=true`
- [ ] `FARM_PRINTFLOW_CANARY_HUMAN_APPROVAL_REQUIRED=true`
- [ ] `FARM_PRINTFLOW_CANARY_SINGLE_PRINTER_ONLY=true`
- [ ] `FARM_PRINTFLOW_BASE_URL` unset by default
- [ ] `FARM_PRINTFLOW_API_TOKEN` unset by default
- [ ] Stop if the real adapter is enabled unexpectedly, dry-run is disabled
      unexpectedly, or real adapter credentials are present without a separate
      approved physical canary record.

## Feature Flags and Modes

- [ ] Bed automation remains disabled by default.
- [ ] Bed automation dry-run remains enabled by default.
- [ ] Any canary-specific flag remains disabled by default.
- [ ] Automatic rollout is disabled.
- [ ] Automatic retry is disabled unless explicitly approved in a later Work
      Package.
- [ ] ERP writes remain Draft-only and idempotent if the parent flow touches ERP
      evidence.
- [ ] Obico remains notify-only if Obico evidence is present.

## Mock Harness Evidence

- [ ] Normal simulated completion covered.
- [ ] Plate-already-empty or equivalent no-op case covered.
- [ ] Adapter failure covered.
- [ ] Adapter timeout covered.
- [ ] Duplicate callback or duplicate command idempotency covered.
- [ ] Lost acknowledgement covered.
- [ ] Restart-uncertain state covered.
- [ ] Object-remains or post-check-failed case covered.
- [ ] E-stop-active or safety-blocked case covered if the harness supports it.
- [ ] Logs and metrics include sanitized aliases and stop reasons.
- [ ] Logs and metrics do not include secrets or real identifiers.

## Real PrintFlow Approval Hold Point

This PR must not ask for or use the approval phrase to execute a real PrintFlow
call. Before any later real hardware-affecting PrintFlow call, the release owner
must ask for this exact approval phrase and no variant:

`CONFIRM_REAL_PRINTFLOW_CANARY <printer_id> <job_id>`

Do not ask for that phrase until the operator confirms this checklist:

- [ ] target printer is physically visible or actively monitored
- [ ] bed is clear
- [ ] emergency stop or power cutoff is accessible
- [ ] correct filament is loaded
- [ ] correct build plate is installed
- [ ] no production/customer job is involved
- [ ] job is a low-risk canary job
- [ ] operator is ready to stop the printer manually
- [ ] logs/telemetry are being captured
- [ ] rollback path is known

The approval phrase must match exactly one printer and one job. Missing,
mismatched, stale, or partial approval is a stop condition.

## Physical Readiness Hold Point

The following checks are required before a separate physical canary request can
be considered. They still do not authorize motion.

- [ ] The named physical printer is idle, not running, not paused, not
      preparing, and not dispatching.
- [ ] The bed is visually inspected by a human.
- [ ] The PrintFlow test device is visually inspected by a human.
- [ ] The safety observer can reach the emergency stop path.
- [ ] Emergency stop or power cutoff is accessible before any real
      hardware-affecting request is considered.
- [ ] The operator has a manual recovery path for uncertain bed state.
- [ ] Non-production material and a non-customer test artifact are selected in
      private operator records.
- [ ] No production credentials or customer data are needed for the canary.
- [ ] Network access is restricted to the approved local test environment.
- [ ] A rollback path is documented without deleting volumes or audit evidence.
- [ ] The rollback owner knows how to disable the real adapter, restore dry-run,
      preserve logs, and leave the affected printer in manual review.

## Observation Rules for Any Later Approved Canary

If a separate approval authorizes a real canary, keep these rules visible to the
human team:

- One canary printer only.
- One bed action at a time.
- No automatic retry after timeout, lost acknowledgement, restart, unknown state,
  manual interruption, or post-check failure.
- No next print until Bambuddy records bed state `READY`.
- Any uncertain state becomes `MANUAL_REVIEW`.
- Any stop condition halts rollout and preserves logs.

## Result Record

Record the result with sanitized values only:

- Run identifier:
- Sanitized printer alias:
- Sanitized PrintFlow device alias:
- Dry-run evidence bundle:
- Human gate status:
- Stop condition encountered:
- Resolution owner:
- Rollback or follow-up required:

Keep real identifiers and sensitive notes outside the repository.
