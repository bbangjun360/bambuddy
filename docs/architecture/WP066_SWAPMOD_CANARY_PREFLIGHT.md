# WP-066 SwapMod Canary Preflight

## Status

WP-066 adds a default-off canary preflight boundary for one reviewed WP-065
SwapMod dry-run candidate. It packages redacted review evidence only. It does
not approve real A1 Mini hardware execution.

No printer command, upload, print start, queue dispatch, scheduler dispatch,
ERP write, Obico mutation, or bed automation mutation is performed by this
boundary.

## Implemented Boundary

Service:

- `backend/app/services/swapmod_canary_preflight.py`

Schema:

- `backend/app/schemas/swapmod_canary_preflight.py`

Routes:

- `GET /api/v1/plate-change-3mf/swapmod-canary-preflight/status`
- `POST /api/v1/plate-change-3mf/swapmod-canary-preflight/packages`

Config defaults:

- `FARM_SWAPMOD_CANARY_PREFLIGHT_ENABLED=false`
- `FARM_SWAPMOD_CANARY_PREFLIGHT_REQUIRE_HUMAN_CONFIRMATION=true`
- `FARM_SWAPMOD_CANARY_PREFLIGHT_SINGLE_PRINTER_ONLY=true`

## Request Contract

The package request accepts one redacted WP-065 dry-run plan, one candidate id,
one target printer id, explicit `A1 Mini` model-family scope, one complete
operator checklist, and this exact confirmation phrase:

```text
CONFIRM_SWAPMOD_CANARY_PREFLIGHT <printer_id> <candidate_id> <line_range_hash>
```

The checklist requires all of these fields to be true:

- `operator_present`
- `printer_visible`
- `emergency_stop_ready`
- `power_cutoff_ready`
- `bed_clear_confirmed`
- `correct_plate_confirmed`
- `no_other_job_running`
- `swapmod_hardware_installed`
- `plate_stack_loaded`
- `original_print_finished`
- `bed_state_reviewed`

The schema forbids extra top-level request fields. The service also rejects
raw command-like fields inside the supplied dry-run plan by keeping the package
in `SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED`.

## Response Contract

A ready response returns:

- `status=SWAPMOD_CANARY_PREFLIGHT_READY`
- `mode=CANARY_PREFLIGHT_ONLY`
- a deterministic redacted package id
- target printer id only
- selected candidate id, kind, line count, line range hash, and command-family counts
- checklist summary
- stop conditions for a later hardware Work Package
- workflow trace ending at `STOP_BEFORE_REAL_EXECUTION`
- all no-execution flags set false
- all side-effect sentinels set to zero

A non-ready response returns `SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED`, review
reasons, no package id, and the same no-execution flags.

## Safety Invariants

WP-066 must not import or call printer manager, Bambu MQTT, FTPS helpers, queue
or scheduler paths, ERP, Obico, or bed automation mutation modules. It must not
expose raw command, send-gcode, execute-gcode, upload, start, or next-print
endpoints. It does not create durable resume state. Restart cannot resume any
physical action from a preflight package.

The preflight package is process-local review evidence only. A later real
hardware Work Package must still define a named canary printer, one attempt, no
retry, exact confirmations, emergency stop/power cutoff, manual recovery, and
no next print before bed READY.

## Test Coverage

Focused coverage includes default-disabled status, safe package creation,
non-ready dry-run plans, missing candidates, non-A1 Mini scope, exact phrase
mismatch, incomplete checklist, nested raw command-like fields, forbidden import
scans, mock-service route scans, and API schema rejection of raw top-level
fields.

## Rollback

There is no migration. Rollback is a file-level revert of the WP-066 config,
schema, service, route, tests, Make target, architecture doc, runbook, and
Work Package updates. Operational rollback is to leave
`FARM_SWAPMOD_CANARY_PREFLIGHT_ENABLED=false`.
