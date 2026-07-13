# WP-076 SwapMod A1 Mini Direct Canary Runbook

## Purpose

Run one supervised A1 Mini direct plate-change transport step through Bambuddy.
This is not a general command endpoint and not a queue or scheduler path.

## Required Configuration

All flags are default-off. Enable only for the named canary printer session:

```bash
FARM_SWAPMOD_STATE_MACHINE_ENABLED=true
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=true
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=true
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_TARGET_PRINTER_ID=<bambuddy_printer_id>
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_SEQUENCE_ROOT=/path/outside/repo
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_RELEASE_SEQUENCE_FILE=release.gcode
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_RELEASE_SEQUENCE_SHA256=<sha256>
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_LOAD_SEQUENCE_FILE=load.gcode
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_LOAD_SEQUENCE_SHA256=<sha256>
```

The target printer ID must identify the named A1 Mini canary for this session.
Requests for any other printer fail closed. The sequence root must be outside
the repository. Sequence files are server-side allowlisted files; the API
never accepts raw G-code or a path.

Bambuddy reads the selected sequence once, verifies that exact byte snapshot
against the configured SHA-256, requires UTF-8, and sends only the verified
snapshot. It serializes the named printer in the database and commits the active
SwapMod state before calling the printer transport.

## Checklist

Every field must be true before a direct transport request:

- `operator_present`
- `printer_visible`
- `emergency_stop_ready`
- `power_cutoff_ready`
- `a1_mini_confirmed`
- `swapmod_hardware_installed`
- `bed_area_clear`
- `plate_stack_ready`
- `no_other_job_running`
- `dry_run_gate_reviewed`

## Procedure

1. Confirm the printer is the A1 Mini canary and visible to the operator.
2. Confirm emergency stop and power cutoff are reachable.
3. Confirm the SwapMod hardware and plate stack are physically installed and
   aligned.
4. Confirm Bambuddy reports no active file and a known idle state.
5. Create or locate a SwapMod cycle and move it to the state matching the step:
   `READY_TO_RELEASE` for `RELEASE_PLATE`, or `READY_TO_LOAD` for
   `LOAD_NEXT_PLATE`.
6. Verify the configured sequence SHA-256.
7. Use the exact phrase:

```text
CONFIRM_A1_MINI_DIRECT_PLATE_CHANGE <printer_id> <cycle_key> <step> <sequence_sha256>
```

8. Submit the direct canary request. Bambuddy must return only after it has
   durably claimed the step; concurrent requests for the same printer are
   rejected after the winning request changes the cycle from its ready state.
9. Monitor physically. Do not retry from software if motion is uncertain or the
   request fails.
10. After motion, perform manual/camera verification through the existing
    SwapMod state-machine verification endpoint.

## Stop Conditions

Stop immediately if any of these occur:

- any direct canary flag is not explicitly enabled for the session;
- the named canary printer ID is missing or does not match the request;
- another cycle since the most recent completed cycle still requires review;
- the configured sequence SHA-256 does not match;
- the sequence cannot be read as the same verified UTF-8 byte snapshot;
- the printer is not A1 Mini;
- Bambuddy shows an active file or non-idle state;
- any checklist field is false;
- the phrase does not exactly match;
- the response reports `COMMAND_FAILED`;
- the transport or verification response is missing, interrupted, or does not
  prove that the cycle reached its expected next state;
- another concurrent request reports that the cycle is no longer in its required
  ready state;
- physical motion is uncertain, interrupted, or unexpected;
- any route attempts queue, scheduler, upload/start, raw command, multi-printer,
  automatic retry, or next-print automation.

## Rollback

Set either flag false and restart Bambuddy if needed:

```bash
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ENABLED=false
FARM_SWAPMOD_A1MINI_DIRECT_CANARY_ALLOW_REAL_COMMANDS=false
```

There is no migration and no automatic resume after restart. Disabling the flags
does not reset an already active or uncertain cycle. Inspect the named printer,
leave the cycle blocked from retry, and complete the existing manual
reconciliation/verification procedure before any new physical request.
