# WP-065 SwapMod 3MF Dry-Run Workflow

## Status

WP-065 adds a default-off dry-run review boundary for comparing one original A1
Mini 3MF with one SwapMod-generated 3MF. It does not authorize hardware
execution.

## Boundary

Implemented files:

- `backend/app/services/swapmod_3mf_dry_run.py`
- `backend/app/schemas/swapmod_3mf_dry_run.py`
- `backend/app/api/routes/swapmod_3mf_dry_run.py`

Routes:

- `GET /api/v1/plate-change-3mf/swapmod-dry-run/status`
- `POST /api/v1/plate-change-3mf/swapmod-dry-run/plans`

Config defaults:

- `FARM_SWAPMOD_3MF_DRY_RUN_ENABLED=false`
- `FARM_SWAPMOD_3MF_DRY_RUN_REQUIRED=true`
- `FARM_SWAPMOD_3MF_SAMPLE_ROOT` unset; default is `~/workspace/plate-change-samples`

The endpoint accepts only local `.3mf` or `.gcode.3mf` paths under the configured
sample root. It rejects repository paths and raw `.gcode` files.

## Extraction

The first slice is intentionally exact-match only. It reads the first internal
`.gcode` member from each 3MF, normalizes line endings, and looks for exactly
two full original-job occurrences inside the SwapMod G-code. When that structure
is present, it summarizes three windows:

- lines before the first original occurrence: `plate_load_only`;
- lines between the two original occurrences: `inter_job_swap`;
- lines after the second original occurrence: `final_swap`.

If the structure is not exact, the response is `SWAPMOD_DRY_RUN_REVIEW_REQUIRED`
and includes only redacted review reasons. It does not approve execution.

## Redaction

Responses include candidate ids, candidate kinds, line counts, line range hashes,
command-family counts, and dry-run workflow states. Responses do not include raw
G-code, local absolute paths, printer IPs, access codes, serial numbers, tokens,
customer data, or arbitrary command text.

## Side Effects

WP-065 does not import or call printer manager, Bambu MQTT, FTPS helpers, queue
or scheduler dispatch paths, ERP, Obico, or bed automation mutation paths. All
forbidden side-effect sentinels remain zero.

## Handoff

A future WP-066 may implement a human-gated real A1 Mini canary using one
reviewed candidate id, one printer, one attempt, exact confirmation phrases, no
retry, and no next print until bed READY is verified.
