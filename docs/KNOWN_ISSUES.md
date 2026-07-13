# Known Issues

Living registry of defects in the repository, harness, or process that more
than one session may hit. Read this before starting any task (AGENTS.md read
order step 2).

Rules:

- If your task would hit an OPEN issue, fix or unblock it first. Do not add
  another local workaround.
- If you work around anything not listed here, add it here in the same PR.
- When an issue is fixed, set its status to FIXED with the date and commit;
  do not delete the entry for one release cycle.

## OPEN

No known open repository, harness, or process defects are currently blocking the
next highest backlog item. Add new repeated defects here instead of carrying
local workarounds between sessions.

## FIXED

### PROCESS-07 Stacked Work Package PRs skipped Validation — FIXED 2026-07-14

- Was: `.github/workflows/validation.yml` ran for pull requests targeting
  `farm-main` only. A stacked Work Package PR targeting a `feature/wp-*`
  branch required repeated manual workflow dispatches to obtain the same gate.
- Fix: `FIX_COMMIT` extends the existing base-branch filter to
  `feature/wp-*` and adds a harness contract test while retaining
  `workflow_dispatch`. Workflow permissions, jobs, and product behavior are
  unchanged.

### PROCESS-06R Upstream integration docs stayed Draft after merge — FIXED 2026-07-14

- Was: operator-approved upstream PR #92 merged v0.2.4.9 into `farm-main`, but
  its ExecPlan still left publication unchecked and the impact report still
  described the integration PR as awaiting review.
- Fix: commit `9f05aea3` records the merged state in both documents and adds a
  2026-07-14 freshness check. v0.2.4.9 remains the latest stable release;
  v0.2.5b2 daily builds remain prerelease and outside the approved scope.

### UI-01 Settings requests protected 2FA status when auth is disabled — FIXED 2026-07-14

- Was: opening Settings with authentication disabled still requested
  `/api/v1/auth/2fa/status`. The endpoint correctly returned 401, and the
  browser then retried the avoidable protected request.
- Fix: commit `8a930df1` gates the current-user 2FA query on `authEnabled`.
  Regression tests assert zero calls while authentication is disabled and
  preserve the authenticated-user request when authentication is enabled.

### HARNESS-02 verify-full smoke needs the compose harness running — FIXED 2026-07-02

- Was: `make test-integration` waited through the full smoke readiness timeout
  when no local Bambuddy/mock harness was listening, then emitted only a generic
  connection-refused smoke failure. WP-060 through WP-064 worked around this with
  temporary localhost containers.
- Fix: `harness/scripts/smoke.py` now preflights loopback smoke targets and exits
  with structured `reason: harness_not_running` guidance before the readiness
  loop. A listening-but-unhealthy app still fails through the normal smoke path.

### HARNESS-04 test-scenario discovers zero tests — FIXED 2026-07-02

- Was: earlier `make test-scenario` runs discovered no scenario tests, leaving
  verify-full's scenario stage as a no-op.
- Fix: `harness/tests/scenario_baseline_harness.py` is present and
  `make test-scenario` runs two synthetic loopback scenario tests.
  `test_makefile_contract.py` now asserts that the scenario target has at least
  one checked-in `scenario_*.py` file to discover.

### PROCESS-05 Frontend suite is outside the enforced gates — FIXED 2026-07-02

- Was: frontend changes were not represented in shared validation policy.
- Fix: Node is not a required toolchain for non-frontend farm validation. The
  Makefile now provides explicit `test-frontend` and `frontend-gate-check`
  targets, and `verify-fast`/`verify-full` run the gate check. If a PR changes
  `frontend/`, the gate requires `make test-frontend` evidence and an explicit
  `FRONTEND_TESTED=1` rerun.

### PROCESS-06 Stale ExecPlans — FIXED 2026-07-02

- Was: old ExecPlans under `workpacks/exec/` still showed PR creation pending
  although their branches had merged.
- Fix: WP-010, WP-030, WP-040, WP-050, WP-063-A/B/C, and WP-064-A/B/C/D now
  carry concise hygiene notes with the local merge/PR evidence. The same-PR
  update rule in `AGENTS.md` remains the forward process.

### GIT-01 Corrupt zero-byte git objects — FIXED 2026-07-02

- Was: `git fsck` reported 7 empty loose objects (first seen WP-066,
  2026-06-26); sessions moved to fresh `/tmp` worktrees instead of repairing.
- Fix: with operator approval, the zero-byte files were moved out of
  `.git/objects/` and objects re-fetched from origin; `git fsck` is clean.
  This applies to the primary local clone; if another clone shows the same
  symptom, repeat the same operator-approved procedure.


### HARNESS-03 `.env.harness.example` shipped broken placeholders — FIXED 2026-07-02

- Was: tracked example had `postgres:REPLACE@sha256:REPLACE` etc., so every
  fresh checkout/worktree could not start the compose harness; the working
  digests lived only in the untracked local `.env.harness`. This manufactured
  HARNESS-02 on every new worktree.
- Fix: example now carries real public image digests (they are pins, not
  secrets). Passwords remain synthetic local-only values. Additionally,
  `test_orca_wp010_contract.py` read the untracked `.env.harness` directly,
  so `make verify-fast` itself failed on every fresh checkout/worktree since
  WP-010; it now falls back to the example file when the local file is absent.

### PROCESS-01 WP number collisions between parallel tracks — FIXED 2026-07-02

- Was: numbers were allocated per-session by guess; WP-080 and WP-105 were
  each minted twice on different branches.
- Fix: allocation rule in AGENTS.md (max across origin/farm-main and open
  feature/wp-* branches, plus reserved WP-9xx off-track range).
