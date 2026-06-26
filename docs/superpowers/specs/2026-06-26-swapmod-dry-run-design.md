# WP-065 SwapMod Dry-Run Workflow Design

## Goal

Build a Bambuddy-owned dry-run workflow that compares an original A1 Mini 3MF
with a SwapMod-generated 3MF, identifies reviewable plate-change candidate
blocks without exposing raw G-code, and simulates the post-print workflow that a
future real canary will execute.

The real A1 Mini canary is intentionally a later Work Package. WP-065 must not
send printer commands, upload files, start prints, clear plate gates, dispatch
queue items, or expose arbitrary G-code.

## Context

The current WP-064-D boundary can upload one reviewed 3MF artifact to one
canary printer and start it once under human supervision. It does not extract
SwapMod G-code, react to print completion, control the bed plate, or start the
next print.

Existing research in `docs/architecture/WP063_A1_MINI_PLATE_CHANGE_GCODE_REVIEW.md`
shows that SwapMod output is a modified print-job workflow. It includes
plate-load, inter-job swap, duplicated print-job, and final-swap behavior. The
inter-job swap block depends on the preceding print-end state, coordinate mode,
homing state, installed SwapMod hardware, plate stack state, and firmware
behavior. That makes direct execution a future canary activity, not a WP-065
implementation detail.

## Scope

WP-065 implements:

- default-off configuration for SwapMod dry-run analysis;
- a service that accepts one original 3MF and one SwapMod 3MF under controlled
  roots;
- internal 3MF G-code member discovery and deterministic comparison;
- candidate block summaries for plate-load, inter-job swap, and final-swap
  windows when the structure is unambiguous;
- redacted block fingerprints, line counts, command-family counts, and safety
  notes;
- a dry-run workflow trace:
  `WAIT_ORIGINAL_FINISH -> EXTRACT_REVIEWED_SWAP_BLOCK -> MANUAL_REVIEW_REQUIRED -> WOULD_SEND_ALLOWLISTED_SEQUENCE -> WOULD_START_NEXT_PRINT`;
- API and harness tests proving there are no printer, queue, scheduler, MQTT,
  FTPS, raw G-code, ERP, Obico, or bed automation side effects.

WP-065 excludes:

- real printer commands;
- direct Bambu MQTT or FTPS use;
- upload/start calls;
- queue or scheduler dispatch;
- bed-ready mutation;
- raw G-code request or response fields;
- automatic retry;
- software resume after restart;
- real A1 Mini hardware canary execution.

## API Shape

Add a new route boundary under the existing plate-change 3MF area:

- `GET /api/v1/plate-change-3mf/swapmod-dry-run/status`
- `POST /api/v1/plate-change-3mf/swapmod-dry-run/plans`

The request body contains:

- `original_path`: local original `.3mf` path;
- `swapmod_path`: local SwapMod `.3mf` path;
- `dry_run`: must be `true`;
- `expected_printer_model_family`: optional string, initially informational.

The schema forbids extra fields. Field names such as `raw_gcode`, `gcode`,
`command`, `send_gcode`, `execute_gcode`, `queue_action`, `scheduler_action`,
and `printer_action` are rejected by schema validation.

The response contains:

- `status`: `SWAPMOD_DRY_RUN_READY` or `SWAPMOD_DRY_RUN_REVIEW_REQUIRED`;
- `mode`: `DRY_RUN_ONLY`;
- redacted source names and SHA-256 hashes;
- discovered internal G-code member names;
- `candidate_blocks`, each with:
  - `candidate_id`;
  - `candidate_kind`: `plate_load_only`, `inter_job_swap`, or `final_swap`;
  - `line_count`;
  - `line_range_hash`;
  - `command_family_counts`;
  - `review_required=true`;
  - `raw_gcode_included=false`;
- `workflow_trace` with dry-run-only states;
- `real_execution_supported=false`;
- `printer_upload_supported=false`;
- `printer_start_supported=false`;
- all forbidden side-effect sentinels at zero.

No response includes raw full G-code, printer IPs, access codes, serial numbers,
local absolute paths, tokens, customer data, or arbitrary command text.

## Extraction Strategy

The first implementation is conservative and deterministic:

1. Read only `.gcode` members from both 3MF ZIP files.
2. Select the first matching G-code member pair for this WP.
3. Normalize line endings but do not alter command text.
4. Locate exact occurrences of the original G-code line sequence inside the
   SwapMod G-code.
5. If two exact original-job occurrences are found, classify:
   - lines before the first occurrence as `plate_load_only`;
   - lines between the first and second occurrence as `inter_job_swap`;
   - lines after the second occurrence as `final_swap`.
6. If the structure is not exact, return `SWAPMOD_DRY_RUN_REVIEW_REQUIRED` with
   a redacted reason and no executable approval.

This intentionally starts narrower than the observed real SwapMod sample, where
some completion lines can be modified. The purpose is to establish the safe
boundary, contracts, and failure behavior first. Broader fuzzy matching can be a
later Work Package after the exact-match slice is tested.

## State Machine

WP-065 does not subscribe to live printer events. It returns the workflow that a
future canary will execute:

1. `WAIT_ORIGINAL_FINISH`: observe original print completion.
2. `EXTRACT_REVIEWED_SWAP_BLOCK`: select the reviewed block id from the dry-run
   plan.
3. `MANUAL_REVIEW_REQUIRED`: require an operator to review the fingerprinted
   candidate.
4. `WOULD_SEND_ALLOWLISTED_SEQUENCE`: dry-run placeholder for a future
   Bambuddy-owned allowlisted executor.
5. `WOULD_START_NEXT_PRINT`: dry-run placeholder that is only reachable after a
   future bed READY verification.

The future WP-066 real canary must convert these dry-run states into a
human-gated runtime with one printer, one allowlisted block, one attempt, exact
confirmation phrases, no retry, and no next print before bed READY.

## Safety Rules

- Bambuddy remains the sole owner of future printer state-changing commands.
- External modules do not receive printer credentials.
- No arbitrary G-code endpoint is introduced.
- Raw G-code is never accepted from the API and never returned.
- Candidate block hashes are stable enough for review but not sufficient for
  hardware approval by themselves.
- Any ambiguous extraction result remains manual-review only.
- A restart does not resume any physical action because WP-065 has no physical
  action.

## Tests

Focused tests cover:

- default-disabled status;
- schema rejection of raw command fields;
- controlled path guards and repository-path rejection;
- invalid 3MF rejection;
- no-G-code-member rejection;
- exact synthetic original/swapmod pair producing three redacted candidates;
- ambiguous pair returning review-required without approval;
- command-family count redaction;
- workflow trace content;
- no forbidden side-effect sentinels;
- route integration with mocks only;
- architecture checks proving no imports of printer manager, Bambu MQTT, FTPS,
  queue dispatch, scheduler dispatch, ERP, Obico, or bed automation mutation.

## Rollback

There is no migration. Rollback is a file-level revert of the WP-065 config,
schemas, service, route, tests, Make target, architecture/runbook docs, and
Work Package. Operational rollback is to leave the new feature flag disabled.

## Done

WP-065 is done when:

- the dry-run endpoint can summarize a synthetic SwapMod-style pair;
- ambiguous structures are blocked for manual review;
- no raw G-code or printer command path exists;
- focused WP-065 tests pass;
- `make verify-fast` passes;
- the Work Package records validation evidence.
