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

This list names the reference-pack contents imported for Bambuddy planning.

- `test-evidence/INDEX.md` - master index of imported test and validation evidence.
- `test-evidence/phase0-results.md` - Phase 0 safety and protocol evidence.
- `test-evidence/mvp-runtime-results.md` - MVP runtime and compose evidence.
- `test-evidence/validation-checkpoints.md` - validation checkpoints and handoff notes.
- `models-and-policies.md` - model and policy ideas mapped to Bambuddy concepts.
- `feature-candidates.md` - recommended future Work Packages.
- `config-and-env-keys.md` - configuration, environment, JSON, and sensitive-key names with placeholders.
- `excluded-sensitive-values.md` - actual secret values or personal data excluded from import.

## Import Policy

Preserve lab evidence when useful, including IP addresses, printer serials,
timestamps, and local file paths. Do not import actual access codes, API tokens,
passwords, private keys, customer data, or personal data.

## Fixtures

Safe example fixtures copied from Print Farm OS live under
`harness/fixtures/phase0/`. They are for harness and planning use only.
