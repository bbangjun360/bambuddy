# WP-065 SwapMod 3MF Dry-Run Review Runbook

## Purpose

Generate a redacted dry-run review plan from one original 3MF and one
SwapMod-generated 3MF. This runbook is not for real printer control.

## Required Configuration

```bash
FARM_SWAPMOD_3MF_DRY_RUN_ENABLED=true
FARM_SWAPMOD_3MF_DRY_RUN_REQUIRED=true
FARM_SWAPMOD_3MF_SAMPLE_ROOT=$HOME/workspace/plate-change-samples
```

The input artifacts must resolve under `FARM_SWAPMOD_3MF_SAMPLE_ROOT` and must
not be inside the repository.

## Procedure

1. Put the original and SwapMod 3MF artifacts under the configured sample root.
2. Confirm neither path contains printer credentials, customer data, or generated
   files intended for commit.
3. Call `GET /api/v1/plate-change-3mf/swapmod-dry-run/status`.
4. Call `POST /api/v1/plate-change-3mf/swapmod-dry-run/plans` with:

```json
{
  "original_path": "/path/under/sample-root/original.3mf",
  "swapmod_path": "/path/under/sample-root/swapmod.3mf",
  "dry_run": true,
  "expected_printer_model_family": "A1 Mini"
}
```

5. Review candidate ids, candidate kinds, line counts, line range hashes, and
   command-family counts.
6. Treat `SWAPMOD_DRY_RUN_REVIEW_REQUIRED` as a stop condition for automation.

## Stop Conditions

Stop immediately if any of these occur:

- the feature flag is not explicitly enabled for local review;
- either input path is outside the configured sample root;
- either input path is inside the repository;
- either input is not a readable `.3mf` or `.gcode.3mf`;
- either input lacks an internal `.gcode` member;
- the SwapMod structure does not contain exactly two original-job occurrences;
- any response includes raw G-code, local absolute paths, printer IPs, access
  codes, serial numbers, tokens, customer data, or arbitrary command text;
- any route or request attempts printer upload, print start, raw command, queue
  dispatch, scheduler dispatch, automatic retry, or next-print automation.

## Rollback

Set `FARM_SWAPMOD_3MF_DRY_RUN_ENABLED=false`. There is no migration and no
physical action to resume after restart.
