# Upstream Impact Report: Bambuddy v0.2.4.9

Status: validation complete; Draft PR and operator review required

## Revisions

- Fork base: origin/farm-main at
  5614c91b4bec08fe5bce2f891d5048984574eb1c
- Old upstream baseline:
  1b7d6615528843ee0500eae4390ab23e2e5916ef
  (v0.2.4.7-4-g1b7d6615)
- New upstream stable tag: v0.2.4.9
- New upstream SHA: 15242fe36ec262e4f1d97fb89e78494b7b9881af
- Upstream range: 290 commits, 413 files, 74,133 insertions, 20,714 deletions

## Release Summary

v0.2.4.8 routes all direct and ASAP prints through the scheduler queue, changes
the required permission from printer control to queue creation, refreshes the
printer-card UI, and adds maintenance, AMS backup, OIDC, notification, and
dependency updates.

v0.2.4.9 adds atomic cancel-during-dispatch protection, FTS routing fixes,
permission migration, preheat support, UI contrast fixes, and changes the
upstream missing-setting default for plate-clear confirmation from on to off.

Official release notes:

- https://github.com/maziggy/bambuddy/releases/tag/v0.2.4.8
- https://github.com/maziggy/bambuddy/releases/tag/v0.2.4.9

## Custom Overlap

The upstream and farm ranges both modify:

- .gitignore
- backend/app/api/routes/library.py
- backend/app/core/config.py
- backend/app/core/database.py
- backend/app/main.py
- backend/app/models/__init__.py
- backend/app/services/print_scheduler.py
- backend/tests/conftest.py
- backend/tests/integration/test_library_slice_api.py
- frontend/package.json
- frontend/package-lock.json
- frontend/src/api/client.ts
- frontend/src/pages/SettingsPage.tsx
- generated static assets and static/index.html

Previewed conflicts:

- .gitignore
- backend/app/main.py
- backend/app/models/__init__.py
- backend/app/services/print_scheduler.py
- frontend/src/pages/SettingsPage.tsx
- generated static JavaScript rename/rename
- static/index.html

## Safety And Contract Decisions

- Preserve require_plate_clear missing-setting default as True in the farm
  fork. Upstream's off default conflicts with the farm invariant that the next
  print waits for verified bed readiness.
- Preserve the WP-082 scheduler source-print-run and source-cycle identity guard
  before upload, queue status mutation, plate-clear mutation, or printer start.
- Integrate upstream's atomic cancellation and queue fixes around the farm
  guards rather than reverting them.
- Keep every farm automation and ERP write feature disabled by default.
- Keep custom routers, models, diagnostics, and adapters registered.
- Rebuild static assets from resolved frontend source.

## Migration And Permissions

- The releases declare no breaking schema migration but include auto-migrated
  column additions for SQLite and PostgreSQL.
- Back up the staging database before first boot and rehearse restore.
- Review custom groups for queue:create and WEBSOCKET_CONNECT.
- Review API-key scopes for maintenance, projects, and archives; new scopes
  migrate off unless explicitly granted.

## Risk

Risk: **R4**

Reasons:

- Scheduler and queue dispatch behavior changes.
- Printer-card control changes.
- Plate-clear default conflicts with a farm safety invariant.
- Database and permission migrations.
- Direct overlap with the existing scheduler core patch recorded in
  .fuzzyline/PATCH_LEDGER.yaml.

## Staging, Canary, And Rollback

- No deployment from the integration branch.
- First boot occurs only on staging with a database backup and restore proof.
- Validate queue cancellation, plate-clear hold, SwapMod READY handoff, and
  custom operator permissions without a real printer command.
- Any later hardware canary requires a named printer, present operator,
  emergency stop, power cutoff, and reviewed dry run.
- Roll back code to 5614c91b; restore the pre-migration database backup when
  schema compatibility requires it.

## Validation Evidence

- Pre-merge make verify-fast: passed, 189 harness tests and two
  characterization tests.
- Merge characterization: passed after preserving scheduler, schema, and UI
  fail-closed defaults.
- Focused SwapMod scheduler gates passed:
  scheduler handoff chain (2 mock and 3 backend tests), scheduler queue-readiness
  binding (2 mock and 19 backend tests), queue-readiness binding (2 mock and 27
  backend tests), and scheduler next-print gate (2 mock and 13 backend tests).
- Full backend image suite: 7,053 passed and 4 skipped.
- Full frontend suite: 175 files and 2,305 tests passed; all 11 locales contain
  5,576 leaves and remain in parity.
- Production frontend and Docker image builds: passed. The generated bundle
  still emits the upstream chunk-size warning for the 8.18 MB JavaScript file.
- Live production-container integration suite: 2,405 passed.
- make verify-fast: passed with 190 harness tests and two characterization
  tests after integration.
- make test-contract: passed with 190 harness tests.
- make verify-full: passed against the integration app on port 8001 and the
  isolated mock-services harness on port 19130.
- Headless Chrome checks at 1440x1000 and 390x844: initial setup UI rendered
  without clipping or overlap and without a fatal JavaScript exception. The
  upstream bundle reports a non-fatal duplicate Three.js import warning.

## Remaining Operator-Gated Work

- No production deployment or physical printer command was executed.
- Rehearse database backup and restore on staging before accepting migrations.
- Audit custom groups and API keys for queue:create, WEBSOCKET_CONNECT, and new
  maintenance/project/archive scopes.
- Exercise queue cancellation and the plate-clear hold with simulated printers,
  then perform any hardware canary only under the named-device checklist.
- Keep the integration PR in Draft until the operator reviews this R4 evidence.
