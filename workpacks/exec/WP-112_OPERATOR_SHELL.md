# WP-112: Operator Shell

## Purpose

Start the operator-approved UI redesign with one observable, independently
testable slice: the shared application shell. Make navigation and pending farm
work scannable without changing any page workflow or backend contract.

## Observable outcome

An operator using Bambuddy on desktop or mobile sees a compact route-aware
header, workflow section labels in the navigation, and existing queue, pending
upload, and plate-clear signals in the shared shell. Existing links, permission
gates, badges, keyboard shortcuts, external links, and sidebar preferences keep
working.

## Read these files

- `docs/modules/BAMBUDDY_BASELINE.md`
- `frontend/src/components/Layout.tsx`
- `frontend/src/__tests__/components/Layout.test.tsx`
- `frontend/src/i18n/locales/en.ts`

Do not read `docs/archive/FULL_SPEC_v1.1.md` for this Work Package.

## Scope control

- Goal: deliver the first vertical slice of the operator-approved UI redesign.
- Files/modules: shared frontend shell, shell tests, navigation locale keys,
  generated static assets, this Work Package, and `workpacks/BACKLOG.md`.
- Constraints: no API, database, permission, printer-command, scheduler,
  feature-flag, or page workflow changes.
- Done-when behavior: desktop and mobile shell navigation is route-aware,
  grouped, responsive, and exposes the existing pending-work signals.
- Tests: focused Layout tests, full frontend and locale parity, production
  build, `make verify-fast`, and browser screenshots with console review.

Revise this Work Package before proceeding if implementation needs a service
contract change, a production dependency, or edits to an individual page's
business workflow.

## In scope

- Add semantic workflow sections to the existing ordered navigation.
- Add a stable, responsive top bar with current-route context.
- Surface existing queue, pending-upload, and plate-clear states without new
  requests or mutations.
- Tighten shell spacing, focus states, active states, and mobile drawer
  semantics while retaining current themes.
- Add characterization and behavior tests for the shared shell.

## Out of scope

- Redesigning printer cards, queue, inventory, archive, project, statistics,
  settings, authentication, setup, or modal content.
- Changing sidebar preference storage, permission evaluation, API contracts,
  backend routes, or WebSocket behavior.
- Adding a UI framework, design-system dependency, analytics, or telemetry.
- Enabling or changing any farm automation or physical actuation flag.
- Completing every UI redesign phase in this PR. Follow-on pages remain
  separate operator-observable Work Packages.

## Architecture boundaries

- Bambuddy remains the sole printer state-changing command authority.
- The shell consumes only data already fetched by `Layout`.
- Navigation visibility remains governed by existing permissions and advanced
  authentication settings.
- Stored sidebar order and hidden-item preferences remain authoritative.
- No new feature flag is needed because this is a presentation-only
  replacement; no behavior or backend capability is introduced.

## Milestones

1. Capture the current desktop and mobile shell and add characterization tests.
2. Implement route context, navigation sections, and status affordances.
3. Verify focused and complete frontend behavior and rebuild static assets.
4. Verify the production image visually at desktop and mobile sizes.

## Progress

- [x] 2026-07-13: Operator explicitly approved starting the deferred UI
  redesign after upstream v0.2.4.9 integration.
- [x] 2026-07-13: Allocated WP-112 after checking `origin/farm-main` and open
  `feature/wp-*` branches.
- [x] 2026-07-13: `make verify-fast` baseline passed with 190 harness and two
  characterization tests.
- [x] 2026-07-13: Captured 1440x1000 and 390x844 pre-change screenshots.
- [x] 2026-07-13: Added Layout characterization and behavior tests; the focused
  file passes 28 tests.
- [x] 2026-07-13: Implemented and visually verified the responsive operator
  shell in a healthy production-image container.
- [x] 2026-07-13: Full frontend validation passes 2,309 tests across 175 files,
  with all 11 locales in parity with English.
- [x] 2026-07-13: Published Draft PR #93 with the validation and merge-policy
  exclusion summary.
- [x] 2026-07-13: Operator visually approved the shared shell and authorized
  PR #93 to leave Draft and merge.

## Done when

- Expanded and mobile navigation display workflow section labels while the
  collapsed rail remains compact.
- The shared header exposes the active route using the existing translated
  navigation label.
- Existing queue and archive pending counts and the plate-clear signal remain
  visible and link to the correct destination.
- Sidebar order, hidden items, external links, permission gates, keyboard
  shortcuts, theme selection, update status, and authentication controls retain
  their existing behavior.
- At 1440x1000 and 390x844 there is no text clipping, incoherent overlap,
  horizontal page overflow, or blank main content.
- Bambuddy's production image starts and serves the updated static bundle.

## Validation

Run:

1. `python3 harness/scripts/check_workpack.py workpacks/exec/WP-112_OPERATOR_SHELL.md`
2. `npm --prefix frontend ci`
3. `npm --prefix frontend run test:run -- src/__tests__/components/Layout.test.tsx`
4. `npm --prefix frontend run test:run`
5. `npm --prefix frontend run build`
6. `make verify-fast FRONTEND_TESTED=1`
7. Headless Chrome desktop and mobile screenshot and console checks.

## Migration, diagnostics, and rollback

- Migration: none.
- Changed contracts: none.
- Feature-flag default: none; presentation-only shell replacement.
- Failure diagnostics: frontend test output, browser console, API request
  failures already reported through React Query, and screenshot evidence.
- Rollback: revert the WP-112 commit and rebuild static assets. No data or API
  rollback is required.

## Outcomes

The shared shell now groups the existing navigation into Fleet, Production,
Insights, Administration, and Links while preserving stored ordering and
visibility. A sticky route-aware top bar exposes existing queue, pending-upload,
and plate-clear state as destination links; it introduces no mutation or new
request.

Validation evidence on 2026-07-13:

- Focused Layout suite: 28 passed.
- Full frontend suite: 175 files and 2,309 tests passed.
- Locale parity: English plus all 10 translated locale files have 5,584 leaves.
- ESLint, TypeScript, Vite production build, `git diff --check`, and
  `make verify-fast FRONTEND_TESTED=1` passed.
- The production integration image started healthy and served the generated
  v0.2.4.9 static bundle at `http://127.0.0.1:8001`.
- Desktop 1440x1000 and mobile 390x844 captures showed no clipping or overlap.
  The clicked mobile drawer had a visible backdrop, remained within the
  viewport (`body.scrollWidth === innerWidth === 390`), exposed the workflow
  labels, and produced no page-console errors.

Migration and rollback remain as documented above. Remaining redesign work is
intentionally split into later observable slices: printer fleet/card workflows,
production work surfaces (queue, archives, inventory, projects, and files),
then insights and administration surfaces. The operator accepted the shared
shell visually on 2026-07-13, clearing PR #93 for routine merge.
