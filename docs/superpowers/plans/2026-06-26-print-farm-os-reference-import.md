# Print Farm OS Reference Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Bambuddy reference pack from Print Farm OS test evidence, policies, feature candidates, and safe fixtures without changing runtime behavior.

**Architecture:** This is a documentation and fixture import. Runtime code stays untouched; reference docs live under `docs/reference/print-farm-os/`, and copied sample inputs live under `harness/fixtures/phase0/`. Operational evidence may preserve lab context such as IPs, serials, timestamps, and local paths, but actual secret values are excluded and recorded.

**Tech Stack:** Markdown, JSON fixture files, binary STL/3MF fixtures, shell verification commands, git.

---

## File Structure

Create:

- `docs/reference/print-farm-os/README.md` - entry point and source snapshot.
- `docs/reference/print-farm-os/test-evidence/INDEX.md` - master evidence index.
- `docs/reference/print-farm-os/test-evidence/phase0-results.md` - Phase 0 evidence summary.
- `docs/reference/print-farm-os/test-evidence/mvp-runtime-results.md` - MVP/runtime evidence summary.
- `docs/reference/print-farm-os/test-evidence/validation-checkpoints.md` - checkpoint and handoff summary.
- `docs/reference/print-farm-os/models-and-policies.md` - model/policy ideas mapped to Bambuddy.
- `docs/reference/print-farm-os/feature-candidates.md` - future Work Package candidates.
- `docs/reference/print-farm-os/excluded-sensitive-values.md` - actual secrets or personal data excluded from import.
- `harness/fixtures/phase0/README.md` - fixture provenance and safety notes.
- `harness/fixtures/phase0/phase0-inventory.example.json`
- `harness/fixtures/phase0/phase0-discovery-ignore.example.json`
- `harness/fixtures/phase0/orca-smoke-cube.stl`
- `harness/fixtures/phase0/orca-smoke-cube-centered.stl`
- `harness/fixtures/phase0/not-printer-ready-placeholder.gcode.3mf`
- `harness/fixtures/phase0/phase0-smoke.gcode.3mf`

Source repository:

- Local clone: `/tmp/print-farm-os`
- Upstream: `https://github.com/bbangjun360/print-farm-os.git`

Do not modify Bambuddy backend, frontend, database migrations, Makefile, or runtime harness behavior in this plan.

---

### Task 1: Source Inventory

**Files:**
- Create: `docs/reference/print-farm-os/README.md`
- Create: `docs/reference/print-farm-os/excluded-sensitive-values.md`

- [ ] **Step 1: Verify source clone and current Bambuddy state**

Run:

```bash
git -C /tmp/print-farm-os log --oneline -1
git status --short
```

Expected:

- `/tmp/print-farm-os` prints one commit line.
- `git status --short` contains only files intentionally changed by this task or is empty.

- [ ] **Step 2: Create the reference directory**

Run:

```bash
mkdir -p docs/reference/print-farm-os/test-evidence
```

Expected: command exits successfully.

- [ ] **Step 3: Write the reference entry point**

Create `docs/reference/print-farm-os/README.md` with this structure:

```markdown
# Print Farm OS Reference Pack

This directory preserves useful planning, validation, and fixture material from
`https://github.com/bbangjun360/print-farm-os.git` for the Bambuddy farm fork.

Runtime code was not ported. Use this reference pack to inform future Bambuddy
Work Packages.

## Source Snapshot

- Source repository: `https://github.com/bbangjun360/print-farm-os.git`
- Local source path used during import: `/tmp/print-farm-os`
- Imported into Bambuddy path: `docs/reference/print-farm-os/`

## Contents

- `test-evidence/INDEX.md` - master index of imported test and validation evidence.
- `test-evidence/phase0-results.md` - Phase 0 safety and protocol evidence.
- `test-evidence/mvp-runtime-results.md` - MVP runtime and compose evidence.
- `test-evidence/validation-checkpoints.md` - validation checkpoints and handoff notes.
- `models-and-policies.md` - model and policy ideas mapped to Bambuddy concepts.
- `feature-candidates.md` - recommended future Work Packages.
- `excluded-sensitive-values.md` - actual secret values or personal data excluded from import.

## Import Policy

Preserve lab evidence when useful, including IP addresses, printer serials,
timestamps, and local file paths. Do not import actual access codes, API tokens,
passwords, private keys, customer data, or personal data.

## Fixtures

Safe example fixtures copied from Print Farm OS live under
`harness/fixtures/phase0/`. They are for harness and planning use only.
```

- [ ] **Step 4: Write the exclusion ledger**

Create `docs/reference/print-farm-os/excluded-sensitive-values.md` with this structure:

```markdown
# Excluded Sensitive Values

This file records source values or files that were not copied because they are
actual secrets or personal data.

Operational lab context such as IP addresses, printer serials, timestamps, and
local paths is allowed in this reference pack when it helps preserve test
evidence.

## Exclusions

No actual access codes, API tokens, passwords, private keys, customer data, or
personal data were intentionally imported.

## Review Commands

```bash
rg -n "access_code|api[_-]?token|password|private key|BEGIN .*PRIVATE KEY|customer|email" docs/reference/print-farm-os
```
```

- [ ] **Step 5: Verify task output**

Run:

```bash
test -f docs/reference/print-farm-os/README.md
test -f docs/reference/print-farm-os/excluded-sensitive-values.md
rg -n "Runtime code was not ported|Import Policy|No actual access codes" docs/reference/print-farm-os
```

Expected: `test` commands succeed and `rg` prints matching lines from the new files.

- [ ] **Step 6: Commit**

Run:

```bash
git add docs/reference/print-farm-os/README.md docs/reference/print-farm-os/excluded-sensitive-values.md
git commit -m "docs: add print farm os reference entrypoint"
```

Expected: commit succeeds.

---

### Task 2: Fixture Copy

**Files:**
- Create: `harness/fixtures/phase0/README.md`
- Create: `harness/fixtures/phase0/phase0-inventory.example.json`
- Create: `harness/fixtures/phase0/phase0-discovery-ignore.example.json`
- Create: `harness/fixtures/phase0/orca-smoke-cube.stl`
- Create: `harness/fixtures/phase0/orca-smoke-cube-centered.stl`
- Create: `harness/fixtures/phase0/not-printer-ready-placeholder.gcode.3mf`
- Create: `harness/fixtures/phase0/phase0-smoke.gcode.3mf`

- [ ] **Step 1: Create fixture directory**

Run:

```bash
mkdir -p harness/fixtures/phase0
```

Expected: command exits successfully.

- [ ] **Step 2: Copy safe fixtures from Print Farm OS**

Run:

```bash
install -m 0644 /tmp/print-farm-os/print-farm-os/config/phase0-inventory.example.json harness/fixtures/phase0/phase0-inventory.example.json
install -m 0644 /tmp/print-farm-os/print-farm-os/config/phase0-discovery-ignore.example.json harness/fixtures/phase0/phase0-discovery-ignore.example.json
install -m 0644 /tmp/print-farm-os/print-farm-os/fixtures/orca-smoke-cube.stl harness/fixtures/phase0/orca-smoke-cube.stl
install -m 0644 /tmp/print-farm-os/print-farm-os/fixtures/orca-smoke-cube-centered.stl harness/fixtures/phase0/orca-smoke-cube-centered.stl
install -m 0644 /tmp/print-farm-os/print-farm-os/fixtures/not-printer-ready-placeholder.gcode.3mf harness/fixtures/phase0/not-printer-ready-placeholder.gcode.3mf
install -m 0644 /tmp/print-farm-os/print-farm-os/fixtures/phase0-smoke.gcode.3mf harness/fixtures/phase0/phase0-smoke.gcode.3mf
```

Expected: all files are copied.

- [ ] **Step 3: Write fixture README**

Create `harness/fixtures/phase0/README.md` with this structure:

```markdown
# Phase 0 Fixtures

These fixtures were copied from Print Farm OS for Bambuddy harness planning and
test reference use.

Source repository: `https://github.com/bbangjun360/print-farm-os.git`
Source local path: `/tmp/print-farm-os/print-farm-os`

## Files

| File | Source | Bytes | SHA-256 | Notes |
| --- | --- | ---: | --- | --- |
| `phase0-inventory.example.json` | `config/phase0-inventory.example.json` | 2920 | `76473bb1bb3a962d6a42479dcb5eaa1b4ebdbe07bcceb92ea2236776feb96857` | Non-secret inventory example. |
| `phase0-discovery-ignore.example.json` | `config/phase0-discovery-ignore.example.json` | 80 | `9869ec62d34dc2b2b6675667eaac52f641e4feca73830ccac1bbde8f0b972a00` | Non-secret discovery ignore example. |
| `orca-smoke-cube.stl` | `fixtures/orca-smoke-cube.stl` | 1499 | `072dc859f04f3ab1adaf829e1d073cfa14d7f444d8e5cd478d671c2b0fffe1d6` | Tiny slicer smoke model. |
| `orca-smoke-cube-centered.stl` | `fixtures/orca-smoke-cube-centered.stl` | 1625 | `85fa6572b7c9eac48ec13a2574b57fb165008da899114122f0088d810a7970ae` | Centered slicer smoke model. |
| `not-printer-ready-placeholder.gcode.3mf` | `fixtures/not-printer-ready-placeholder.gcode.3mf` | 139 | `74ebcb7c445a1045d8c86521c6b591681cb2016ac0b33d3fbbd2d0f9c504807c` | Placeholder used to verify negative gates. |
| `phase0-smoke.gcode.3mf` | `fixtures/phase0-smoke.gcode.3mf` | 544 | `40ce6e71efa131340f609a3d6206af7c96cb271b9023e0808a4f39f5c279079d` | Smoke fixture from source repository. |

These fixtures are not production print files for a real printer unless a later
Work Package explicitly validates that use.
```

- [ ] **Step 4: Verify sizes and hashes**

Run:

```bash
wc -c harness/fixtures/phase0/phase0-inventory.example.json harness/fixtures/phase0/phase0-discovery-ignore.example.json harness/fixtures/phase0/orca-smoke-cube.stl harness/fixtures/phase0/orca-smoke-cube-centered.stl harness/fixtures/phase0/not-printer-ready-placeholder.gcode.3mf harness/fixtures/phase0/phase0-smoke.gcode.3mf
sha256sum harness/fixtures/phase0/phase0-inventory.example.json harness/fixtures/phase0/phase0-discovery-ignore.example.json harness/fixtures/phase0/orca-smoke-cube.stl harness/fixtures/phase0/orca-smoke-cube-centered.stl harness/fixtures/phase0/not-printer-ready-placeholder.gcode.3mf harness/fixtures/phase0/phase0-smoke.gcode.3mf
```

Expected byte sizes:

```text
2920 phase0-inventory.example.json
80 phase0-discovery-ignore.example.json
1499 orca-smoke-cube.stl
1625 orca-smoke-cube-centered.stl
139 not-printer-ready-placeholder.gcode.3mf
544 phase0-smoke.gcode.3mf
```

Expected SHA-256 values:

```text
76473bb1bb3a962d6a42479dcb5eaa1b4ebdbe07bcceb92ea2236776feb96857  phase0-inventory.example.json
9869ec62d34dc2b2b6675667eaac52f641e4feca73830ccac1bbde8f0b972a00  phase0-discovery-ignore.example.json
072dc859f04f3ab1adaf829e1d073cfa14d7f444d8e5cd478d671c2b0fffe1d6  orca-smoke-cube.stl
85fa6572b7c9eac48ec13a2574b57fb165008da899114122f0088d810a7970ae  orca-smoke-cube-centered.stl
74ebcb7c445a1045d8c86521c6b591681cb2016ac0b33d3fbbd2d0f9c504807c  not-printer-ready-placeholder.gcode.3mf
40ce6e71efa131340f609a3d6206af7c96cb271b9023e0808a4f39f5c279079d  phase0-smoke.gcode.3mf
```

- [ ] **Step 5: Commit**

Run:

```bash
git add harness/fixtures/phase0
git commit -m "test: import print farm os phase0 fixtures"
```

Expected: commit succeeds.

---

### Task 3: Test Evidence Index

**Files:**
- Create: `docs/reference/print-farm-os/test-evidence/INDEX.md`

- [ ] **Step 1: List source evidence candidates**

Run:

```bash
find /tmp/print-farm-os/docs/3d-printing-automation -maxdepth 1 -type f -name '*.md' -printf '%f\n' | sort
find /tmp/print-farm-os/print-farm-os/tests -maxdepth 1 -type f -name 'test_*.py' -printf '%f\n' | sort
```

Expected: command prints Print Farm OS planning/result markdown files and test module names.

- [ ] **Step 2: Write the master evidence index**

Create `docs/reference/print-farm-os/test-evidence/INDEX.md` with these sections and table columns:

```markdown
# Print Farm OS Test Evidence Index

This index tracks the Print Farm OS test and validation evidence imported for
Bambuddy planning.

## Source Groups

| Group | Source paths | Import action | Bambuddy relevance |
| --- | --- | --- | --- |
| Phase 0 protocol checks | `docs/3d-printing-automation/02-phase0-protocol-validation.md`, `phase0-run-2026-06-08.md`, `print-farm-os/tests/test_phase0_*.py` | Summarized and indexed with lab context preserved | Future printer preflight, artifact gate, protocol simulator, and first-printer canary work. |
| A1 / AMS Lite gates | `02a-a1-ams-lite-preflight-gate.md`, `10-a1-unattended-cell-hazard-checklist.md`, `12-a1-unattended-pilot-protocol.md`, `test_phase0_a1_*.py`, `test_phase0_ams_*.py` | Summarized and indexed with lab context preserved | Bed automation, manual review, AMS gating, and unattended-cell safety criteria. |
| Orca/Bambu slicer flow | `02b-orcaslicer-bambu-print-flow.md`, `test_m11_orca_runtime_smoke.py`, `test_m11_slicing_artifacts.py`, `test_phase0_slicing_upload_candidate.py`, fixture files | Summarized; safe fixtures copied | Existing Bambuddy slicer sidecar and artifact compatibility checks. |
| Bambu error references | `02c-bambulab-wiki-error-reference.md`, `test_phase0_bambu_wiki_hms.py`, `test_phase0_printer_error_policy.py` | Summarized and indexed | HMS/error policy and stop-condition docs. |
| MVP production core | `03-mvp-functional-spec.md`, `04-mvp-implementation-plan.md`, `test_m3_*.py`, `test_m10_*.py`, `test_m18_*.py`, `test_m19_*.py`, `test_m20_*.py`, `test_m21_*.py` | Summarized | Product/SKU, WorkOrder, Queue Approval, Queue Reservation, Reprint, and software happy path candidates. |
| Runtime and UI validation | `10-mvp-current-status-20260616T0330KST.md`, `11-mvp-runtime-closeout-20260616T1248KST.md`, `14-ui-verification-and-design-runbook.md`, `15-stitch-ui-generation-brief.md`, `16-stitch-ui-output-review.md`, `test_m15_*.py`, `test_m17_*.py` | Summarized | Future operator UI and compose/runtime verification. |
| Execution ledgers and checkpoints | `09-execution-progress-ledger.md`, `13-validation-checkpoint-2026-06-09-1100.md` | Summarized | Evidence tracking format and Work Package handoff discipline. |

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
- Lab context is allowed when copied or summarized.
- Actual access codes, API tokens, passwords, private keys, customer data, and
  personal data are excluded.
```

- [ ] **Step 3: Verify index coverage terms**

Run:

```bash
rg -n "Phase 0 protocol|A1 / AMS Lite|Orca/Bambu slicer|MVP production core|Queue Reservation|Reprint" docs/reference/print-farm-os/test-evidence/INDEX.md
```

Expected: each major evidence group appears.

- [ ] **Step 4: Commit**

Run:

```bash
git add docs/reference/print-farm-os/test-evidence/INDEX.md
git commit -m "docs: index print farm os test evidence"
```

Expected: commit succeeds.

---

### Task 4: Evidence Summary Documents

**Files:**
- Create: `docs/reference/print-farm-os/test-evidence/phase0-results.md`
- Create: `docs/reference/print-farm-os/test-evidence/mvp-runtime-results.md`
- Create: `docs/reference/print-farm-os/test-evidence/validation-checkpoints.md`

- [ ] **Step 1: Inspect source result headings**

Run:

```bash
rg -n "^#{1,3} " /tmp/print-farm-os/docs/3d-printing-automation/phase0-run-2026-06-08.md /tmp/print-farm-os/docs/3d-printing-automation/10-mvp-current-status-20260616T0330KST.md /tmp/print-farm-os/docs/3d-printing-automation/11-mvp-runtime-closeout-20260616T1248KST.md /tmp/print-farm-os/docs/3d-printing-automation/13-validation-checkpoint-2026-06-09-1100.md
```

Expected: headings print for Phase 0 run, MVP status, MVP closeout, and validation checkpoint.

- [ ] **Step 2: Write Phase 0 summary**

Create `docs/reference/print-farm-os/test-evidence/phase0-results.md` with these sections:

```markdown
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
```

- [ ] **Step 3: Write MVP runtime summary**

Create `docs/reference/print-farm-os/test-evidence/mvp-runtime-results.md` with these sections:

```markdown
# MVP Runtime Results

## Source Files

- `docs/3d-printing-automation/10-mvp-current-status-20260616T0330KST.md`
- `docs/3d-printing-automation/11-m2-implementation-scaffold.md`
- `docs/3d-printing-automation/11-mvp-runtime-closeout-20260616T1248KST.md`
- `docs/3d-printing-automation/14-ui-verification-and-design-runbook.md`
- `docs/3d-printing-automation/15-stitch-ui-generation-brief.md`
- `docs/3d-printing-automation/16-stitch-ui-output-review.md`
- `print-farm-os/tests/test_m15_runtime_quick_check.py`
- `print-farm-os/tests/test_m17_production_smoke.py`
- `print-farm-os/tests/test_m21_mvp_software_happy_path.py`

## Imported Result Themes

- Runtime quick checks focus on environment readiness before operator actions.
- Compose/runtime smoke checks give a useful pattern for Bambuddy harness health reports.
- UI verification docs define stable anchors and browser verification flows that can inform future Bambuddy operator UI work.
- Session handoff and support bundle ideas are useful for preserving state across long farm-debugging sessions.

## Bambuddy Mapping

| Print Farm OS concept | Bambuddy integration point |
| --- | --- |
| Runtime quick check | Existing `make harness-health`, support bundle, and system health page. |
| Compose runtime smoke | Existing harness Docker Compose and smoke scripts. |
| UI verification anchors | Future frontend tests around queue, file manager, and operator runbooks. |
| Session handoff | Work Package closeout docs and runbook evidence. |

## Import Decision

Use these results as reference patterns for future verification improvements.
Do not replace existing Bambuddy harness commands.
```

- [ ] **Step 4: Write validation checkpoint summary**

Create `docs/reference/print-farm-os/test-evidence/validation-checkpoints.md` with these sections:

```markdown
# Validation Checkpoints

## Source Files

- `docs/3d-printing-automation/09-execution-progress-ledger.md`
- `docs/3d-printing-automation/13-validation-checkpoint-2026-06-09-1100.md`
- `docs/3d-printing-automation/10-mvp-current-status-20260616T0330KST.md`
- `docs/3d-printing-automation/11-mvp-runtime-closeout-20260616T1248KST.md`
- `docs/3d-printing-automation/captures/session-handoff-*.md`
- `docs/3d-printing-automation/captures/validation-checkpoint-*.md`

## Imported Result Themes

- Progress ledgers distinguish current baseline, active safety rules, latest verification summary, open blockers, ready work, and next action lanes.
- Validation checkpoints make safe next commands explicit and state when not to advance.
- Session handoff captures runtime quick checks, setup blockers, credential capture session status, evidence timeline, and resume commands.

## Bambuddy Mapping

| Evidence pattern | Bambuddy use |
| --- | --- |
| Current baseline | Work Package start/end checklist. |
| Safety rules still active | PrintFlow, bed automation, and first-printer canary docs. |
| Latest verification summary | PR description and release gate evidence. |
| Current open blockers | `docs/runbooks/` and support bundle output. |
| Resume commands | Long-running harness debugging and operator handoff. |

## Import Decision

Adopt the evidence structure in future Work Package docs and runbooks. Keep raw
capture folders out of this initial import unless a later Work Package needs a
specific capture file for a characterization test.
```

- [ ] **Step 5: Verify summaries**

Run:

```bash
rg -n "Bambuddy Mapping|Import Decision|Source Files" docs/reference/print-farm-os/test-evidence
```

Expected: each of the three summary files has the expected sections.

- [ ] **Step 6: Commit**

Run:

```bash
git add docs/reference/print-farm-os/test-evidence/phase0-results.md docs/reference/print-farm-os/test-evidence/mvp-runtime-results.md docs/reference/print-farm-os/test-evidence/validation-checkpoints.md
git commit -m "docs: summarize print farm os validation evidence"
```

Expected: commit succeeds.

---

### Task 5: Models And Policies Reference

**Files:**
- Create: `docs/reference/print-farm-os/models-and-policies.md`

- [ ] **Step 1: Inspect source model and policy files**

Run:

```bash
sed -n '1,220p' /tmp/print-farm-os/print-farm-os/print_farm_os/core/production.py
sed -n '1,220p' /tmp/print-farm-os/print-farm-os/print_farm_os/core/quality.py
sed -n '1,220p' /tmp/print-farm-os/print-farm-os/print_farm_os/core/materials.py
sed -n '1,180p' /tmp/print-farm-os/print-farm-os/print_farm_os/phase0/artifact_gate.py
sed -n '1,220p' /tmp/print-farm-os/print-farm-os/print_farm_os/phase0/upload_eligibility.py
```

Expected: source model enums, dataclasses, QC taxonomy, material policy, artifact gate, and upload eligibility logic are visible.

- [ ] **Step 2: Write model and policy mapping**

Create `docs/reference/print-farm-os/models-and-policies.md` with these sections:

```markdown
# Print Farm OS Models And Policies

This file summarizes model and policy ideas from Print Farm OS. It does not
define Bambuddy runtime behavior.

## Source Files

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
```

- [ ] **Step 3: Verify policy coverage**

Run:

```bash
rg -n "QCReasonCode|Operator Task Policy|Artifact Gate|Direct Port Risk|Bambuddy target" docs/reference/print-farm-os/models-and-policies.md
```

Expected: each policy area appears.

- [ ] **Step 4: Commit**

Run:

```bash
git add docs/reference/print-farm-os/models-and-policies.md
git commit -m "docs: map print farm os models to bambuddy"
```

Expected: commit succeeds.

---

### Task 6: Feature Candidates

**Files:**
- Create: `docs/reference/print-farm-os/feature-candidates.md`

- [ ] **Step 1: Write candidate Work Package list**

Create `docs/reference/print-farm-os/feature-candidates.md` with these sections:

```markdown
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
```

- [ ] **Step 2: Verify candidate coverage**

Run:

```bash
rg -n "^## [1-7]\\.|Recommended Sequence|Artifact Gate|Product/SKU" docs/reference/print-farm-os/feature-candidates.md
```

Expected: seven candidates and the recommended sequence appear.

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/reference/print-farm-os/feature-candidates.md
git commit -m "docs: list print farm os feature candidates"
```

Expected: commit succeeds.

---

### Task 7: Final Verification

**Files:**
- Verify: `docs/reference/print-farm-os/**`
- Verify: `harness/fixtures/phase0/**`

- [ ] **Step 1: Verify destination inventory**

Run:

```bash
find docs/reference/print-farm-os harness/fixtures/phase0 -maxdepth 3 -type f | sort
```

Expected output includes:

```text
docs/reference/print-farm-os/README.md
docs/reference/print-farm-os/excluded-sensitive-values.md
docs/reference/print-farm-os/feature-candidates.md
docs/reference/print-farm-os/models-and-policies.md
docs/reference/print-farm-os/test-evidence/INDEX.md
docs/reference/print-farm-os/test-evidence/mvp-runtime-results.md
docs/reference/print-farm-os/test-evidence/phase0-results.md
docs/reference/print-farm-os/test-evidence/validation-checkpoints.md
harness/fixtures/phase0/README.md
harness/fixtures/phase0/not-printer-ready-placeholder.gcode.3mf
harness/fixtures/phase0/orca-smoke-cube-centered.stl
harness/fixtures/phase0/orca-smoke-cube.stl
harness/fixtures/phase0/phase0-discovery-ignore.example.json
harness/fixtures/phase0/phase0-inventory.example.json
harness/fixtures/phase0/phase0-smoke.gcode.3mf
```

- [ ] **Step 2: Verify fixture hashes**

Run:

```bash
sha256sum harness/fixtures/phase0/phase0-inventory.example.json harness/fixtures/phase0/phase0-discovery-ignore.example.json harness/fixtures/phase0/orca-smoke-cube.stl harness/fixtures/phase0/orca-smoke-cube-centered.stl harness/fixtures/phase0/not-printer-ready-placeholder.gcode.3mf harness/fixtures/phase0/phase0-smoke.gcode.3mf
```

Expected SHA-256 values:

```text
76473bb1bb3a962d6a42479dcb5eaa1b4ebdbe07bcceb92ea2236776feb96857  harness/fixtures/phase0/phase0-inventory.example.json
9869ec62d34dc2b2b6675667eaac52f641e4feca73830ccac1bbde8f0b972a00  harness/fixtures/phase0/phase0-discovery-ignore.example.json
072dc859f04f3ab1adaf829e1d073cfa14d7f444d8e5cd478d671c2b0fffe1d6  harness/fixtures/phase0/orca-smoke-cube.stl
85fa6572b7c9eac48ec13a2574b57fb165008da899114122f0088d810a7970ae  harness/fixtures/phase0/orca-smoke-cube-centered.stl
74ebcb7c445a1045d8c86521c6b591681cb2016ac0b33d3fbbd2d0f9c504807c  harness/fixtures/phase0/not-printer-ready-placeholder.gcode.3mf
40ce6e71efa131340f609a3d6206af7c96cb271b9023e0808a4f39f5c279079d  harness/fixtures/phase0/phase0-smoke.gcode.3mf
```

- [ ] **Step 3: Search for actual secret patterns**

Run:

```bash
rg -n "BEGIN .*PRIVATE KEY|PRINT_FARM_.*=.*[^<]|access_code.:.:[^<]|api[_-]?token.:.:[^<]|password.:.:[^<]" docs/reference/print-farm-os harness/fixtures/phase0
```

Expected: no matches for actual private keys, concrete access codes, API tokens, or passwords. Matches inside explanatory text or placeholder examples are acceptable only when they do not contain real values.

- [ ] **Step 4: Confirm runtime files were not changed**

Run:

```bash
git diff --name-only 40824210..HEAD | rg -v '^(docs/reference/print-farm-os/|harness/fixtures/phase0/|docs/superpowers/)'
```

Expected: no output.

- [ ] **Step 5: Run repository status check**

Run:

```bash
git status --short
```

Expected: clean worktree.

- [ ] **Step 6: Commit final documentation corrections**

Run this only when Step 1 through Step 5 revealed a documentation or fixture
correction that was made:

```bash
git add docs/reference/print-farm-os harness/fixtures/phase0
git commit -m "docs: finalize print farm os reference import"
```

Expected: commit succeeds when a correction was made. When no correction was
made, skip this step and leave the worktree clean.
