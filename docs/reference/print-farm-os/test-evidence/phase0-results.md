# Phase 0 Results

## Source Files

- `docs/3d-printing-automation/02-phase0-protocol-validation.md`
- `docs/3d-printing-automation/02a-a1-ams-lite-preflight-gate.md`
- `docs/3d-printing-automation/02b-orcaslicer-bambu-print-flow.md`
- `docs/3d-printing-automation/02c-bambulab-wiki-error-reference.md`
- `docs/3d-printing-automation/phase0-run-2026-06-08.md`
- `docs/3d-printing-automation/10-a1-unattended-cell-hazard-checklist.md`
- `docs/3d-printing-automation/12-a1-unattended-pilot-protocol.md`
- `print-farm-os/tests/test_phase0_*.py`

## Imported Result Themes

- Inventory and discovery checks validate non-secret printer metadata and managed-printer decisions.
- Network and TLS probes check safe reachability before credentials or printer commands.
- Auth smoke, MQTT status, FTPS storage, camera probe, and status normalization separate observation from command publishing.
- 3MF inspection, artifact gate, transfer plan, upload eligibility, and print-start review are the strongest candidates for Bambuddy pre-dispatch safety gates.
- A1/A1 mini/AMS Lite evidence emphasizes explicit operator approval, external spool confirmation, idle-state confirmation, and bed-clear checks.
- P1S-related evidence records strict compatibility requirements and motion-validation blocking after collision investigation.

## Bambuddy Mapping

| Print Farm OS concept | Bambuddy integration point |
| --- | --- |
| Inventory and discovery reconciliation | Existing printer discovery and future harness protocol simulator. |
| TLS/FTPS/MQTT readiness | Existing virtual printer, Bambu FTP/MQTT tests, and first-printer canary runbooks. |
| Artifact gate | `LibraryFile`, slice output, archive reprint, and queue dispatch boundary. |
| Upload eligibility | `PrintQueueItem` start path and background dispatch preflight. |
| A1 unattended hazard checklist | Bed automation and PrintFlow canary stop conditions. |
| Operator confirmation gates | Future operator task model and runbook UI. |

## Import Decision

Keep the evidence as reference material first. Do not wire these gates into
Bambuddy dispatch until a dedicated Work Package adds characterization tests
around the current print start path.
