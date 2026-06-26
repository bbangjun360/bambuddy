# Print Farm OS Reference Policy

This directory preserves redacted policy and test-result findings from Print Farm
OS for Bambuddy farm planning.

Runtime code and raw artifacts were not ported. Use this reference material only
to inform future Bambuddy Work Packages.

## Source

- Reference branch: `origin/codex/print-farm-os-reference-import`
- Imported into Bambuddy path: `docs/reference/print-farm-os/`

## Allowed Use

- Inspect redacted notes.
- Inspect high-level test conclusions.
- Reference safe source paths when they are not sensitive.
- Convert conclusions into Bambuddy-native docs or tests for the active Work
  Package.

## Forbidden Use

Do not merge the branch, cherry-pick it, or copy raw 3MF, raw G-code, output
3MF, generated artifacts, logs, env files, printer access codes, serial numbers,
IP addresses, tokens, or customer data.

Do not add printer upload/start behavior, live command execution, or a real
sample dependency to CI from this reference material.

## Contents

- `config-and-env-keys.md` - policy for preserving key names and placeholder
  shapes only.
- `excluded-sensitive-values.md` - categories of sensitive values and artifacts
  excluded from import.
- `test-evidence/INDEX.md` - index of allowed test-evidence summaries.
- `test-evidence/phase0-results.md` - Phase 0 reference summary policy.

## Fixtures

No Print Farm OS source fixtures are tracked for this reference pack.
`harness/fixtures/phase0/README.md` records the no-artifact policy only.
