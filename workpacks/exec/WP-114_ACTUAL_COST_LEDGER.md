# WP-114 Actual Cost Ledger

## Observable outcome

Give farm operators a read-only, per-run cost ledger that compares the slicer
estimate snapshot with actual material, energy, and machine-time cost in KRW.
Original runs, failed runs, and reprints remain separate rows and separate
summary buckets instead of being collapsed into one archive total.

This Work Package may consult only the WP-05 and related acceptance clauses in
`docs/archive/FULL_SPEC_v1.1.md`; the rest of the archive remains out of scope.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `docs/KNOWN_ISSUES.md`
- `workpacks/BACKLOG.md`
- `.agent/PLANS.md`
- The print-log, archive-statistics, settings, and cost test modules named below
- Only WP-05 and its related acceptance clauses in `docs/archive/FULL_SPEC_v1.1.md`

# Current Behavior

- `backend/app/models/print_log.py::PrintLogEntry` stores one row per actual
  run with status, duration, filament, material cost, energy, and energy cost.
- `backend/app/services/print_log.py::write_log_entry` writes the row when a
  print finishes. Reprints already create distinct rows.
- `backend/app/api/routes/archives.py::get_archive_stats` aggregates material
  and energy totals but does not expose an accounting ledger, estimate
  snapshots, machine-time cost, or failed/reprint cost buckets.
- `backend/app/api/routes/print_log.py::get_print_log` returns run metadata but
  currently omits the model's cost and energy fields from its explicit
  serializer.
- Bambuddy has `currency` and `energy_cost_per_kwh` settings. There is no
  machine-hour rate and no currency conversion contract.

Observed on 2026-07-13 from `origin/farm-main` at merge commit `e82b0488` and
the existing print-log/statistics tests.

## In scope

- A farm-owned additive snapshot table linked one-to-one to a retained
  `PrintLogEntry`.
- A default-off feature flag and a non-negative machine-hour rate.
- Immutable estimate/rate snapshots captured with each enabled run.
- A read-only, paginated API with run rows and totals for completed, failed,
  cancelled, original, and reprint buckets.
- KRW-only operation for this slice. Capture fails closed when Bambuddy's
  configured currency is not KRW; no implicit currency relabeling.
- Characterization, unit, integration, migration, authorization, and
  missing-data tests.

## Out of scope

- UI changes, invoices, ERP writes, inventory/accounting postings, exchange
  rates, profitability, tax, labor allocation, or automatic queue behavior.
- FULL_SPEC WP-05's labor, overhead, closing/adjustment, and ERP cost payload
  deliverables remain later slices of WP-114. This first API slice does not
  mark the backlog capability complete.
- Recalculating or inventing historical rates for legacy print-log rows.
- Changing archive/statistics responses or printer command paths.

## Done when

- The feature and all allocation values are disabled or zero by default.
- Enabled KRW capture stores one immutable snapshot per retained print-log row.
- Original, failed, cancelled, reprint, and incomplete costs remain separately queryable.
- Missing evidence produces null row totals and variance instead of invented zero values.
- The read route enforces `STATS_READ` whenever authentication is enabled.
- Focused tests and shared gates pass, and Bambuddy starts cleanly in the harness.
- Because this adds schema and a shared hook, the PR remains draft for operator approval.

# Architecture Boundaries

- Bambuddy remains the only printer command authority. This slice emits no
  printer, MQTT, FTPS, G-code, bed, or scheduler command.
- The ledger reads Bambuddy-owned run data only and does not access another
  service's database.
- Actual cost rows are keyed by print-log event, so failed attempts and
  reprints cannot overwrite one another.
- The snapshot records source values and rates; totals are deterministic
  derivations and never mutate inventory or ERP.
- Existing upstream behavior is patched only at the print-log completion hook
  and DB model registration points, recorded in `.fuzzyline/PATCH_LEDGER.yaml`.

# Milestones

1. Characterize current per-run cost persistence and separate reprint rows.
2. Add failing API/feature-flag/snapshot/failure-path tests using synthetic
   data and no external credentials.
3. Implement the additive snapshot model, capture service, schemas, and
   read-only route behind the default-off flag.
4. Run focused and shared gates, inspect the diff for secrets and scope creep,
   document migration/rollback, and publish a draft PR for schema approval.

# Progress

- [x] 2026-07-13 19:13 KST: Selected the highest unblocked backlog item from
  current `origin/farm-main`; confirmed WP-114 is unused locally and remotely.
- [x] 2026-07-13 19:13 KST: Observed existing print-log, archive statistics,
  cost settings, failed-run, and reprint behavior.
- [x] 2026-07-13 19:18 KST: Added the pre-product characterization test; one
  failed-attempt/reprint separation test passed on unmodified product code.
- [x] 2026-07-13 19:31 KST: Added API, policy, idempotency, incomplete-data,
  default-off, non-KRW, and SAVEPOINT failure-isolation tests.
- [x] 2026-07-13 19:31 KST: Implemented the default-off snapshot model,
  capture service, read API, model/route registration, and patch-ledger entry.
- [x] 2026-07-13 19:38 KST: Focused suite passed (35 tests), safety suite
  passed (7 tests), harness contract passed (3 tests), and verify-fast passed.
- [x] 2026-07-13 19:47 KST: Clean-start PostgreSQL runtime passed `/health`,
  default-off 404, enabled capture/API reconciliation, and zero app errors;
  Chromium desktop/mobile checks had no console or failed-response errors.
- [x] 2026-07-13 20:00 KST: Final focused regression passed (36 tests),
  including incomplete-estimate/actual-total summary consistency.
- [x] 2026-07-13 20:00 KST: `make test-unit`, `make test-contract`, corrected
  alternate-port `make test-integration`, `make verify-full`, and Ruff passed.
- [x] 2026-07-13 20:17 KST: Published draft PR #95 targeting `farm-main`;
  additive schema and the shared print-log hook await explicit operator approval.
- [x] 2026-07-13 22:55 KST: Pre-approval audit reproduced row/summary
  rounding drift and acceptance of non-finite policy rates, added regressions,
  and applied minimal fail-closed fixes. Focused regression passed 39 tests;
  PostgreSQL reconciled the boundary rows to `0.02 KRW` exactly.
- [x] 2026-07-13 22:58 KST: Final `make verify-fast`, `make test-unit`,
  `make test-contract`, alternate-port `make test-integration`, and
  `make verify-full` passed. The isolated app and main port 18000 were healthy.

# Decisions

- Extend the farm through a separate snapshot table rather than adding more
  accounting columns directly to upstream `PrintLogEntry`. Actual run values
  remain sourced from the existing log row; immutable estimate/rate context
  lives in the farm-owned table.
- Treat the first linked run as `original` and later linked rows as `reprint`.
  Unlinked legacy/direct rows are reported as `unlinked`, never guessed.
- Do not backfill legacy rows. Missing snapshots remain explicitly incomplete
  because assigning today's rates to historical runs would be false accounting.
- Require the existing Bambuddy currency setting to be `KRW` while capture is
  enabled. Currency conversion is a later operator-approved capability.

- Store a reviewed policy version plus estimated power, electricity tariff,
  effective material rate, and machine-hour rate on every snapshot. This
  satisfies the first slice of FULL_SPEC's policy-evidence requirement.
- Treat missing material, energy, or runtime as incomplete: component totals
  remain visible, but total cost and variance stay null rather than converting
  absent evidence to zero.
- Round each displayed money component before deriving a row total, and sum
  those same rounded row values in the summary. Raw binary-float aggregates
  must not disagree with the operator-visible rows.
- Accept only finite positive electricity, estimated-power, and machine-hour
  policy values. A non-finite rate skips the optional snapshot while the
  canonical print-log transaction remains intact.

# Harness Changes

- No external service harness is required; all data is synthetic and local.
- Integration fixtures create linked original, failed, cancelled, and reprint
  `PrintLogEntry` rows and snapshots.
- Failure tests cover disabled flag, non-KRW configuration, missing actual
  energy/material values, non-finite policy rates, orphan rows, unauthorized
  reads, and pagination.

# Implementation

Implemented files and symbols:

- `backend/app/core/config.py`: default-off flag, machine-hour rate,
  estimated-power rate, and policy version.
- `backend/app/models/farm_cost_ledger.py`: additive estimate/rate snapshot.
- `backend/app/services/farm_cost_ledger.py`: capture and deterministic totals.
- `backend/app/schemas/farm_cost_ledger.py`: stable read contract.
- `backend/app/api/routes/farm_cost_ledger.py`: read-only filtered endpoint.
- `backend/app/services/print_log.py::write_log_entry`: optional capture hook.
- Model/router registration and the repository's additive DB creation path.
- Focused unit/integration/architecture tests, harness contract, and runbook.
- `.fuzzyline/PATCH_LEDGER.yaml`: upstream-core patch record.

# Validation

Run in order:

```bash
docker run --rm --network none -e LOG_TO_FILE=false \
  -e DATA_DIR=/tmp/bambuddy-wp114-tests \
  -v "$PWD:/workspace:ro" -w /workspace \
  --entrypoint python wp114_harness-bambuddy:latest \
  -m pytest -q -p no:cacheprovider \
  backend/tests/unit/test_farm_cost_ledger_characterization.py \
  backend/tests/unit/test_farm_cost_ledger.py \
  backend/tests/unit/test_farm_cost_ledger_architecture.py \
  backend/tests/unit/test_farm_cost_ledger_failure_isolation.py \
  backend/tests/integration/test_farm_cost_ledger_api.py \
  backend/tests/unit/test_print_log.py \
  backend/tests/integration/test_cost_statistics.py \
  backend/tests/unit/test_route_auth_coverage.py
make verify-fast
make test-unit
make test-contract
env BAMBUDDY_BASE_URL=http://127.0.0.1:18001 MOCK_BASE_URL=http://127.0.0.1:19114 make test-integration
env BAMBUDDY_BASE_URL=http://127.0.0.1:18001 MOCK_BASE_URL=http://127.0.0.1:19114 make verify-full
```

Observable scenario: with the flag enabled, KRW configured, and three
synthetic linked events (successful original, failed reprint, successful
reprint), `GET /api/v1/farm-cost-ledger` returns three rows, distinct attempt
numbers/kinds, and totals whose failed and reprint buckets reconcile exactly
to the row totals. With the flag disabled, the route fails closed.

# Failure and Recovery

- Snapshot capture is transactionally tied to print-log creation; duplicate
  capture is prevented by a unique key and is idempotent.
- Missing material or energy observations produce nullable components and an
  explicit completeness state, not invented zero-cost evidence.
- Rollback disables the feature flag and reverts the application commit. The
  additive snapshot table may remain unused; dropping it is optional and is
  never performed automatically.
- No retry can resend or resume a printer or ERP action because this slice has
  no state-changing external boundary.

# Risks and Human Gates

- This PR adds a database table and patches a shared print-log hook. It stays
  draft and requires explicit operator approval before merge.
- Incorrect rate/currency labeling is an accounting risk; capture therefore
  fails closed outside KRW and records rate snapshots per run.
- Machine cost is an allocation estimate, not a cash transaction. The API
  names it separately from material and energy actuals.

# Outcomes

The first WP-114 vertical slice is implemented locally. It provides an
additive, default-off KRW estimate snapshot and a read-only per-run actual cost
API with separate original, failed, cancelled, and reprint buckets. Snapshot
failures are isolated from the canonical print log.

The final focused regression passed 39 tests. Shared unit, contract,
integration, verify-fast, and verify-full gates passed. A clean PostgreSQL
runtime created the additive table, preserved separate failed/reprint rows,
reconciled both the `10346.80 KRW` scenario and the `0.02 KRW` rounding
boundary, and emitted no application error logs. Desktop and mobile Chromium
checks were nonblank and error-free.

Draft PR #95 is published and review-ready but remains draft pending explicit
operator approval because it adds schema and a shared print-log hook. Later
WP-114 slices still own labor, overhead, adjustment/closing, and ERP cost
payload requirements.
