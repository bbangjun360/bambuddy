# Purpose

Integrate the official Bambuddy stable release v0.2.4.9 into the customized
farm fork while preserving printer-command ownership, bed-readiness gates,
Draft-only ERP behavior, and a runnable rollback point.

# Current Behavior

- origin/farm-main is at merge commit 5614c91b and has a green
  make verify-fast baseline with 189 harness tests and two characterization
  tests before this integration starts.
- The common upstream base is 1b7d6615528843ee0500eae4390ab23e2e5916ef,
  described as v0.2.4.7-4-g1b7d6615.
- The target stable tag is v0.2.4.9 at
  15242fe36ec262e4f1d97fb89e78494b7b9881af.
- The farm core-patch ledger tracks
  backend/app/services/print_scheduler.py and the scheduler handoff identity
  guard that must execute before upload, queue mutation, bed-clear mutation,
  or printer start.

# Scope

In scope:

- Merge official stable tags v0.2.4.8 and v0.2.4.9 through the v0.2.4.9 tag.
- Resolve conflicts in upstream-owned files without removing farm extensions.
- Preserve farm API routes, models, configuration, scheduler safety gates, and
  frontend farm settings.
- Rebuild generated frontend assets from the resolved frontend source.
- Add characterization coverage and an upstream impact report.

Out of scope:

- Upstream main commits after v0.2.4.9 or the v0.2.5 beta/daily line.
- Production deployment, database migration execution, or physical canary.
- WP-110 changes, a UI redesign, feature-flag enablement, or new farm behavior.
- Automatic merge into farm-main.

# Architecture Boundaries

- Bambuddy remains the sole printer state-changing command authority.
- Missing plate-clear configuration remains fail-closed in the farm fork.
- The SwapMod scheduler handoff identity guard remains before all external and
  state-changing scheduler effects.
- Bed uncertainty remains MANUAL_REVIEW; no uncertain action auto-resumes.
- Farm automation and ERP posting flags remain disabled by default.
- Generated static assets are outputs of the resolved frontend source.

# Milestones

1. Record exact revisions, release notes, changed paths, conflicts, and risk.
2. Add farm scheduler safety characterization before merging upstream.
3. Merge v0.2.4.9 and resolve source conflicts with explicit preservation
   decisions.
4. Run focused scheduler, backend, frontend, contract, integration, and full
   gates; repair only integration regressions.
5. Complete the impact report, rollback notes, and operator-gated Draft PR.

# Progress

- [x] 2026-07-13: Read charter, known issues, backlog, upstream-update skill,
  patch ledger, and ExecPlan rules.
- [x] 2026-07-13: Recorded old/new SHAs and official v0.2.4.8/v0.2.4.9 release
  notes.
- [x] 2026-07-13: Baseline make verify-fast passed.
- [x] 2026-07-13: Previewed seven merge conflicts and sixteen changed-path
  overlaps.
- [x] 2026-07-13: Merged and resolved v0.2.4.9 while preserving custom routes,
  models, SwapMod scheduler guards, and the fail-closed plate-clear default.
- [x] 2026-07-13: Passed focused scheduler gates, 7,053 backend tests, 2,305
  frontend tests, 2,405 live-container integration tests, make verify-fast,
  make test-contract, make verify-full, and desktop/mobile browser checks.
- [x] 2026-07-13: Published operator-gated Draft PR #92. The operator approved
  it and GitHub merged it into `farm-main` as `9ec919af`.
- [x] 2026-07-14: Refreshed upstream release metadata. v0.2.4.9 remains the
  latest stable release. `v0.2.5b2-daily.20260713` is a prerelease and remains
  outside this integration's approved scope.

# Decisions

- Target the latest stable release v0.2.4.9, not upstream main or v0.2.5 beta.
- Classify the integration as R4 because upstream changes queue dispatch,
  scheduler cancellation, printer-card controls, permissions, and the
  plate-clear default.
- Preserve the farm fork's fail-closed plate-clear default even though upstream
  v0.2.4.9 changes the unset default to off.
- Rebuild frontend assets after resolving source; do not hand-merge generated
  JavaScript or HTML hashes.

# Harness Changes

- Add harness/tests/test_upstream_scheduler_safety.py to lock the farm's
  fail-closed missing-setting behavior.
- Retain existing SwapMod scheduler handoff architecture and focused behavior
  suites.
- Add integration repair tests only when the merge exposes an uncovered
  contract regression.

# Implementation

- Merge v0.2.4.9 into integration/upstream-v0.2.4.9.
- Resolve .gitignore, backend/app/main.py,
  backend/app/models/__init__.py,
  backend/app/services/print_scheduler.py,
  frontend/src/pages/SettingsPage.tsx, and generated static conflicts.
- Complete UPSTREAM_IMPACT_REPORT.md with file/symbol overlap, migration,
  staging, canary, and rollback evidence.

# Validation

Run:

1. python3 -m unittest harness.tests.test_upstream_scheduler_safety
2. make verify-fast
3. Existing SwapMod scheduler handoff and queue-readiness focused targets.
4. Backend upstream tests and make test-frontend.
5. make test-contract and make test-integration.
6. make verify-full with the local harness running.
7. Browser verification of the updated upstream UI before UI redesign work.

# Failure and Recovery

- Abort the integration merge before commit if custom safety behavior cannot be
  preserved mechanically.
- No production deployment occurs from this branch.
- Rollback is farm-main merge commit 5614c91b; database backup and restore are
  mandatory before any later staging migration.
- Any uncertain scheduler, printer, migration, or physical behavior blocks the
  integration PR and is recorded in the impact report.

# Risks and Human Gates

- R4: scheduler and queue changes can start a print, alter cancellation timing,
  or bypass a physical-bed hold.
- Auto-migrated upstream columns require a staging backup/restore rehearsal.
- Permission changes can affect custom operator groups and API keys.
- PR #92 received explicit operator approval before merge. Production rollout,
  migration rehearsal, permission review, and any physical canary remain
  separately operator-gated.

# Outcomes

The source integration was operator-approved and merged into `farm-main` through
PR #92. Bambuddy starts from the merged production image, serves its root,
health, and API documentation endpoints, and preserves the farm scheduler
handoff guard. Missing
require_plate_clear configuration remains fail-closed across backend behavior,
the settings contract, and the UI; explicitly stored false remains supported.

No deployment, database migration, or physical command was executed. Staging
backup/restore rehearsal, permission review, simulated cancellation and
plate-clear exercises, and any later named-printer canary remain operator-gated.
The integrated release remains R4 for rollout even though the source PR was
approved and merged.
