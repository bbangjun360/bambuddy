---
name: harness-verify
description: Diagnose and repair the farm repository test harness, smoke checks, fixtures, and deterministic CI gates.
---

Run the narrowest failing gate first. Preserve the product behavior while fixing the
harness. Never make a test pass by deleting assertions, broadening timeouts without
evidence, or skipping a failing suite.

Classify failures as:

- product regression
- stale fixture
- contract mismatch
- environment/setup
- nondeterminism/race
- external dependency
- harness defect

Return the classification, evidence, fix, and commands run.
