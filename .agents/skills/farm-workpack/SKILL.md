---
name: farm-workpack
description: Plan or implement one 3D print farm Work Package while keeping Bambuddy runnable and scope limited.
---

1. Read the root `AGENTS.md`, project charter, and exactly one Work Package.
2. Restate Goal, Context, Constraints, and Done-when.
3. Inspect existing Bambuddy behavior before proposing new code.
4. Create a characterization test for modified upstream behavior.
5. Add harness fixtures, fake behavior, and failure scenarios before product code.
6. Implement one observable vertical slice behind a default-off feature flag.
7. Run `make verify-fast`, then the Work Package's exact tests.
8. Review the diff for scope creep, core patches, secrets, and missing rollback.
9. Update the Work Package or ExecPlan with evidence.
