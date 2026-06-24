# PrintFlow Canary Stop Conditions

## Purpose

These stop conditions apply to WP-060 canary readiness, mock harness dry-runs,
and any later separately approved physical canary. When a stop condition is met,
halt canary preparation or rollout, preserve evidence, and move the affected
printer or bed-cycle record to manual review where applicable.

## Immediate Stop Conditions

Stop immediately if any of the following occur:

- A real printer, PrintFlow device, ERPNext instance, Obico instance, Bambu MQTT
  service, FTPS service, or hardware interface receives an unexpected command.
- A non-dry-run path is enabled without explicit approval.
- A feature flag that should be default-off is enabled unexpectedly.
- Any log, fixture, checklist, commit, or PR text contains a secret, access
  code, serial number, production URL, real network address, or customer data.
- Any external module attempts to control a printer or connect directly to Bambu
  MQTT or FTPS.
- A general arbitrary G-code endpoint is introduced or exposed.
- Bambuddy fails to start or loses the ability to record state transitions.
- The operator or safety observer is unavailable for a physical canary decision.

## Printer and Bed State Stops

Stop if the candidate printer or bed state is uncertain:

- Printer is `RUNNING`, `PAUSED`, `PREPARING`, dispatching, or otherwise not
  idle.
- Bed state is not verified `READY` before any next-print decision.
- Object remains after a simulated or approved bed action.
- Camera, sensor, or post-check evidence is unavailable when required.
- Temperature, cooldown, or material condition is outside the approved policy.
- Manual inspection disagrees with system state.
- Emergency stop status is active, unknown, or untested.

## Adapter and Harness Stops

Stop if the adapter or mock harness shows unsafe behavior:

- Timeout before acknowledgement.
- Acknowledgement lost after possible execution.
- Adapter heartbeat loss.
- Duplicate command creates duplicate side effects.
- Duplicate callback changes an already finalized result.
- Adapter reports success but post-check fails.
- Process restart occurs during `EXECUTING` or `VERIFYING`.
- Restart recovery resumes physical action automatically.
- Unknown adapter state is treated as success.
- Mock harness scenario becomes nondeterministic.

## ERP, Obico, and Downstream Stops

Stop if downstream systems cross their allowed boundary:

- ERPNext attempts to control a printer or PrintFlow device.
- ERP inventory or accounting writes are not idempotent.
- ERP writes are not Draft-only during readiness work.
- Obico attempts to control the printer instead of notify-only behavior.
- Any downstream failure causes automatic printer or bed action.

## Required Stop Response

When a stop condition is met:

- [ ] Halt canary preparation or rollout.
- [ ] Do not retry automatically.
- [ ] Do not start the next print.
- [ ] Preserve logs, metrics, screenshots, and harness artifacts.
- [ ] Redact secrets and real identifiers before sharing evidence.
- [ ] Mark the affected cycle, printer, or checklist as `MANUAL_REVIEW` where
      the system supports it.
- [ ] Assign a human owner for resolution.
- [ ] Record whether rollback is needed.
- [ ] Re-run the relevant mock or dry-run evidence after the fix.

## Restart Rule

Never automatically resume an uncertain physical bed action after restart. A
cycle interrupted during execution, verification, timeout handling, lost
acknowledgement, or manual interruption must require human review before any
further action.

## Rollout Rule

A stopped canary cannot be expanded to additional printers. Expansion requires a
new evidence package, human approval, and a later Work Package or rollout record
that explicitly names the changed scope with sanitized aliases.
