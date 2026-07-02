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

### GIT-01 Corrupt zero-byte git objects

- Symptom: `git fsck` reports 7 empty loose objects (first seen WP-066,
  2026-06-26). Commits currently work because the objects are unreachable,
  but `git gc`/`git clone` from this copy can fail.
- Workarounds seen: sessions moved to fresh `/tmp` worktrees instead of
  repairing (WP-066 note "commit flow blocked").
- Real fix: with human approval, move the zero-byte files out of
  `.git/objects/`, then `git fetch origin` to restore any that matter.
  Destructive-command rule applies: requires explicit operator approval.

### HARNESS-02 verify-full smoke needs the compose harness running

- Symptom: `make test-integration` (smoke.py) expects Bambuddy on
  `BAMBUDDY_PORT` (default 18000). On a checkout where the harness compose is
  not up, verify-full fails.
- Workarounds seen: WP-060 through WP-064 each started a throwaway localhost
  SQLite container to satisfy smoke. Do not repeat this.
- Real fix: make `test-integration` fail fast with a clear message when the
  harness is not up (distinct from a real smoke failure), or start/stop the
  harness inside the target. Root cause of "harness not up" was HARNESS-03.

### HARNESS-04 test-scenario discovers zero tests

- Symptom: `make test-scenario` discovers `scenario_*.py` and finds nothing,
  so verify-full's scenario stage is a no-op (gap noted since WP-010).
- Real fix: either add the first scenario test or make the target fail on
  zero collected tests so the gap stays visible.

### PROCESS-05 Frontend suite is outside the enforced gates

- Symptom: `verify-fast`/`verify-full` run Python only; `make test-frontend`
  and `make test-paper-export` exist but nothing enforces them, so frontend
  regressions pass the gates.
- Real fix: decide whether node is a required toolchain; if yes, add
  `test-frontend` to verify-full. Until then, any PR touching `frontend/`
  must run `make test-frontend` and say so in the PR.

### PROCESS-06 Stale ExecPlans

- Symptom: many ExecPlans under `workpacks/exec/` (WP-010, 030, 040, 050,
  063-*, 064-*) still show "commit/push/PR" unchecked although the PRs merged.
  The next session cannot trust Progress sections.
- Real fix: one hygiene pass updating Outcomes to match git history; from now
  on the same-PR update rule in AGENTS.md applies.

## FIXED

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
