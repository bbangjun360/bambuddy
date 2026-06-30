# WP-076 SwapMod A1 Mini Direct Canary Design

## Goal

Add a default-off Bambuddy-owned direct canary boundary for A1 Mini SwapMod
plate-change transport. This is for tomorrow's supervised physical test setup;
it must not send any command until the operator enables the flags and submits
the exact phrase and checklist.

## WP-06x vs WP-07x

WP-06x proves 3MF artifact review and one supervised upload/start attempt.
It does not control plate-change motion directly.

WP-07x proves the SwapMod runtime flow: operator trigger, release/load states,
verification, dry-run transport, and dry-run execution gate. It intentionally
does not import printer control or send commands.

The missing slice is a narrow WP-07x follow-on: convert one state-machine
transport step into an A1 Mini direct canary command using a server-side
allowlisted sequence file. The API must accept only a step id, printer id,
checklist, and exact phrase. It must never accept raw G-code or an arbitrary
path.

## Design

Create a separate route/service/schema so the existing WP-075 dry-run state
machine remains unchanged and its architecture tests still prove no control
transport is present there.

The new route exposes:

- `GET /api/v1/swapmod-a1-mini-direct-canary/status`
- `POST /api/v1/swapmod-a1-mini-direct-canary/cycles/{cycle_key}/transport-steps`

The route requires:

- feature enabled;
- real command flag explicitly enabled;
- one A1 Mini printer id;
- current SwapMod cycle state matching the requested step:
  `READY_TO_RELEASE` for `RELEASE_PLATE`, `READY_TO_LOAD` for `LOAD_NEXT_PLATE`;
- current printer state known idle: `IDLE` or terminal `FINISH` with no active
  file;
- server-side configured sequence file for the requested step;
- SHA-256 of that file matching the configured hash;
- exact operator phrase:
  `CONFIRM_A1_MINI_DIRECT_PLATE_CHANGE <printer_id> <cycle_key> <step> <sha256>`;
- all checklist fields true.

On success, Bambuddy reads the configured sequence file and sends it through
the existing in-process printer client as one fixed command payload. It then
advances the state machine to the relevant verification state. On send failure,
it moves the cycle to a blocked/manual-review state and does not retry.

## Safety

- Default-off flags block the route.
- Existing WP-075 dry-run transport remains non-real.
- API schemas forbid extra fields, including raw command fields.
- No queue, scheduler, upload, print start, ERP, Obico, or bed automation
  mutation is called.
- No automatic retry is implemented.
- Raw command content is never returned in responses.
- Sequence files are not committed and must live outside the repository.

## Test Scope

Add unit tests for gate validation, SHA validation, state matching, successful
send, and send failure. Add API tests for default-off behavior, schema rejection,
and mocked successful transport. Add architecture and harness checks proving
the new route is explicit and the old WP-075 boundary remains unchanged.
