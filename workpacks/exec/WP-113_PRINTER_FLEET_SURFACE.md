# WP-113: Printer Fleet Surface

## Purpose

Continue the operator-approved UI redesign with one observable slice: make the
printer fleet page and printer-card headers faster to scan on desktop and
mobile. Preserve every existing printer action and safety gate while improving
the hierarchy of state, identity, location, filtering, and view controls.

## Observable outcome

An operator sees fleet state counts, search and view tools, and printer identity,
location, connection, and health in a stable visual hierarchy at desktop and
mobile widths. Existing printer controls remain present, permission-gated, and
behaviorally unchanged.

## Current Behavior

`frontend/src/pages/PrintersPage.tsx` owns the fleet page, `StatusSummaryBar`,
toolbar controls, and `PrinterCard`. The page is 8,872 lines because printer
display, status queries, controls, and modals are colocated. The current summary
is an inline list of status dots, the toolbar compresses into three menus, and
card identity is followed by a long equal-weight badge row.

The existing behavior was observed by reading these symbols and by running the
focused `PrintersPage.test.tsx` suite. Existing local preferences control search,
status/location filters, sort order, card size, camera-wall view, grouping,
hidden disconnected printers, and collapsed groups.

## Read these files

- `docs/modules/BAMBUDDY_BASELINE.md`
- `frontend/src/pages/PrintersPage.tsx`
- `frontend/src/__tests__/pages/PrintersPage.test.tsx`
- `frontend/src/components/Card.tsx`

Do not read `docs/archive/FULL_SPEC_v1.1.md` for this Work Package.

## Scope control

- Goal: redesign only the printer fleet presentation hierarchy.
- Files/modules: PrintersPage display markup, existing page tests, generated
  assets, backlog, and this ExecPlan.
- Constraints: no service contract, printer command, permission, dependency,
  migration, or safety-gate change.
- Done-when behavior: fleet and card state are scannable and responsive while
  all existing workflows remain reachable.

## In scope

- Redesign the existing status summary as a stable, semantic fleet overview.
- Improve the responsive search/filter/sort/view/action toolbar hierarchy.
- Improve printer-card outer state, identity, location, and connection/health
  scan hierarchy using data already fetched by `PrinterCard`.
- Improve the no-printers and no-results presentation without changing actions.
- Add characterization and presentation tests in existing discovery paths.
- Rebuild checked-in static assets.

## Out of scope

- API, backend, WebSocket, database, authentication, or permission changes.
- Any printer command, confirmation, plate-clear, bulk-action, or safety logic.
- WP-110 SwapMod controls or physical actuation presentation.
- Reworking AMS, temperature, fan, queue, camera, maintenance, modal, upload,
  drag-and-drop, or print-control internals inside a card.
- A new component library, production dependency, or feature flag.
- Queue, archive, inventory, project, file, statistics, or settings redesigns.

## Architecture Boundaries

- Bambuddy remains the sole printer state-changing command authority.
- Existing permission checks remain attached to the same controls.
- Existing API calls, React Query keys, WebSocket behavior, and mutations remain
  unchanged.
- Existing localStorage keys and meanings remain authoritative.
- Printer state colors are derived only from existing connection, gcode state,
  HMS, maintenance, queue, and plate-clear values.
- No general G-code or new actuation surface is introduced.

## Milestones

1. Establish a green repository and focused frontend baseline.
2. Add characterization coverage for fleet semantics and card identity/state.
3. Implement the fleet summary, responsive toolbar, and card header hierarchy.
4. Run focused and full frontend validation and rebuild static assets.
5. Verify fixture-backed idle, paused, problem, and offline cards in a production
   image at desktop and mobile sizes; retain automated printing-state coverage.
6. Publish a Draft PR for operator visual review.

## Progress

- [x] 2026-07-13: Operator visually approved WP-112; PR #93 merged to
  `farm-main` as `ad7ccc79`.
- [x] 2026-07-13: Checked open PRs and allocated WP-113 after WP-112.
- [x] 2026-07-13: Created `feature/wp-113-printer-fleet` from current
  `origin/farm-main`.
- [x] 2026-07-13: Pre-edit `make verify-fast` passed with 190 harness and two
  characterization tests.
- [x] 2026-07-13: Pre-edit focused PrintersPage suite passed 60 tests.
- [x] 2026-07-13: Added two characterization tests before presentation edits;
  the focused suite passed 62 tests.
- [x] 2026-07-13: Implemented semantic state counts, responsive tools, state-led
  card headers, compact metadata, and unframed empty states without changing a
  query, mutation, permission, printer command, or local preference.
- [x] 2026-07-13: Added three presentation tests; the focused suite passed 65
  tests, including idle, printing, and offline card semantics.
- [x] 2026-07-13: Full frontend validation passed 175 files and 2,314 tests;
  ESLint and all 11 locale parity checks passed.
- [x] 2026-07-13: Production build generated `index-BT7fGDK7.js` and
  `index-C0vbNqQe.css`; the existing large-chunk warning remains non-blocking.
- [x] 2026-07-13: `make verify-fast FRONTEND_TESTED=1` passed 190 harness tests
  twice and two characterization tests; the WP checker and `git diff --check`
  also passed.
- [x] 2026-07-13: The rebuilt integration container reported healthy and
  `/health` returned `{"status":"healthy"}`. Bambuddy still starts.
- [x] 2026-07-13: Chrome fixture checks at 1440x1000 and 390x844 rendered one
  idle, paused, problem, and offline card, opened the compact Filters menu,
  showed no horizontal overflow, and reported zero console or HTTP failures.
- [x] 2026-07-13: Published Draft PR #94 for operator visual review; merge remains
  blocked until approval is recorded in the operator channel.
- [x] 2026-07-13: Operator visually approved PR #94 in the session channel and
  authorized merge to `farm-main` followed by the port 18000 harness deployment.

## Decisions

- Keep behavior inside `PrintersPage.tsx` for this slice. Extracting command or
  modal logic from the monolith would enlarge the regression surface without
  improving the operator-visible outcome.
- Reuse existing icons, colors, translation labels, controls, and data. Add a
  translation key only when no accurate existing label exists.
- Do not add a feature flag. This is a presentation-only replacement that adds
  no capability, request, mutation, or permission.
- Keep all four card density choices and camera-wall mode because operators
  already persist and use those preferences.
- Operator visual approval was recorded on 2026-07-13; routine merge may proceed
  after the approval-record commit passes refreshed CI.

## Harness Changes

- Add tests to `frontend/src/__tests__/pages/PrintersPage.test.tsx`; do not add a
  per-WP file or Makefile target.
- Characterize the existing printer name/model/location and state destination
  semantics before changing markup.
- Add presentation tests for semantic fleet summary, status metadata, card
  identity, zero/empty state, and preserved toolbar controls.
- No backend harness, external service fixture, or production credential is
  required.

## Implementation

Expected changed files and symbols:

- `frontend/src/pages/PrintersPage.tsx`
  - `StatusSummaryBar`
  - `ToolbarDropdown`, `ToolbarMenu`, and page toolbar markup
  - `PrinterCard` outer wrapper and identity/status header
  - fleet empty and filtered-empty states
- `frontend/src/__tests__/pages/PrintersPage.test.tsx`
- `frontend/src/i18n/locales/*.ts` only if a missing semantic label is needed
- generated `static/index.html` and hashed assets
- `workpacks/BACKLOG.md`
- this ExecPlan


## Done when

- Fleet status counts use semantic markup and stable dimensions.
- Search, filters, sort, camera/cards mode, density, selection, and Add Printer
  remain reachable at desktop and mobile widths.
- Printer cards expose name, model, location, connection, and health before
  secondary diagnostics without moving or changing a printer command.
- Empty and filtered-empty states remain actionable and permission-aware.
- Existing local preferences, grouped views, card sizes, and camera wall retain
  their behavior.
- Browser checks show no clipping, incoherent overlap, horizontal page overflow,
  blank fleet/card content, or page-console errors.
- The production image starts and serves the rebuilt static bundle.

## Validation

Run:

1. `python3 harness/scripts/check_workpack.py workpacks/exec/WP-113_PRINTER_FLEET_SURFACE.md`
2. `npx vitest run src/__tests__/pages/PrintersPage.test.tsx`
3. `npm run test:run`
4. `npm run lint`
5. `npm run build`
6. `make verify-fast FRONTEND_TESTED=1`
7. Build and start the production integration image.
8. Use Chrome with fixture responses at 1440x1000 and 390x844; inspect the
   rendered pixels, page console, horizontal overflow, toolbar interaction,
   and printer-card state hierarchy.

Expected observable scenario:

- A fixture fleet contains connected idle, active paused, HMS problem, and
  offline printers across locations. Automated tests separately exercise the
  active printing state.
- The summary reports only present states with stable counts.
- Search, filters, sort, page view, density, selection, and Add Printer remain
  reachable at desktop and mobile widths.
- Each card exposes name, model, location, connection/health state, and active
  job hierarchy without clipping or moving an existing command.

## Failure and Recovery

- Migration: none.
- Changed contracts: none.
- Feature-flag default: none changed.
- Diagnostics: focused/full test output, React Query/API errors, browser page
  console, screenshot evidence, and container health.
- Rollback: revert the WP-113 commit and rebuild static assets. No data,
  credential, printer, or API rollback is required.
- A fixture or browser failure must not be bypassed with production printer
  credentials or a direct database edit.

## Risks and Human Gates

- The 8,872-line page has a broad rendering surface. Limit edits to display
  hierarchy and keep focused/full frontend tests mandatory.
- PR #90 modifies WP-110 plate-change controls on a printer card. WP-113 must
  not copy, alter, or merge that draft safety/actuation code.
- Simulation and fixture screenshots are visual evidence only, not proof of
  hardware safety.
- Operator visual approval is required before the Draft PR merges.

## Outcomes

WP-113 now gives the Printers page an operator-scannable hierarchy. Present
fleet states are exposed as semantic counts, responsive tools retain the same
search/filter/sort/view/density/selection/add workflows, and every card leads
with state, identity, model, location, and existing connection/health signals.
Empty and filtered-empty states remain actionable without adding nested cards.

The behavioral surface did not change: API contracts, React Query keys,
WebSocket handling, permission gates, localStorage meanings, printer commands,
WP-110 actuation controls, dependencies, migrations, feature defaults, logs,
and metrics are unchanged. Failure-path coverage includes an offline fixture;
rollback is a commit revert plus static rebuild and requires no data action.

Validation passed the 65-test focused page suite, the full 175-file/2,314-test
frontend suite, locale parity, ESLint, production build, workpack validation,
diff validation, repository fast gate, production-container health, and
fixture-backed desktop/mobile browser inspection. The browser run had four
distinct card states, working compact Filters, no horizontal overflow, and zero
console or failed HTTP responses.

Operator visual approval for PR #94 is recorded. After merge,
the next UI redesign Work Package should address the print queue as the next
operator workflow named in `workpacks/BACKLOG.md`; library/inventory and settings
remain later independent slices.
