# WP-063 Bambuddy-Native Plate-Change Command Boundary

## Status

Implemented as WP-063-A dry-run research boundary on 2026-06-25.
This document does not authorize real printer movement or any hardware canary.

## Context

PrintFlow and SwapMod are treated as 3MF/G-code post-processing workflows, not
remote control servers. The direction for a later direct command path is
Bambuddy-native and supervised: one operator, one selected printer, one reviewed
allowlisted command sequence, and no arbitrary command input.

WP-063-A implements only the dry-run API boundary and architecture evidence. It
must not send a real printer command.

## Existing Command Paths Inspected

- `backend/app/services/bambu_mqtt.py`: `BambuMQTTClient.start_print()` publishes
  the existing `project_file` command. `stop_print()`, `pause_print()`, and
  `resume_print()` publish direct printer control commands. `send_gcode()` is the
  internal generic command emitter used by several specific helpers.
- `backend/app/services/printer_manager.py`: `PrinterManager.start_print()` logs
  and delegates to the active `BambuMQTTClient`. `PrinterManager.stop_print()`
  delegates to the client stop path. It is the central in-process owner for live
  Bambuddy printer clients.
- `backend/app/api/routes/printers.py`: existing stop, pause, and resume routes
  fetch the active MQTT client and call the client methods directly. Existing
  bed-jog and home-axes routes compute predefined movement commands from typed
  query parameters and call the client command emitter. `clear-plate` only clears
  Bambuddy's awaiting-plate-clear flag and does not emit a printer command.
- `backend/app/services/print_scheduler.py`: queue dispatch uploads a file over
  FTPS with `upload_file_async()` and then calls `printer_manager.start_print()`.
  It also maintains dispatch holds so the same printer does not receive multiple
  queue starts while a prior command is being digested.
- `backend/app/services/background_dispatch.py`: direct reprint/library dispatch
  also uploads over FTPS, registers the expected print, and calls
  `printer_manager.start_print()`.
- `backend/app/api/routes/print_queue.py`: stopping an active queue item calls
  `printer_manager.stop_print()`. Starting a staged queue item only clears queue
  gates so the scheduler can dispatch later.
- `backend/app/services/printflow_canary.py` and `backend/app/api/routes/printflow_canary.py`:
  the prior external PrintFlow server adapter is blocked as pending redesign and
  remains useful only as a dry-run safety pattern.
- Tests inspected include `backend/tests/unit/test_bed_jog.py`,
  `backend/tests/unit/services/test_bambu_mqtt.py`,
  `backend/tests/unit/services/test_printer_manager.py`,
  `backend/tests/integration/test_printers_api.py`, and the WP-060 canary tests.

## Future Attachment Point

A future real plate-change command should attach through a dedicated
Bambuddy-native service, not through PrintFlow, SwapMod, the scheduler, the
queue, background dispatch, FTPS upload, or a route that accepts command text.

The safest existing live transport is the Bambuddy-owned printer manager and its
active `BambuMQTTClient`, because that is where Bambuddy already holds printer
connection state and credentials. A later implementation should add a narrow
printer-manager method such as an allowlisted plate-change sequence executor,
then call the existing client command transport only from that method. The route
must continue to accept only enum sequence identifiers and human approval data.

WP-063-A does not call that transport. It adds an independent dry-run service and
route that return an auditable plan with all action fields set to `None` and all
forbidden side-effect sentinels at zero.

## Implemented Dry-Run Boundary

Routes:

- `POST /api/v1/plate-change/dry-run-commands`
- `GET /api/v1/plate-change/status`

Config flags:

- `FARM_PLATE_CHANGE_COMMAND_ENABLED=false`
- `FARM_PLATE_CHANGE_COMMAND_DRY_RUN=true`
- `FARM_PLATE_CHANGE_HUMAN_APPROVAL_REQUIRED=true`
- `FARM_PLATE_CHANGE_SINGLE_PRINTER_ONLY=true`
- `FARM_PLATE_CHANGE_ALLOW_REAL_COMMANDS=false`

Accepted request shape:

- `idempotency_key`
- `target_printer_ids`, which must contain exactly one sanitized printer alias
- `command_sequence`, currently only `supervised_plate_change_v1`
- `dry_run=true`
- `operator_approved=true`
- `operator_approval_phrase`, exactly
  `CONFIRM_DRY_RUN_PLATE_CHANGE <printer-alias> <command-sequence>`
- optional metadata, stored only as a fingerprint in the response

The schema forbids extra fields, so a body field such as `gcode` is rejected by
validation instead of being ignored.

## Forbidden Boundaries

The WP-063-A implementation must not:

- call Bambu MQTT command methods;
- call FTPS upload, download, or delete helpers;
- import or call `printer_manager`;
- touch `PrintQueueItem`, `PrintLogEntry`, `BedAutomationCycle`, or ERP draft
  write models;
- call scheduler or background dispatch services;
- mutate Obico shadow records;
- accept arbitrary command text;
- accept multiple printers;
- implement real execution, retry, queue dispatch, scheduler dispatch, or
  automatic restart recovery.

## Hardware-Free Test Coverage

The following can be tested without hardware:

- default-disabled POST behavior;
- status flag reporting;
- dry-run-only gate;
- human approval and exact phrase gates;
- single-printer gate;
- enum-only command sequence validation;
- schema rejection of arbitrary command body fields;
- idempotent dry-run response storage;
- action fields remain `None`;
- sentinel counters remain zero;
- integration tests patch common printer, FTPS, scheduler, queue dispatch, ERP,
  Obico, and bed paths and assert they are not called;
- architecture tests verify the WP-063 files do not import live command or
  mutation modules.

## Human-Supervised Canary Later

A later Work Package is required before real execution. That Work Package must
produce separate evidence for:

- exact reviewed command sequence content;
- a dedicated printer-manager execution method;
- audit storage with operator, printer alias, sequence id, phrase, timestamp,
  and result;
- physical idle-state verification;
- emergency stop and power cutoff availability;
- one named canary printer, represented only by a sanitized alias in repo files;
- no retry after timeout, restart, lost acknowledgement, manual interruption, or
  uncertain state;
- no next print until the bed state is verified `READY`;
- human checklist completion and stop-condition review.

## Rollback

Rollback is a file-level revert of the WP-063-A route, schema, service, tests,
Makefile target, docs, and ExecPlan. There is no migration and no persistent
state outside the process-local dry-run records.
