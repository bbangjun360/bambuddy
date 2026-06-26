# Phase 0 Fixtures

No Print Farm OS raw sample artifacts are kept in this directory.

## Reference-Only Policy

`origin/codex/print-farm-os-reference-import` is reference-only. Do not copy
source 3MF files, raw G-code, output 3MF files, generated artifacts, logs,
printer access codes, serial numbers, IP addresses, tokens, env files, or
customer data from it.

Reusable Print Farm OS findings belong in redacted docs and tests, not in
tracked sample-artifact dependencies. Future work that needs sample data must
create synthetic fixtures inside its own Work Package and keep any automation
behind default-off flags and simulator/canary gates.
