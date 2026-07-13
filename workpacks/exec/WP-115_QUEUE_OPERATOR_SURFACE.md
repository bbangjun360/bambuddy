# WP-115 Queue Operator Surface

## Purpose

Redesign the existing Print Queue page as a compact operator workspace that
matches the approved WP-112 shell and WP-113 printer fleet surface. Operators
must be able to scan running jobs, pending work, aggregate load, filters, and
queue actions without losing any existing queue behavior.

## Observable outcome

At desktop and mobile widths, the Queue page presents one coherent operational
header, a concise status rail, accessible view tabs, a responsive control bar,
and denser run rows. Existing start, stop, edit, cancel, requeue, bulk edit,
batch, sort, filter, drag-order, history, timeline, and pipeline workflows
remain available through the same API contracts and permission checks.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `docs/KNOWN_ISSUES.md`
- `workpacks/BACKLOG.md`
- `.agent/PLANS.md`
- `frontend/src/pages/QueuePage.tsx`
- `frontend/src/components/QueueStatsBar.tsx`
- `frontend/src/__tests__/pages/QueuePage.test.tsx`
- `frontend/src/pages/PrintersPage.tsx` for the approved WP-113 visual language

The archived full specification is not required for this UI-only slice.

## Current Behavior

- `QueuePage` owns queue queries, printer-status queries, mutations, filters,
  tabs, sorting, drag ordering, batching, and every modal in one large module.
- The page header, tab strip, summary card, filter row, layout controls, and
  bulk toolbar render as separate vertical bands before the first queue item.
- `SortableQueueItem` uses large rounded cards and a printing-only gradient,
  while WP-113 uses a quieter compact header and toolbar treatment.
- Existing tests cover 26 queue behaviors including tabs, filters, mutation
  controls, history, staged work, G-code badges, and filament-short override.

Observed on 2026-07-13 from `origin/farm-main` commit `e82b0488`. The unchanged
baseline passed `make verify-fast` and all 26 focused QueuePage tests.

## In scope

- Queue-only header, status summary, tabs, filters, layout controls, and bulk
  action composition.
- Denser queue and batch row presentation with stable dimensions and existing
  archive/library thumbnails.
- Accessible tab and control semantics, including mobile overflow behavior.
- Focused structure tests, full frontend validation, generated static assets,
  backlog status, and this living ExecPlan.

## Out of scope

- Backend routes, API payloads, printer commands, scheduler behavior, queue
  ordering semantics, permissions, mutation confirmation, or local-storage
  keys.
- Pipeline, history-card, timeline, printer fleet, library, inventory, or
  settings workflow redesign beyond their existing embedding in QueuePage.
- New dependencies, migrations, feature flags, production configuration, or
  changes to authentication.

## Done when

- Header, status rail, tabs, filters, view controls, and bulk actions form one
  compact and predictable operator surface.
- Active and pending queue rows are denser, have no decorative gradient, and
  retain all current metadata, thumbnails, badges, and commands.
- Desktop 1440x1000 and mobile 390x844 render without overlap, horizontal page
  overflow, blank content, failed responses, or console errors.
- Existing QueuePage behavior tests, new layout/semantics tests, full Vitest
  and i18n checks, TypeScript build, shared gates, and clean-start smoke pass.
- The PR states that Bambuddy still starts and that no backend or printer
  contract changed.

## Architecture Boundaries

- Bambuddy remains the sole owner of queue and printer state-changing commands.
- UI handlers continue calling the existing `api` client methods unchanged.
- Existing permission checks and confirmation modals remain the command gates.
- This slice adds no direct MQTT, FTPS, G-code, ERP, database, or network
  integration.
- Generated `static/` output must come from the validated frontend source.

## Milestones

1. Record the green baseline and characterize the operator workflow.
2. Add failing structure/semantics tests for the redesigned surface.
3. Implement the Queue header, summary rail, responsive toolbar, and dense rows.
4. Run focused, full frontend, build, shared, and browser validation.
5. Review the diff, publish a PR, and leave visual approval as the human gate.

## Progress

- [x] 2026-07-13 20:24 KST: Selected the next independent unblocked backlog
  slice while WP-114 and WP-110 remain approval-gated; confirmed WP-115 is free.
- [x] 2026-07-13 20:28 KST: Baseline `make verify-fast` passed and focused
  QueuePage tests passed (26 tests).
- [x] 2026-07-13 20:34 KST: Added a workflow characterization test and a
  red compact-structure/accessibility test; the focused suite grew from 26 to
  28 tests and failed only on the missing operator landmark before production
  code changed.
- [x] 2026-07-13 20:49 KST: Implemented the compact status rail, semantic tabs
  with arrow/Home/End keyboard navigation, unified responsive controls, dense
  queue/batch rows, and mobile bottom safe area. Focused tests passed 28/28.
- [x] 2026-07-13 21:10 KST: Full frontend tests passed 2,316/2,316 with all 11
  locales in parity; ESLint, TypeScript/Vite build, `make verify-fast`, and
  `make verify-full` passed. Isolated Chrome checks passed at 1440x1000 and
  390x844 with zero page overflow, overlaps, clipped controls, image failures,
  failed responses, console errors, or runtime exceptions.
- [x] 2026-07-13 21:23 KST: Published draft PR #96 for operator visual review
  at https://github.com/bbangjun360/bambuddy/pull/96; the isolated preview
  remains available at http://127.0.0.1:18115/queue.
- [x] 2026-07-13 23:35 KST: Pre-approval browser audit reproduced the fixed
  bug-report button covering a mobile Queue cancel control and the icon-only
  resume-after-failure button losing its accessible name. Added regressions,
  reserved a mobile row gutter, and restored the translated button label.
- [x] 2026-07-13 23:35 KST: Focused Queue tests passed 30/30; the full frontend
  passed 2,318/2,318 with 11 locales in parity. ESLint, build, `verify-fast`,
  `verify-full`, desktop/mobile browser checks, and card/control intersection
  checks passed; main port 18000 remained healthy.
- [x] 2026-07-14 01:03 KST: A second pre-approval Chrome accessibility audit
  found unnamed pending-item selection and drag controls, 13px archive-link
  targets, and unnamed sort selects. Added a red regression for item-specific
  names, stable targets, and the active tabpanel relationship before changing
  production code.
- [x] 2026-07-14 01:16 KST: Added translated item-specific accessible names,
  explicit Queue/History sort names, and stable 32px CSS targets for compact
  row and sort controls. Focused tests passed 31/31; the full frontend passed
  2,319/2,319 with all locales in parity. ESLint, build, `verify-fast`,
  isolated `verify-full`, visual checks, and the Chrome accessibility tree
  audit passed.
- [x] 2026-07-14 05:17 KST: Merged `origin/farm-main` commit `24196873`
  into the draft after UI-01 landed. Queue source merged without conflict;
  only the generated JavaScript asset and `static/index.html` required a
  lockfile-based rebuild. Merge commit: `21901a7d`.
- [x] 2026-07-14 05:31 KST: Revalidated the combined branch. Queue and
  Settings focused tests passed 80/80; the full frontend passed 2,321/2,321
  with all locales in parity. ESLint, build, `verify-fast`, isolated
  `verify-full`, desktop/mobile CDP checks, accessibility-tree checks, and
  mobile fixed-control intersection checks all passed.

## Decisions

- Preserve the proven queue domain behavior and change composition and visual
  hierarchy only. This keeps the blast radius inside the operator UI.
- Reuse the compact WP-113 header and toolbar language rather than introducing
  a second design system.
- Keep actual print thumbnails as the visual asset; do not add decorative or
  stock imagery to an operational queue.
- Keep tabs for Active, History, Timeline, and Pipelines because they already
  partition distinct workflows and have stable deep links.
- Reserve the fixed bug-report button's horizontal footprint on mobile Queue
  and batch rows, not only bottom padding. This keeps cards and command targets
  outside the overlay at every scroll position while preserving desktop width.
- Give the mobile icon-only resume-after-failure control an explicit translated
  accessible name and tooltip because its visible text is hidden below `sm`.
- Derive compact row control names from existing translated action labels plus
  the visible job name. This avoids new locale keys while distinguishing
  repeated selection, drag, archive, and file-manager controls.
- Keep compact icon controls at `h-8 w-8` in source. The configured 90% UI
  scale renders these as 28.8 CSS px, above the audit floor and without
  increasing row height or crowding mobile commands.

## Harness Changes

- Added frontend characterization and structure tests in the existing Vitest
  discovery path. No backend or external-service harness fixture changed.
- Reused MSW queue/printer handlers with synthetic identifiers and data only.
- Browser verification used the isolated `farm_wp115` Compose project on
  ports 18115/19115. Its inactive synthetic printer used no real serial, IP,
  access code, printer connection, production credential, or customer data.
- A CDP coordinate audit checks the global fixed bug-report button against
  visible Queue row and command rectangles at 390x844; both intersection sets
  are empty after the fix.
- A CDP accessibility audit checks scoped DOM names, Chrome accessibility-tree
  names, duplicate IDs, active tabpanel ownership, and control dimensions at
  1440x1000 and 390x844.
- Rebuilding the isolated preview exposed a stale PostgreSQL volume whose role
  password predated the current `.env.harness.example`. The `farm_wp115` role
  was synchronized to the synthetic `local-harness-only` value and only its app
  container was restarted; no volume, schema, or application data was removed.

## Implementation

Expected files:

- `frontend/src/pages/QueuePage.tsx`
- `frontend/src/components/QueueStatsBar.tsx`
- `frontend/src/__tests__/pages/QueuePage.test.tsx`
- generated `static/index.html` and hashed `static/assets/*`
- `workpacks/BACKLOG.md`
- `workpacks/exec/WP-115_QUEUE_OPERATOR_SURFACE.md`

No backend, API client, route, model, schema, or deployment file is in scope.

## Validation

Run in order:

```bash
make verify-fast
npm --prefix frontend run test -- --run src/__tests__/pages/QueuePage.test.tsx
npm --prefix frontend run test:run
npm --prefix frontend run lint
npm --prefix frontend run build
make verify-fast FRONTEND_TESTED=1
make verify-full FRONTEND_TESTED=1
```

Observed results on 2026-07-14:

- Focused QueuePage: 31/31 tests passed, including semantic tabs, dynamic
  tabpanel ownership, item-specific control names, stable compact targets,
  arrow-key focus movement, mobile overlay clearance, filters, history, and
  existing action controls.
- Full frontend: 175 files and 2,319 tests passed; all 11 locales matched; ESLint
  and the TypeScript/Vite production build passed.
- Shared gates: `make verify-fast FRONTEND_TESTED=1` and isolated
  `make verify-full FRONTEND_TESTED=1` passed. The full smoke explicitly used
  `BAMBUDDY_BASE_URL=http://127.0.0.1:18115` and
  `MOCK_BASE_URL=http://127.0.0.1:19115`; all four targets returned 200.
- Browser: 1440x1000 and 390x844 showed two compact active rows, loaded real
  repository thumbnails, no page overflow or component overlap, no clipped
  controls, and no failed requests or browser errors. Queue/History keyboard
  switching retained focus. At mobile top and scroll bottom, visible Queue
  rows, commands, and the fixed bug-report control had zero intersection.
- Accessibility: every scoped control and interactive Chrome accessibility
  node had a name, no duplicate IDs were present, no scoped target rendered
  below 28 CSS px, and History switched the shared panel to
  `aria-labelledby="queue-tab-history"` with `Sort: History`.

Refresh validation on 2026-07-14 used the isolated
`farm_wp115_merge_20260714` stack on ports 18145/19145. Bambuddy root,
`/health`, API docs, and mock health returned 200. Desktop 1440x1000 and mobile
390x844 retained two compact active rows with zero page overflow, row or
landmark overlap, clipped controls, image failures, failed responses, console
errors, or runtime exceptions. Keyboard tab focus followed Queue/History
selection, and the fixed bug-report button intersected zero rows or commands
at both the mobile top and bottom scroll positions.

Observable scenario: with one printing, one pending, and one completed synthetic
job, the active Queue view shows the running and pending work plus summary load;
History exposes the completed row; switching views, filtering, sorting, and
opening existing actions behaves exactly as before.

## Failure and Recovery

- Rollback is a source and generated-asset revert; there is no data migration.
- Query retries, mutations, confirmation gates, and local-storage keys remain
  unchanged, so restart and recovery behavior stays upstream-compatible.
- If responsive or browser validation fails, keep the PR draft and restore the
  last green layout before any operator review.

## Risks and Human Gates

- Visual density can hide controls or truncate labels at narrow widths; test
  both 390px and 1440px viewports and inspect screenshots.
- Recomposition can accidentally detach an existing handler or permission
  gate; the existing behavior suite and new control tests must stay green.
- This UI-only slice has no merge-policy exclusion, but it remains draft until
  the operator visually approves the desktop and mobile result.

## Outcomes

WP-115 now delivers a compact Queue operator surface consistent with WP-112 and
WP-113 while preserving the existing API calls, permissions, mutations, drag
ordering, filters, history, timeline, pipelines, and local-storage keys.

There is no backend or service-contract change, migration, destructive action,
new dependency, feature-flag default change, auth change, printer command
change, or safety-gate change. No new logs or metrics are required because all
failure paths still use the existing query, mutation, API, and browser
diagnostics. Rollback is the source plus generated-asset revert. Bambuddy was
built and started successfully in the isolated harness. The pre-approval audit
also removed a mobile command-overlay collision and restored the accessible
name of an icon-only failure-recovery action. The second audit also named each
compact selection, reorder, archive, and sort control and restored stable target
dimensions. The remaining gate is operator visual approval of the draft PR;
no merge is attempted before it. The 2026-07-14 `farm-main` refresh preserved
that behavior and restored a clean merge base without changing the approval
gate.
