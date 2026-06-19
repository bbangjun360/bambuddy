---
name: upstream-update
description: Integrate a new upstream release into a customized fork with impact analysis, preserved custom behavior, and no automatic merge.
---

1. Read `AGENTS.md` and `.fuzzyline` manifests.
2. Record old/new tags and exact SHAs.
3. Compare actual changed files and symbols.
4. Identify overlap with custom paths, contracts, migrations, auth, queue, printer
   commands, slicer behavior, ERP posting, and bed automation.
5. Add or update characterization tests before adapting custom code.
6. Produce `UPSTREAM_IMPACT_REPORT.md`.
7. Preserve custom behavior until an explicit migration plan is tested.
8. Run upstream, custom, contract, and integration gates.
9. Assign risk R0-R4 and document staging/canary/rollback.
10. Do not merge or deploy automatically.
