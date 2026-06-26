# Print Farm OS Test Evidence Index

This index tracks the Print Farm OS test and validation evidence imported for
Bambuddy planning.

## Source Groups

| Group | Source paths | Import action | Bambuddy relevance |
| --- | --- | --- | --- |
| Phase 0 protocol checks | `docs/3d-printing-automation/02-phase0-protocol-validation.md`, `docs/3d-printing-automation/phase0-run-2026-06-08.md`, `print-farm-os/tests/test_phase0_*.py` | Summarized and indexed with lab context preserved | Future printer preflight, artifact gate, protocol simulator, and first-printer canary work. |
| A1 / AMS Lite gates | `docs/3d-printing-automation/02a-a1-ams-lite-preflight-gate.md`, `docs/3d-printing-automation/10-a1-unattended-cell-hazard-checklist.md`, `docs/3d-printing-automation/12-a1-unattended-pilot-protocol.md`, `print-farm-os/tests/test_phase0_a1_*.py`, `print-farm-os/tests/test_phase0_ams_*.py` | Summarized and indexed with lab context preserved | Bed automation, manual review, AMS gating, and unattended-cell safety criteria. |
| Orca/Bambu slicer flow | `docs/3d-printing-automation/02b-orcaslicer-bambu-print-flow.md`, `print-farm-os/tests/test_m11_orca_runtime_smoke.py`, `print-farm-os/tests/test_m11_slicing_artifacts.py`, `print-farm-os/tests/test_phase0_slicing_upload_candidate.py`, `print-farm-os/fixtures/*.stl`, `print-farm-os/fixtures/*.gcode.3mf` | Summarized; safe fixtures copied | Existing Bambuddy slicer sidecar and artifact compatibility checks. |
| Bambu error references | `docs/3d-printing-automation/02c-bambulab-wiki-error-reference.md`, `print-farm-os/tests/test_phase0_bambu_wiki_hms.py`, `print-farm-os/tests/test_phase0_printer_error_policy.py` | Summarized and indexed | HMS/error policy and stop-condition docs. |
| MVP production core | `docs/3d-printing-automation/03-mvp-functional-spec.md`, `docs/3d-printing-automation/04-mvp-implementation-plan.md`, `print-farm-os/tests/test_m3_*.py`, `print-farm-os/tests/test_m10_*.py`, `print-farm-os/tests/test_m18_*.py`, `print-farm-os/tests/test_m19_*.py`, `print-farm-os/tests/test_m20_*.py`, `print-farm-os/tests/test_m21_*.py` | Summarized | Product/SKU, WorkOrder, Queue Approval, Queue Reservation, Reprint, and software happy path candidates. |
| Runtime and UI validation | `docs/3d-printing-automation/10-mvp-current-status-20260616T0330KST.md`, `docs/3d-printing-automation/11-mvp-runtime-closeout-20260616T1248KST.md`, `docs/3d-printing-automation/14-ui-verification-and-design-runbook.md`, `docs/3d-printing-automation/15-stitch-ui-generation-brief.md`, `docs/3d-printing-automation/16-stitch-ui-output-review.md`, `print-farm-os/tests/test_m15_*.py`, `print-farm-os/tests/test_m17_*.py` | Summarized | Future operator UI and compose/runtime verification. |
| Execution ledgers and checkpoints | `docs/3d-printing-automation/09-execution-progress-ledger.md`, `docs/3d-printing-automation/13-validation-checkpoint-2026-06-09-1100.md` | Summarized | Evidence tracking format and Work Package handoff discipline. |

## Test Module Coverage

| Test module pattern | Coverage area | Recommended Bambuddy use |
| --- | --- | --- |
| `test_phase0_network_probe.py`, `test_phase0_tls_probe.py`, `test_phase0_auth_smoke.py` | Safe connectivity and credential readiness | Add harness-only protocol simulator checks before real printer canary. |
| `test_phase0_three_mf_inspector.py`, `test_phase0_artifact_gate.py`, `test_phase0_upload_eligibility.py` | Artifact compatibility and guarded upload decisions | Add a Bambuddy pre-dispatch artifact gate Work Package. |
| `test_phase0_mqtt_status.py`, `test_phase0_status_normalizer.py`, `test_phase0_print_control.py`, `test_phase0_print_start.py` | MQTT status, normalized printer state, and command planning | Inform Bambuddy characterization tests around print start boundaries. |
| `test_m3_production_core.py`, `test_m3_repository.py`, `test_m3_schema_mapping.py` | Product, work order, queue, and repository model | Inform product/SKU Work Package without porting schema directly. |
| `test_m10_qc_taxonomy.py`, `test_m20_reprint_queue_api.py` | QC failure reasons and reprint flow | First candidate for Bambuddy print-log/reprint enhancement. |
| `test_m18_queue_reservation.py`, `test_m19_queue_approval.py` | Queue approval/reservation gates | Inform queue state machine changes behind feature flags. |
| `test_m6_label_printer_driver.py`, `test_m6_operations_api.py` | Label printer dry-run and operations API | Inform future label print job tracking. |

## Import Notes

- The index preserves source file paths so future Work Packages can inspect the
  original source.
- This is an index of Print Farm OS summarized/reference evidence, not a record of Bambuddy test execution.
- Lab context is allowed when copied or summarized.
- Actual access codes, API tokens, passwords, private keys, customer data, and
  personal data are excluded.
