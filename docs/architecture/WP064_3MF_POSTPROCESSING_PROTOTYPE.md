# WP-064 3MF Post-Processing Prototype

## Status

WP-064-A introduced a disabled-by-default, dry-run-only 3MF post-processing
planner. WP-064-B extends that prototype with deterministic synthetic insertion
behavior for tests only. WP-064-C adds a local-only real-sample output review
mode that writes review artifacts only under an explicit local output root.

The prototype does not authorize hardware execution, printer upload, printer
start, MQTT, FTPS, queue dispatch, scheduler dispatch, ERP writes, Obico
mutation, or bed automation mutation.

## Context

Previous plate-change research concluded that direct live G-code command
execution is not ready for approval from samples alone. A 3MF post-processing
prototype is safer for the next iteration because behavior stays inside a
bounded print-job artifact that can be listed, summarized, and reviewed before
any future use.

WP-064-A only inspected controlled local/test artifacts and returned a redacted
plan. WP-064-B still uses synthetic fixtures only, but when output artifacts are
explicitly enabled for tests it can rewrite a controlled temp 3MF by inserting a
symbolic marker block into one synthetic internal G-code member.

## Implemented Boundary

Service:

- `backend/app/services/plate_change_3mf_postprocess.py`

Schema:

- `backend/app/schemas/plate_change_3mf_postprocess.py`

Routes:

- `POST /api/v1/plate-change-3mf/postprocess-plans`
- `GET /api/v1/plate-change-3mf/status`

Config flags:

- `FARM_PLATE_CHANGE_3MF_POSTPROCESS_ENABLED=false`
- `FARM_PLATE_CHANGE_3MF_POSTPROCESS_DRY_RUN=true`
- `FARM_PLATE_CHANGE_3MF_ALLOW_OUTPUT_ARTIFACT=false`
- `FARM_PLATE_CHANGE_3MF_REAL_SAMPLE_ROOT` unset; default is `~/workspace/plate-change-samples`
- `FARM_PLATE_CHANGE_3MF_OUTPUT_ROOT` unset; default is `~/workspace/plate-change-outputs`
- `FARM_PLATE_CHANGE_3MF_ALLOW_REAL_SAMPLE_OUTPUT=false`

The request accepts a local `source_path`, `dry_run=true`, optional
`create_output_artifact=false`, optional `real_sample_output_review=false`,
and optional `output_dir`. The schema forbids extra fields, so raw editable
G-code fields, command text, raw command fields, and arbitrary body fields are
rejected by validation instead of being ignored.

## Planner Behavior

The planner:

- requires the feature flag to be enabled;
- requires dry-run mode;
- accepts only `.3mf` or `.gcode.3mf` ZIP artifacts;
- requires source paths to be under controlled local temp/test roots;
- lists internal 3MF ZIP entries;
- identifies internal files ending in `.gcode`;
- detects the embedded printer model family when present;
- reads internal G-code only to build symbolic marker summaries;
- returns candidate blocks and insertion points without raw G-code text;
- reports source SHA-256 and, only when output is created, output SHA-256;
- reports `postprocess_supported=false` and `prototype_only=true`;
- reports `real_gcode_inserted=false`;
- reports `printer_upload_supported=false`,
  `printer_start_supported=false`, and `real_execution_supported=false`;
- keeps all forbidden side-effect sentinels at zero.

The redacted diff summary never contains raw G-code. It records counts and
review requirements only.

## WP-064-B Synthetic Insertion

WP-064-B uses synthetic minimal 3MF fixtures only. It does not use real user
sample files and tests must not read `~/workspace/plate-change-samples`.

The deterministic synthetic insertion point is the comment marker:

```text
; BAMBUDDY_SYNTHETIC_PLATE_CHANGE_INSERTION_POINT
```

When output artifact creation is explicitly enabled and exactly one synthetic
internal G-code member contains that marker, the service inserts this symbolic
block immediately before the marker:

```text
; BAMBUDDY_PLATE_CHANGE_BLOCK_START
; symbolic_step: PLATE_CHANGE_REVIEW_REQUIRED
; symbolic_step: NO_REAL_GCODE_IN_WP_064_B
; BAMBUDDY_PLATE_CHANGE_BLOCK_END
```

The inserted block is safe synthetic text only. It contains no executable A1
mini G-code and `real_gcode_inserted` remains `false`.

The output artifact preserves the original ZIP member set. It modifies only the
target internal G-code member, preserves unrelated 3MF members byte-for-byte,
and reports:

- `insertion_performed`
- `insertion_marker_present`
- `inserted_block_kind`
- `source_sha256`
- `output_sha256`
- `deterministic_diff_summary`
- `preserved_member_count`
- `modified_member_paths`
- `real_gcode_inserted=false`
- `printer_upload_supported=false`
- `printer_start_supported=false`
- `real_execution_supported=false`

Unknown or unsupported synthetic structures return `POSTPROCESS_UNSUPPORTED` and
create no output artifact.

## WP-064-C Local Real-Sample Output Review

WP-064-C is review-only. It allows a human operator to generate a local output
3MF from a local real sample so the resulting ZIP can be inspected before any
future Work Package considers broader use. It does not approve printing.

Real-sample output review requires all of these gates:

- `FARM_PLATE_CHANGE_3MF_POSTPROCESS_ENABLED=true`;
- `FARM_PLATE_CHANGE_3MF_POSTPROCESS_DRY_RUN=true`;
- `FARM_PLATE_CHANGE_3MF_ALLOW_OUTPUT_ARTIFACT=true`;
- `FARM_PLATE_CHANGE_3MF_ALLOW_REAL_SAMPLE_OUTPUT=true`;
- request `dry_run=true`;
- request `create_output_artifact=true`;
- request `real_sample_output_review=true`.

The source path must resolve under `FARM_PLATE_CHANGE_3MF_REAL_SAMPLE_ROOT`, or
under `~/workspace/plate-change-samples` when the config root is unset. The
output directory must resolve under `FARM_PLATE_CHANGE_3MF_OUTPUT_ROOT`, or
under `~/workspace/plate-change-outputs` when the config root is unset. The
service rejects output directories inside the repository so generated `.3mf` or
G-code files cannot be written into tracked paths.

The output artifact preserves every original source member byte-for-byte and
adds or refreshes only this internal review manifest:

```text
Metadata/bambuddy_real_sample_output_review.json
```

The manifest contains redacted review metadata, hashes, internal G-code member
paths, and safety booleans. It never contains raw full G-code. WP-064-C does not
insert executable A1 mini G-code and does not modify internal G-code members.

The response includes redacted source and output names, `source_sha256`,
`output_sha256`, `internal_gcode_paths`, `modified_internal_paths`,
`preserved_member_count`, a deterministic diff summary,
`human_review_required=true`, `not_approved_for_printing=true`,
`printer_upload_supported=false`, `printer_start_supported=false`, and
`real_execution_supported=false`.

## Optional Output Artifact

Output artifact creation is blocked unless both are true:

- runtime config sets `FARM_PLATE_CHANGE_3MF_ALLOW_OUTPUT_ARTIFACT=true`;
- the request sets `create_output_artifact=true`.

When enabled, the service writes only under a controlled temp/test root. WP-064-B
output artifacts are prototype evidence for human diff review, not printer-ready
jobs. They must not be uploaded or started by Bambuddy.

Raw 3MF files, raw G-code files, extracted full G-code, generated output 3MF
artifacts, model geometry, printer identifiers, access codes, tokens, IPs, and
customer data must not be committed.

## Forbidden Boundaries

WP-064-B must not:

- send real printer commands;
- upload files to a printer;
- start prints;
- connect to direct Bambu MQTT;
- use FTPS helpers;
- expose arbitrary G-code or raw command endpoints;
- accept raw editable G-code input;
- dispatch queue or scheduler work;
- mutate ERP, Obico, or bed automation state;
- insert executable A1 mini G-code;
- write output artifacts into repository-tracked paths;
- use raw local sample directories in tests;
- commit raw sample artifacts, generated 3MF/G-code artifacts, or secrets;
- weaken CI or security tests.

## Test Coverage

Focused coverage includes:

- default-disabled API behavior;
- status safe defaults;
- dry-run runtime enforcement;
- schema rejection of raw editable G-code, command text, raw command, and body
  fields;
- synthetic 3MF fixture planning;
- deterministic insertion output hash stability;
- insertion marker appearing exactly once;
- only the target internal G-code member changing;
- unrelated 3MF members being byte-preserved;
- filename and content redaction;
- controlled path guards;
- raw `.gcode` source rejection;
- invalid ZIP rejection;
- unsupported synthetic structures returning safe blocked results;
- output artifact blocking by default;
- temp-root-only output artifact creation when explicitly enabled;
- real-sample output review blocked by default;
- real-sample output review requiring both config and request flags;
- real-sample input root and output root enforcement;
- repository path output rejection;
- manifest-only real-sample review artifact generation;
- response redaction with no raw full G-code;
- zero side-effect sentinels;
- architecture checks for no live-control imports or execution routes;
- tracked and worktree-file checks proving no raw `.3mf`, `.gcode.3mf`, or
  `.gcode` sample/output files are committed;
- harness checks proving no external mock post-processing execution server is
  exposed.

## Future Work

Future Work Packages may define how reviewed artifacts become approved for
printing. WP-064-C artifacts remain local review evidence only and are marked
`not_approved_for_printing=true`.

Printer upload and print start remain out of scope until a separate approved
Work Package adds and tests a Bambuddy-owned execution boundary.
