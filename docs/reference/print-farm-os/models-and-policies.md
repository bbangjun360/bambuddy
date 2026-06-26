# Print Farm OS Models And Policies

This file summarizes model and policy ideas from Print Farm OS. It does not
define Bambuddy runtime behavior.
Bambuddy targets are planning anchors, not accepted schema or API changes.

## Source Files

Source snapshot: `2d8f108` (Restructure MVP UI into flow modes).

- `print-farm-os/print_farm_os/core/production.py`
- `print-farm-os/print_farm_os/core/quality.py`
- `print-farm-os/print_farm_os/core/materials.py`
- `print-farm-os/print_farm_os/core/artifacts.py`
- `print-farm-os/print_farm_os/core/queue_approval.py`
- `print-farm-os/print_farm_os/core/queue_reservation.py`
- `print-farm-os/print_farm_os/phase0/artifact_gate.py`
- `print-farm-os/print_farm_os/phase0/upload_eligibility.py`
- `print-farm-os/backend/migrations/0001_production_core.sql`
- `print-farm-os/backend/migrations/0002_file_assets.sql`

## Product And Work Order Model

Print Farm OS models `Product`, `ProductVariant`, `Part`, and `WorkOrder` as
production objects. Bambuddy already has `Project`, `ProjectBOM`,
`LibraryFile`, archives, and queue items, so a direct schema port is not
recommended.

Recommended Bambuddy mapping:

| Print Farm OS model | Bambuddy target |
| --- | --- |
| `Product` / `ProductVariant` | `Project` plus future SKU metadata. |
| `Part` | `ProjectBOM` and `LibraryFile`. |
| `WorkOrder` | Future production-order table or ERP production request review table. |
| `QueueItem` | Existing `PrintQueueItem` with feature-flagged production fields. |

## QC And Reprint Policy

Useful concepts:

- `QCOutcome`: not required, waiting QC, passed, failed, hold.
- `QCReasonCode`: first layer lift, warping, spaghetti, under extrusion, over extrusion, stringing/blobs, layer shift, support failure, dimension out of tolerance, surface defect, missing part, color/material mismatch, label missing/wrong, bed swap damage, printer error, material quality, operator handling damage, unknown.
- `QCDisposition`: reprint, rework, scrap, hold, B-grade.
- `ReprintRequest`: separate source QC record and source queue item.

Recommended Bambuddy mapping:

| Concept | Bambuddy target |
| --- | --- |
| QC reason taxonomy | `PrintLogEntry.failure_reason`, archive reprint modal, future QC API. |
| QC disposition | Future print-log/QC workflow. |
| Reprint request | Archive reprint path and background dispatch metadata. |

## Operator Task Policy

Print Farm OS task types:

- `bed_clear`
- `qc`
- `material_change`
- `label_attach`
- `adapter_failure`

Recommended Bambuddy mapping:

| Task type | Bambuddy target |
| --- | --- |
| `bed_clear` | Existing clear-plate queue setting and bed automation Work Packages. |
| `qc` | Future QC screen and print-log failure handling. |
| `material_change` | Existing filament deficit and spool assignment workflows. |
| `label_attach` | Existing label rendering API plus future label job tracking. |
| `adapter_failure` | PrintFlow, ERP, Obico, and slicer adapter diagnostics. |

## Material And Cost Policy

Useful concepts:

- Material batches record vendor, lot code, spool count, grams per spool, and unit cost.
- Material mounts track printer slot, mounted grams, remaining grams, and mounted/unmounted state.
- Consumption reconciliation compares estimated grams to actual grams and flags variance.
- Reorder prediction uses remaining grams, safety stock, and expected usage.

Recommended Bambuddy mapping:

| Concept | Bambuddy target |
| --- | --- |
| Material batch | Spoolman inventory and Bambuddy spool catalog. |
| Material mount | AMS/spool assignment and slot tracking. |
| Consumption variance | `usage_tracker`, print log material usage, and stats. |
| Reorder prediction | Existing filament SKU settings and shopping list. |

## Artifact Gate And Upload Eligibility

Useful gate inputs:

- 3MF inspection result.
- Printer/profile compatibility evidence.
- Printer-ready candidate check.
- Bed temperature policy.
- Idle/completed/cancelled printer state handling.
- Explicit operator approval.

Recommended Bambuddy mapping:

| Gate concept | Bambuddy target |
| --- | --- |
| 3MF inspection | Existing 3MF parser, plate extraction, and library metadata. |
| Compatibility evidence | Future pre-dispatch gate before `PrintQueueItem` start. |
| Explicit approval | Manual start, queue-only mode, and canary runbooks. |
| Bed clear confirmation | Clear plate setting and bed automation state machine. |

## Direct Port Risk

A direct port would duplicate Bambuddy models and migrations. Use these ideas as
Work Package inputs, then write Bambuddy-native tests against existing routes,
models, and services.
