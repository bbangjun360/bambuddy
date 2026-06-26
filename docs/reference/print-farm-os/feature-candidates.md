# Print Farm OS Feature Candidates For Bambuddy

These candidates are ordered by near-term value and implementation risk. Each
candidate should become its own Bambuddy Work Package before runtime changes.

## 1. QC Reason Taxonomy

- Value: Standardizes failed-print reasons and makes reprint analytics more useful.
- Source references: `core/quality.py`, `test_m10_qc_taxonomy.py`, `test_m20_reprint_queue_api.py`.
- Bambuddy touch points: `PrintLogEntry.failure_reason`, archive reprint flow, print log modal, statistics.
- Risk: Low if introduced as display/API taxonomy first.
- Recommended first test: unit test that maps each taxonomy code to a stable label, category, default disposition, and allowed dispositions.

## 2. Artifact Gate Before Dispatch

- Value: Blocks mismatched or non-printer-ready files before upload or print start.
- Source references: `phase0/artifact_gate.py`, `phase0/upload_eligibility.py`, `test_phase0_artifact_gate.py`, `test_phase0_upload_eligibility.py`.
- Bambuddy touch points: `LibraryFile`, archive reprint, slice output, `PrintQueueItem` start route, background dispatch.
- Risk: Medium because it touches dispatch boundaries.
- Recommended first test: characterization test proving current start route behavior before adding a feature-flagged gate.

## 3. Operator Tasks

- Value: Converts bed-clear, material-change, QC, label-attach, and adapter-failure work into visible operator tasks.
- Source references: `core/production.py`, `test_m10_operator_workflow_coverage.py`, `test_m9_a1_unattended_safety.py`.
- Bambuddy touch points: queue page, clear-plate settings, filament deficit handling, label API, PrintFlow/ERP/Obico diagnostics.
- Risk: Medium because it adds user-visible workflow state.
- Recommended first test: API test that creates a material-change task when a queued print has no matching spool.

## 4. Product/SKU Work Orders

- Value: Gives production farms a bridge from product demand to queued print copies.
- Source references: `core/production.py`, `core/product_import.py`, `test_m10_product_bulk_import.py`, `test_m21_mvp_software_happy_path.py`.
- Bambuddy touch points: `Project`, `ProjectBOM`, `LibraryFile`, `PrintQueueItem`, ERP production request review.
- Risk: High because it overlaps with projects, queue, and ERP.
- Recommended first test: product/SKU import dry run that creates no `PrintQueueItem` until explicitly approved.

## 5. Label Print Job Tracking

- Value: Tracks label printing separately from label rendering and supports printed-unit traceability.
- Source references: `core/labels.py`, `frontend/src/labelPrinterDriver.ts`, `test_m6_label_printer_driver.py`.
- Bambuddy touch points: existing label routes and future queue-item label actions.
- Risk: Medium because browser/device integrations need careful dry-run defaults.
- Recommended first test: label print job dry-run records queued, printed, and failed states without device access.

## 6. Material Batch And Consumption Variance

- Value: Improves cost accounting, inventory reconciliation, and reorder forecasts.
- Source references: `core/materials.py`, `test_m13_materials_costing.py`.
- Bambuddy touch points: Spoolman inventory, `usage_tracker`, print log, filament SKU settings, shopping list.
- Risk: Medium because actual grams and spool state can diverge.
- Recommended first test: pure unit test for estimated-vs-actual variance classification.

## 7. Phase 0 Readiness Report

- Value: Gives operators a single preflight report before first-printer canary or hardware automation.
- Source references: `phase0/preflight.py`, `phase0/runbook_progress.py`, `test_phase0_preflight_readiness.py`, `test_phase0_runbook_progress.py`.
- Bambuddy touch points: `make harness-health`, support bundle, runbooks, future system health page.
- Risk: Low if it starts as a report-only harness command.
- Recommended first test: harness test that renders blocked and ready rows from deterministic fake inputs.

## Recommended Sequence

1. QC Reason Taxonomy
2. Phase 0 Readiness Report
3. Artifact Gate Before Dispatch
4. Operator Tasks
5. Label Print Job Tracking
6. Material Batch And Consumption Variance
7. Product/SKU Work Orders
