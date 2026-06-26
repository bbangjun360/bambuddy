# WP-064 Real-Sample Output Review Runbook

## Purpose

Generate a local review-only 3MF artifact from a local real sample and inspect
its deterministic review metadata. This runbook does not approve printing.

WP-064-C must not upload to printers, start prints, send MQTT, use FTPS, queue
jobs, schedule jobs, mutate ERP/Obico/bed automation, or execute G-code.

## Required Configuration

Keep the global prototype dry-run gate enabled and opt in explicitly:

```bash
FARM_PLATE_CHANGE_3MF_POSTPROCESS_ENABLED=true
FARM_PLATE_CHANGE_3MF_POSTPROCESS_DRY_RUN=true
FARM_PLATE_CHANGE_3MF_ALLOW_OUTPUT_ARTIFACT=true
FARM_PLATE_CHANGE_3MF_ALLOW_REAL_SAMPLE_OUTPUT=true
FARM_PLATE_CHANGE_3MF_REAL_SAMPLE_ROOT=$HOME/workspace/plate-change-samples
FARM_PLATE_CHANGE_3MF_OUTPUT_ROOT=$HOME/workspace/plate-change-outputs
```

The sample root and output root may be changed, but the source path must remain
under the configured sample root and the output directory must remain under the
configured output root. Repository paths are rejected for output.

## Review Procedure

1. Place the source `.3mf` or `.gcode.3mf` under the configured sample root.
2. Choose an output directory under the configured output root.
3. Submit a dry-run plan request to
   `/api/v1/plate-change-3mf/postprocess-plans` with:
   - `dry_run=true`
   - `create_output_artifact=true`
   - `real_sample_output_review=true`
   - `source_path` under the sample root
   - `output_dir` under the output root
4. Confirm the response includes:
   - redacted source and output names
   - `source_sha256`
   - `output_sha256`
   - `internal_gcode_paths`
   - `modified_internal_paths`
   - `preserved_member_count`
   - deterministic diff summary
   - `human_review_required=true`
   - `not_approved_for_printing=true`
   - `printer_upload_supported=false`
   - `printer_start_supported=false`
   - `real_execution_supported=false`
5. Inspect the output ZIP locally. The only WP-064-C-added member should be
   `Metadata/bambuddy_real_sample_output_review.json` unless that manifest was
   already present and refreshed.
6. Confirm no raw full G-code appears in the API response or manifest.

## Stop Conditions

Stop and do not use the artifact if any of these occur:

- the output path is inside the repository;
- the response includes raw full G-code;
- printer upload/start/execution support is true;
- any side-effect sentinel is non-zero;
- the output modifies internal G-code members;
- generated `.3mf`, `.gcode`, or `.gcode.3mf` files appear in `git status`.

## Cleanup

Delete unwanted review artifacts from the configured output root after review.
Do not commit generated 3MF/G-code artifacts, extracted full G-code, customer
data, printer serial numbers, access codes, API tokens, IP addresses, or logs.

## Rollback

Disable `FARM_PLATE_CHANGE_3MF_ALLOW_REAL_SAMPLE_OUTPUT` or disable the global
WP-064 postprocess flag. The feature has no database migration or durable state
inside Bambuddy.
