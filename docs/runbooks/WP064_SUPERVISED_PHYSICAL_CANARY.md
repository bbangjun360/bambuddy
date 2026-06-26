# WP-064 Supervised Physical Canary Runbook

## Purpose

Run one human-supervised upload and one print-start attempt for one reviewed
3MF artifact on one canary printer. This runbook is for a controlled physical
canary only; simulation success is not proof of physical safety.

The canary boundary does not expose raw G-code, arbitrary command execution,
queue dispatch, scheduler dispatch, batch dispatch, automatic retry, or
multi-printer execution.

## Required Configuration

All gates are required. Defaults keep the physical canary blocked.

```bash
FARM_PLATE_CHANGE_3MF_PHYSICAL_CANARY_ENABLED=true
FARM_PLATE_CHANGE_3MF_ALLOW_PRINTER_UPLOAD=true
FARM_PLATE_CHANGE_3MF_ALLOW_PRINT_START=true
FARM_PLATE_CHANGE_3MF_CANARY_SINGLE_PRINTER_ONLY=true
FARM_PLATE_CHANGE_3MF_CANARY_REQUIRE_HUMAN_CONFIRMATION=true
FARM_PLATE_CHANGE_3MF_CANARY_DISABLE_AUTO_RETRY=true
FARM_PLATE_CHANGE_3MF_CANARY_MAX_STARTS=1
FARM_PLATE_CHANGE_3MF_OUTPUT_ROOT=$HOME/workspace/plate-change-outputs
```

The reviewed artifact path must resolve under `FARM_PLATE_CHANGE_3MF_OUTPUT_ROOT`
and must not be inside the repository.

## Required Review Inputs

Before upload, record:

- canary `printer_id`
- reviewed `artifact_path`
- reviewed `artifact_sha256`

Upload confirmation phrase:

```text
CONFIRM_UPLOAD_REVIEWED_3MF <printer_id> <artifact_sha256>
```

Start confirmation phrase:

```text
CONFIRM_START_REVIEWED_3MF <printer_id> <artifact_sha256>
```

The upload phrase does not authorize print start. Print start requires the
separate start phrase and a prior successful upload record.

## Start Checklist

Every field must be true in the `/canary-start` request:

- `operator_present`
- `printer_visible`
- `emergency_stop_ready`
- `power_cutoff_ready`
- `bed_clear_confirmed`
- `correct_plate_confirmed`
- `no_other_job_running`
- `fire_risk_area_clear`

## Procedure

1. Confirm the reviewed 3MF artifact is under the configured output root.
2. Confirm `sha256sum` for the artifact matches the reviewed hash.
3. Confirm exactly one canary printer is selected and visible.
4. Check status with `GET /api/v1/plate-change-3mf/canary-status`.
5. Upload with `POST /api/v1/plate-change-3mf/canary-upload` using the upload
   phrase.
6. Re-check the printer and checklist items.
7. Start with `POST /api/v1/plate-change-3mf/canary-start` using the separate
   start phrase.
8. Do not retry from software if upload or start fails. Stop and inspect the
   printer physically.

## Stop Conditions

Stop immediately if any of these occur:

- any configured canary flag is not set exactly as required;
- artifact SHA-256 does not match;
- artifact path is outside the configured output root;
- artifact path is inside the repository;
- more than one printer is selected;
- the printer state is unknown or not idle;
- any checklist field is false;
- the upload phrase is reused for start;
- any queue, scheduler, retry, batch, multi-printer, raw-command, or raw G-code
  path appears in requests or responses;
- any response leaks printer IP, access code, serial number, token, customer
  data, raw full G-code, or local artifact path.

## Rollback

Set any of these flags to `false` to block the canary immediately:

```bash
FARM_PLATE_CHANGE_3MF_PHYSICAL_CANARY_ENABLED=false
FARM_PLATE_CHANGE_3MF_ALLOW_PRINTER_UPLOAD=false
FARM_PLATE_CHANGE_3MF_ALLOW_PRINT_START=false
```

There is no database migration. The canary upload/start state is in process
memory and is intentionally not resumed after restart.

## CI and Test Safety

Tests must use mocks only. CI must not contact real printers, MQTT, FTPS, or
hardware. Do not commit real 3MF/G-code artifacts, generated outputs, printer
IP addresses, access codes, serial numbers, API tokens, logs, or customer data.
