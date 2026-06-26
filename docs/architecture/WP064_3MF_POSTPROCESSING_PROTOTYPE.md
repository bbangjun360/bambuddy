# WP-064-A 3MF Post-Processing Prototype

## Status

WP-064-A is a disabled-by-default, dry-run-only prototype. It does not authorize
hardware execution, printer upload, printer start, MQTT, FTPS, queue dispatch,
scheduler dispatch, ERP writes, Obico mutation, or bed automation mutation.

## Context

Previous plate-change research concluded that direct live G-code command
execution is not ready for approval from samples alone. A 3MF post-processing
prototype is safer for the next iteration because behavior stays inside a
bounded print-job artifact that can be listed, summarized, and reviewed before
any future use.

WP-064-A only inspects controlled local/test artifacts and returns a redacted
plan. It may optionally write a modified 3MF artifact in a controlled temp
directory when explicitly enabled for tests. That artifact is evidence for
review, not something Bambuddy uploads or starts.

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

The request accepts a local `source_path`, `dry_run=true`, and optional
`create_output_artifact=false`. The schema forbids extra fields, so raw editable
G-code fields are rejected by validation instead of being ignored.

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
- reports `postprocess_supported=false` and `prototype_only=true`;
- reports `printer_upload_supported=false`,
  `printer_start_supported=false`, and `real_execution_supported=false`;
- keeps all forbidden side-effect sentinels at zero.

The redacted diff summary never contains raw G-code. It records counts and
review requirements only.

## Optional Output Artifact

Output artifact creation is blocked unless both are true:

- runtime config sets `FARM_PLATE_CHANGE_3MF_ALLOW_OUTPUT_ARTIFACT=true`;
- the request sets `create_output_artifact=true`.

When enabled, the service writes only under a controlled temp/test root. WP-064-A
does not alter internal G-code. It copies the source 3MF and adds
`Metadata/bambuddy_plate_change_postprocess_plan.json` with a redacted prototype
manifest. Output artifacts require human diff review before any future use.

Raw 3MF files, raw G-code files, extracted full G-code, model geometry, printer
identifiers, access codes, tokens, IPs, and customer data must not be committed.

## Forbidden Boundaries

WP-064-A must not:

- send real printer commands;
- upload files to a printer;
- start prints;
- connect to direct Bambu MQTT;
- use FTPS helpers;
- expose arbitrary G-code or raw command endpoints;
- accept raw editable G-code input;
- dispatch queue or scheduler work;
- mutate ERP, Obico, or bed automation state;
- commit raw sample artifacts or secrets;
- weaken CI or security tests.

## Test Coverage

Focused coverage includes:

- default-disabled API behavior;
- status safe defaults;
- dry-run runtime enforcement;
- schema rejection of raw editable G-code fields;
- synthetic 3MF fixture planning;
- internal file listing and internal G-code candidate detection;
- filename and content redaction;
- controlled path guards;
- raw `.gcode` source rejection;
- invalid ZIP rejection;
- output artifact blocking by default;
- temp-root-only output artifact creation when explicitly enabled;
- zero side-effect sentinels;
- architecture checks for no live-control imports or execution routes;
- tracked-file checks proving no raw `.3mf`, `.gcode.3mf`, or `.gcode` sample
  files are committed;
- harness checks proving no external mock post-processing execution server is
  exposed.

## Future Work

WP-064-B may add deterministic synthetic insertion tests. It should still avoid
hardware execution and should continue to compare redacted plans rather than raw
sample output.

WP-064-C may add human-reviewed real sample output generation. That work must
keep raw samples and extracted full G-code out of the repository and store only
sanitized evidence.

Printer upload and print start remain out of scope until a separate approved
Work Package adds and tests a Bambuddy-owned execution boundary.
