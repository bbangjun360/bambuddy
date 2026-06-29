# WP-066 SwapMod Canary Preflight Runbook

## Purpose

Use this runbook to package one reviewed WP-065 SwapMod dry-run candidate for
human canary review. This is a preflight-only workflow and does not execute
printer commands.

## Preconditions

- WP-065 dry-run evidence has `status=SWAPMOD_DRY_RUN_READY`.
- The selected candidate id and line range hash are from the redacted WP-065
  response.
- The target printer id is a Bambuddy printer id represented without IP, serial,
  access code, or other credentials in repo evidence.
- The operator confirms A1 Mini scope explicitly.

## Feature Flag

The workflow is disabled by default:

```text
FARM_SWAPMOD_CANARY_PREFLIGHT_ENABLED=false
```

Enable only in a local test or reviewed canary-preparation environment:

```text
FARM_SWAPMOD_CANARY_PREFLIGHT_ENABLED=true
FARM_SWAPMOD_CANARY_PREFLIGHT_REQUIRE_HUMAN_CONFIRMATION=true
FARM_SWAPMOD_CANARY_PREFLIGHT_SINGLE_PRINTER_ONLY=true
```

## Status Check

Call:

```text
GET /api/v1/plate-change-3mf/swapmod-canary-preflight/status
```

Safe defaults must report:

- `mode=CANARY_PREFLIGHT_ONLY`
- `real_execution_supported=false`
- `printer_command_supported=false`
- `printer_upload_supported=false`
- `printer_start_supported=false`
- `auto_retry_supported=false`
- all sentinels equal zero

## Package Request

Call:

```text
POST /api/v1/plate-change-3mf/swapmod-canary-preflight/packages
```

Use a body shaped like:

```json
{
  "dry_run_plan": {
    "status": "SWAPMOD_DRY_RUN_READY",
    "mode": "DRY_RUN_ONLY",
    "expected_printer_model_family": "A1 Mini",
    "candidate_blocks": [
      {
        "candidate_id": "swapmod:inter_job_swap:aaaaaaaaaaaa",
        "candidate_kind": "inter_job_swap",
        "line_count": 42,
        "line_range_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "command_family_counts": {"G1": 12, "G4": 4},
        "review_required": true,
        "raw_gcode_included": false,
        "real_execution_supported": false
      }
    ],
    "sentinels": {"printer_commands": 0, "queue_dispatches": 0}
  },
  "candidate_id": "swapmod:inter_job_swap:aaaaaaaaaaaa",
  "target_printer_id": "101",
  "expected_printer_model_family": "A1 Mini",
  "checklist": {
    "operator_present": true,
    "printer_visible": true,
    "emergency_stop_ready": true,
    "power_cutoff_ready": true,
    "bed_clear_confirmed": true,
    "correct_plate_confirmed": true,
    "no_other_job_running": true,
    "swapmod_hardware_installed": true,
    "plate_stack_loaded": true,
    "original_print_finished": true,
    "bed_state_reviewed": true
  },
  "operator_confirmation_phrase": "CONFIRM_SWAPMOD_CANARY_PREFLIGHT 101 swapmod:inter_job_swap:aaaaaaaaaaaa aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}
```

The exact phrase format is:

```text
CONFIRM_SWAPMOD_CANARY_PREFLIGHT <printer_id> <candidate_id> <line_range_hash>
```

## Stop Conditions

Stop and do not proceed to hardware if any of these are true:

- The endpoint returns `SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED`.
- Any checklist field is missing or false.
- The model family is not exactly `A1 Mini`.
- The candidate id is missing, duplicated, or has unexpected metadata.
- The confirmation phrase does not match exactly.
- Any raw command-like field appears in the request or dry-run plan.
- Any side-effect sentinel is nonzero.
- Bambuddy restarts or the physical state becomes uncertain.

## Recovery

There is no automatic retry or restart resume. If preflight fails, correct the
review evidence and create a new package request. If physical state is uncertain,
enter manual review. A later hardware Work Package must verify bed READY before
any next print.

## Rollback

Leave or set:

```text
FARM_SWAPMOD_CANARY_PREFLIGHT_ENABLED=false
```

Code rollback is a file-level revert of the WP-066 config, schema, service,
route, tests, Make target, architecture doc, runbook, and Work Package updates.
