# Print Farm OS Reference Import Design

## Goal

Import useful reference material from `https://github.com/bbangjun360/print-farm-os.git`
into the Bambuddy farm fork without changing runtime behavior.

The import should help finish the current project by preserving evidence,
fixtures, policies, and future feature candidates from Print Farm OS in a form
that is easy to use from Bambuddy work packages.

## Selected Approach

Use a reference-material import, not a code port.

The Print Farm OS repository contains useful production operations material:
Phase 0 printer safety gates, validation checkpoints, runtime closeouts, QC
taxonomy, product/work-order/queue model notes, and safe smoke fixtures. Its
runtime code overlaps with Bambuddy concepts such as `LibraryFile`,
`PrintQueueItem`, `Project`, `PrintLogEntry`, ERP adapters, slicer integration,
and label rendering. Copying that code directly would create duplicate models
and migration risk.

The import will therefore create a documented reference pack plus sanitized
fixtures. Future feature work can then cite the reference pack from a normal
Work Package.

## Scope

In scope:

- Create `docs/reference/print-farm-os/` with an index and topic summaries.
- Index all relevant Print Farm OS test and validation result documents.
- Copy safe static fixtures into `harness/fixtures/phase0/`.
- Summarize model and policy ideas that map cleanly to Bambuddy.
- List feature candidates with Bambuddy integration points and risk level.
- Record skipped or redacted source artifacts with reasons.

Out of scope:

- No Bambuddy backend, frontend, database, or scheduler behavior changes.
- No direct import of Print Farm OS runtime Python/TypeScript code.
- No new migrations.
- No real printer credentials, serials, access codes, tokens, customer data, or
  environment-specific local paths.
- No raw hardware-control capture copied verbatim when it may expose local lab
  details.

## Source Material

Primary source paths in the cloned Print Farm OS repository:

- `README.md`
- `docs/3d-printing-automation/*.md`
- `print-farm-os/README.md`
- `print-farm-os/config/*.example.json`
- `print-farm-os/fixtures/*`
- `print-farm-os/tests/test_*.py`
- `print-farm-os/print_farm_os/core/*.py`
- `print-farm-os/print_farm_os/phase0/*.py`
- `print-farm-os/backend/migrations/*.sql`

The import should keep source path references in indexes so future work can
trace each summary back to the original file.

## Destination Layout

Create this structure:

```text
docs/reference/print-farm-os/
  README.md
  test-evidence/
    INDEX.md
    phase0-results.md
    mvp-runtime-results.md
    validation-checkpoints.md
  models-and-policies.md
  feature-candidates.md
  skipped-or-redacted.md

harness/fixtures/phase0/
  phase0-inventory.example.json
  phase0-discovery-ignore.example.json
  orca-smoke-cube.stl
  orca-smoke-cube-centered.stl
  not-printer-ready-placeholder.gcode.3mf
  phase0-smoke.gcode.3mf
```

## Evidence Import Rule

All relevant test and validation results should be represented in the reference
pack, but not all raw files should be copied byte-for-byte.

Use this classification:

- Copy: generic docs, example configs, safe fixtures, static test names, and
  sanitized result summaries.
- Summarize: validation checkpoints, runtime closeouts, execution ledgers, and
  capture indexes that may include local state.
- Redact or skip raw copy: files with IP addresses, serial numbers, access-code
  status tied to a real lab, local Windows paths, generated capture logs, or
  hardware-control details that are not needed for Bambuddy planning.

Every skipped or redacted source must be listed in
`docs/reference/print-farm-os/skipped-or-redacted.md` with a short reason.

## Test Evidence Index

`test-evidence/INDEX.md` should group evidence into:

- Phase 0 protocol and safety checks.
- Printer discovery, TLS, FTPS, MQTT, camera, and credential readiness.
- 3MF/artifact inspection and upload eligibility checks.
- Orca/Bambu slicer runtime smoke results.
- MVP runtime, compose, UI verification, and closeout results.
- Production-core test coverage from `print-farm-os/tests/test_*.py`.

Each row should include:

- source file path,
- evidence type,
- status when available,
- date when available,
- Bambuddy relevance,
- import action: copied, summarized, redacted, or skipped.

## Model And Policy Summary

`models-and-policies.md` should summarize, not port, these useful ideas:

- Product/SKU and product variant model.
- File asset verification and artifact release model.
- Work order and queue item status model.
- QC outcome, QC reason taxonomy, and reprint request flow.
- Operator task types: bed clear, QC, material change, label attach, adapter
  failure.
- Material batch, material mount, consumption, variance, and reorder concepts.
- Label print job and label printer capability tracking.
- Traceability event and location concepts.
- Phase 0 artifact gate and upload eligibility rules.
- A1 unattended cell hazard checklist concepts.

For each idea, include the likely Bambuddy integration point, for example
`LibraryFile`, `PrintQueueItem`, `PrintLogEntry`, existing label APIs, ERP work
packages, or bed automation work packages.

## Feature Candidates

`feature-candidates.md` should recommend future Work Packages, ordered by
near-term value:

1. QC reason taxonomy for failed prints and reprints.
2. Artifact gate before dispatch: printer/profile compatibility and
   printer-ready checks.
3. Operator tasks for bed clear, material change, QC, and label attach.
4. Product/SKU-based work orders mapped onto Bambuddy projects and queue items.
5. Label print job tracking tied to queue items and printed units.
6. Material batch and consumption variance tracking.
7. Phase 0 readiness/preflight runbook UI or report.

Each candidate should include value, source references, Bambuddy touch points,
risks, and recommended first test.

## Error Handling

If a source file cannot be copied safely:

- do not copy it,
- summarize only the useful public/non-sensitive outcome,
- list it in `skipped-or-redacted.md`,
- prefer source path references over embedding sensitive raw output.

If a fixture format is unclear or potentially executable against real hardware:

- copy only if it is a harmless test fixture,
- add a note in the fixture README,
- never present it as a printer-ready production artifact.

## Verification

Before claiming completion:

- Check that every intended destination file exists.
- Check that copied fixture names and sizes match the source.
- Search the imported docs for obvious secrets and local-only values:
  `access_code`, `token`, `password`, `serial`, private IP-looking strings, and
  local Windows user paths.
- Run the narrowest relevant repository checks:
  `git status --short` and a documentation/fixture inventory command.

No application tests are required for this reference-only import because no
runtime code changes are planned.

## Approval Gate

After this design is written and reviewed, implementation can proceed by
creating the reference pack and fixture copy described above. Runtime feature
implementation requires a separate Work Package and implementation plan.
