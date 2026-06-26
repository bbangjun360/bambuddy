# WP-060 Plate-Change Stop Conditions

## Purpose

These stop conditions apply to WP-060 mock readiness, corrected architecture
work, and any later separately approved plate-change canary. This PR must not
execute a real canary, call a fake PrintFlow server, or send a printer command.

## Immediate Stop Conditions

Stop immediately if any of the following occur:

- Anyone attempts to use PrintFlow or SwapMod as a remote control server.
- `FARM_PRINTFLOW_BASE_URL` or `FARM_PRINTFLOW_API_TOKEN` is set for live
  operation.
- A Bambu printer IP address, access code, serial number, local printer URL,
  production URL, or fake PrintFlow server endpoint is used as a PrintFlow base
  URL.
- The legacy `/real-canary-runs` path constructs an adapter, makes a network
  call, or returns anything other than a blocked pending-redesign result.
- A real printer, ERPNext instance, Obico instance, Bambu MQTT service, FTPS
  service, or hardware interface receives an unexpected command.
- Queue, scheduler, ERP, Obico, or bed side effects occur during readiness or
  dry-run evidence collection.
- A non-dry-run path is enabled without explicit approval.
- A feature flag that should be default-off is enabled unexpectedly.
- A general arbitrary G-code endpoint is introduced or exposed.
- Direct Bambu MQTT or FTPS access is added outside Bambuddy authority.
- A leaked secret, token, access code, serial number, production URL, real
  network address, printer identifier, or customer datum appears in logs,
  fixtures, checklists, commits, or PR text.
- Bambuddy fails to start or loses the ability to record state transitions.
- The operator or safety observer is unavailable for a physical canary decision.

## Future 3MF Post-Process Stops

Stop a future 3MF post-process path if:

- The input is not a reviewed `.3mf` fixture or approved artifact.
- The output is not a deterministic modified `.3mf`.
- Extraction or diff tests cannot prove the expected G-code change.
- The modified artifact bypasses the existing Bambuddy flow.
- The transformation requires printer credentials or customer data.

## Future Direct Command Stops

Stop a future Bambuddy-native direct command path if:

- More than one printer is selected.
- The operator has not confirmed bed and plate state.
- The command is not one predefined allowlisted G-code sequence.
- Any arbitrary G-code input is accepted.
- A scheduler, queue, retry, or repeat path can trigger the command.
- Audit logging is missing or incomplete.
- Hardware canary evidence is missing before enabling.

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

- ERPNext attempts to control a printer or plate-change device.
- ERP inventory or accounting writes are not idempotent.
- ERP writes are not Draft-only during readiness work.
- Obico attempts to control the printer instead of notify-only behavior.
- Any downstream failure causes automatic printer or bed action.

## Emergency Stop and Rollback Requirements

For any later approved physical canary, stop before the request if the operator
cannot reach an emergency stop or power cutoff. Stop before the request if the
rollback path is unknown, unassigned, or would delete logs, metrics,
screenshots, harness artifacts, or audit evidence.

Rollback must preserve evidence and leave any uncertain printer or bed state in
manual review until a human resolves it.

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
