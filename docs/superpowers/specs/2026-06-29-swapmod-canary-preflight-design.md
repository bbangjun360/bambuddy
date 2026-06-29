# WP-066 SwapMod Canary Preflight Design

## Goal

Build the next safe boundary after WP-065: a default-off SwapMod canary
preflight workflow that turns one reviewed dry-run candidate into a redacted,
human-reviewable canary package without sending printer commands.

WP-066 does not execute G-code, upload files, start prints, dispatch queue work,
mutate bed automation state, subscribe to live printer events, or resume
physical actions after restart. It exists to prove that the operator, printer,
candidate, checklist, and stop-condition contract is explicit before any later
real A1 Mini hardware attempt.

## Context

WP-065 can compare an original 3MF with a SwapMod-generated 3MF and return
redacted candidate blocks. WP-063 research says the SwapMod A1 Mini sequence is
not safe as a standalone command because it depends on the preceding print-end
state, coordinate mode, homing state, bed location, SwapMod hardware, plate
stack, and firmware behavior. WP-064-D already provides a pattern for
supervised physical 3MF upload/start with exact confirmation phrases, one
printer, one artifact, one attempt, no retry, and redacted responses.

The desired end-to-end system is still: print the original job, observe finish,
use a reviewed SwapMod-derived plate-change candidate, verify the bed state,
and only then allow the next print. WP-066 prepares that contract; it does not
perform the live action.

## Scope

WP-066 implements a planning boundary only:

- default-off config for SwapMod canary preflight;
- a strict request schema for one dry-run result, one candidate id, one target
  printer id, and one checklist;
- service logic that accepts only `SWAPMOD_DRY_RUN_READY` dry-run summaries;
- candidate validation by id, kind, line range hash, line count, command-family
  counts, and A1 Mini model-family expectation;
- explicit operator confirmation phrase generation and verification;
- redacted canary package output with no raw G-code and no local absolute paths;
- status flags showing real execution is not supported by this Work Package;
- architecture and API tests proving no live-control imports or side effects.

Out of scope:

- Bambu MQTT, FTPS, printer manager, raw G-code, upload, print start, pause,
  cancel, resume, queue dispatch, scheduler dispatch, ERP, Obico, bed automation
  mutation, retry, restart resume, or next-print automation;
- committed 3MF/G-code artifacts, printer IPs, access codes, serial numbers,
  production tokens, logs, or customer data;
- real A1 Mini canary execution.

## API Shape

Add a route under the existing plate-change 3MF area:

- `GET /api/v1/plate-change-3mf/swapmod-canary-preflight/status`
- `POST /api/v1/plate-change-3mf/swapmod-canary-preflight/packages`

The package request contains:

- `dry_run_plan`: the redacted WP-065 response object;
- `candidate_id`: one candidate block id from that plan;
- `target_printer_id`: one Bambuddy printer id as a string;
- `expected_printer_model_family`: must be `A1 Mini` for this Work Package;
- `checklist`: operator, visibility, emergency stop, power cutoff, bed clear,
  correct plate, no other job running, SwapMod hardware installed, plate stack
  loaded, original print finished, and bed state reviewed;
- `operator_confirmation_phrase`: exact phrase proving the operator reviewed
  the package request.

The expected confirmation format is:

```text
CONFIRM_SWAPMOD_CANARY_PREFLIGHT <printer_id> <candidate_id> <line_range_hash>
```

The response contains:

- `status`: `SWAPMOD_CANARY_PREFLIGHT_READY` or
  `SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED`;
- `mode`: `CANARY_PREFLIGHT_ONLY`;
- one redacted package id;
- target printer id only, never IP/access code/serial;
- selected candidate kind, line count, line range hash, and command-family
  counts;
- checklist summary and review reasons;
- stop conditions for a later real canary;
- `real_execution_supported=false`;
- `printer_command_supported=false`;
- `printer_upload_supported=false`;
- `printer_start_supported=false`;
- zeroed side-effect sentinels.

The schema forbids extra fields. Raw command-like fields such as `raw_gcode`,
`gcode`, `command`, `send_gcode`, `execute_gcode`, `queue_action`,
`scheduler_action`, and `printer_action` are rejected.

## State Flow

The preflight service records only deterministic review state:

1. `RECEIVE_REDACTED_DRY_RUN_PLAN`
2. `SELECT_ONE_CANDIDATE`
3. `VERIFY_A1_MINI_SCOPE`
4. `VERIFY_OPERATOR_CHECKLIST`
5. `VERIFY_EXACT_CONFIRMATION`
6. `PACKAGE_FOR_MANUAL_REVIEW`
7. `STOP_BEFORE_REAL_EXECUTION`

Any missing or false checklist field, ambiguous dry-run status, missing
candidate, non-A1 Mini scope, confirmation mismatch, or raw-command field keeps
the result in manual review and returns no executable approval.

## Safety Rules

- The service consumes redacted summaries only and never requires raw G-code.
- Candidate hashes are review identifiers, not hardware approval.
- No code path calls printer manager, Bambu MQTT, FTPS helpers, queue,
  scheduler, ERP, Obico, or bed automation mutation modules.
- The package is process-local review evidence, not a durable resume token.
- Restarting Bambuddy cannot resume any physical action from a preflight result.
- A later real canary still needs its own Work Package, exact confirmation
  phrases, named canary printer, emergency stop/power cutoff procedure, and bed
  READY verification before next print.

## Tests

Focused tests cover:

- default-disabled status;
- dry-run plan status must be `SWAPMOD_DRY_RUN_READY`;
- candidate id must exist exactly once;
- checklist fields must all be true;
- A1 Mini model family must be explicit;
- exact confirmation phrase must match printer id, candidate id, and hash;
- schema rejects raw G-code and command fields;
- ambiguous dry-run plans remain review-required;
- response redacts raw paths, printer credentials, serials, and command text;
- forbidden side-effect sentinels remain zero;
- architecture scan has no live-control imports or execution method calls;
- harness target proves no external mock service exposes SwapMod hardware routes.

## Rollback

There is no migration. Rollback is a file-level revert of the WP-066 config,
schema, route, service, tests, Make target, architecture doc, runbook, and
workpack changes. Operational rollback is to leave
`FARM_SWAPMOD_CANARY_PREFLIGHT_ENABLED=false`.

## Done

WP-066 is done when the preflight endpoint can package one synthetic WP-065
candidate for manual review, all failure paths block safely, no live-control
path exists, focused tests pass, `make verify-fast` passes, and the workpack
records validation evidence.
