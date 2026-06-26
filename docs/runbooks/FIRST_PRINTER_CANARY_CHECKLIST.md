# First Printer Plate-Change Canary Checklist

## Purpose

This checklist is a planning artifact for a future supervised plate-change
canary. It is not a command procedure and does not authorize real hardware
movement.

PrintFlow and SwapMod are treated as 3MF/G-code post-processing workflows, not
remote control servers. The legacy external adapter canary is pending redesign
and must not be used for live operation.

## Canary Identity Rules

- Use sanitized aliases in repo material, such as `CANARY_PRINTER_A`.
- Store real printer names, serial numbers, access codes, locations, and device
  mappings only in the approved private operations record.
- Do not copy production URLs, IP addresses, customer names, or secrets into
  this checklist.
- Keep the canary set to one printer until a later rollout Work Package changes
  the policy.

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
- [ ] Stop if `FARM_PRINTFLOW_BASE_URL` or `FARM_PRINTFLOW_API_TOKEN` is set,
      especially if either value resembles a printer IP, access code, serial,
      production URL, or fake PrintFlow server.

## Legacy External Adapter Hold Point

The legacy `/real-canary-runs` endpoint is deprecated/pending redesign. It must
return a blocked audit response and must not construct an external adapter. Do
not use it for live operation.

## Future 3MF Post-Process Hold Point

Before a later 3MF post-process implementation can be considered:

- [ ] Input `.3mf` fixture selected.
- [ ] Plate-change G-code injection location reviewed.
- [ ] Modified `.3mf` output is deterministic.
- [ ] Extraction and diff tests prove only expected G-code changed.
- [ ] The resulting file is sent or started only through the existing Bambuddy
      flow.
- [ ] No external module receives printer credentials.

## Future Bambuddy-Native Direct Command Hold Point

Before a later direct supervised command implementation can be considered:

- [ ] Operator selects exactly one printer.
- [ ] Operator confirms bed and plate state.
- [ ] Command is one predefined allowlisted G-code sequence.
- [ ] No arbitrary G-code endpoint exists.
- [ ] No scheduler path can trigger the command.
- [ ] No queue auto-dispatch can trigger the command.
- [ ] No repeat or automatic retry exists.
- [ ] Audit log records operator, printer, command identifier, confirmation,
      timestamp, and result.
- [ ] Hardware canary evidence is complete before enabling.

## Physical Readiness Hold Point

The following checks are required before a separate physical canary request can
be considered. They still do not authorize motion.

- [ ] The named physical printer is idle, not running, not paused, not
      preparing, and not dispatching.
- [ ] The bed is visually inspected by a human.
- [ ] The safety observer can reach the emergency stop path.
- [ ] Emergency stop or power cutoff is accessible before any real
      hardware-affecting request is considered.
- [ ] The operator has a manual recovery path for uncertain bed state.
- [ ] Non-production material and a non-customer test artifact are selected in
      private operator records.
- [ ] No production credentials or customer data are needed for the canary.
- [ ] Network access is restricted to the approved local test environment.
- [ ] A rollback path is documented without deleting volumes or audit evidence.

## Observation Rules for Any Later Approved Canary

If a separate approval authorizes a real canary, keep these rules visible to the
human team:

- One canary printer only.
- One bed or plate-change action at a time.
- No automatic retry after timeout, lost acknowledgement, restart, unknown state,
  manual interruption, or post-check failure.
- No next print until Bambuddy records bed state `READY`.
- Any uncertain state becomes `MANUAL_REVIEW`.
- Any stop condition halts rollout and preserves logs.

## Result Record

Record the result with sanitized values only:

- Run identifier:
- Sanitized printer alias:
- Dry-run evidence bundle:
- Human gate status:
- Stop condition encountered:
- Resolution owner:
- Rollback or follow-up required:

Keep real identifiers and sensitive notes outside the repository.
