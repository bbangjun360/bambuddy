# WP-110 SwapMod Control UI

## Observable outcome

An operator runs the SwapMod plate-change flow from the Bambuddy UI instead of raw
`curl`: a plate-change control on each connected printer card, a confirmation gate
(10-item checklist + server read-only phrase), and a SwapMod settings tab with a
failure log and a per-action sequence/speed editor. Sessions S1..S9 proved the
backend chain by hand; this WP surfaces it safely. Design iterated in Paper first
via the WP-901 pipeline.

The current Draft PR's observable outcome is the supervised printer-card control.
It remains absent unless both canary flags are armed and the card represents a
connected, active, explicitly configured A1 Mini that the current operator may
control. Bambuddy remains the final authority and repeats every safety check
before any command can run.

## Read these files

- `backend/app/api/routes/swapmod_state_machine.py` — route patterns, permissions.
- `backend/app/services/swapmod_state_machine.py` — `get_swapmod_cycle`,
  `public_swapmod_cycle`, cycle model usage.
- `backend/app/models/swapmod_state_machine.py` — cycle columns, `transition_log`,
  `manual_review_required`, `blocked_reason`.
- `backend/tests/integration/test_swapmod_state_machine_api.py` — test harness.
- `frontend/src/api/client.ts`, `frontend/src/pages/SettingsPage.tsx`,
  `frontend/src/pages/PrintersPage.tsx` (frontend slices).
- `docs/runbooks/WP076_SWAPMOD_A1_MINI_DIRECT_CANARY.md` — the sequence
  allowlist + SHA-256 safety model the editor must preserve.

## In scope

1. **Backend read-only list** — `GET /swapmod-state-machine/cycles` (newest first;
   optional `printer_id`, `manual_review_only`, `limit` bounded 1..200).
   `PRINTERS_READ`, returns safely regardless of the feature flag, sends no printer
   command. (THIS SLICE.)
2. `swapmodApi` in `client.ts` + a SwapMod settings tab: failure log (read-only).
3. Sequence/speed editor: edit per-action feedrate/speed of the release/load
   sequences. Saving writes a NEW reviewed version with a fresh SHA-256.
4. Plate-change control on each connected printer card + confirmation gate.

## Out of scope

- Autonomous actuation (removing the per-step human phrase) — separate WP.
- Any weakening of the WP-076 sequence allowlist + SHA-256 pin model.
- New backend actuation endpoints — the UI uses the existing validated ones.
- Live raw G-code push from the sequence editor.

## Done when

- `GET /cycles` exists with ordering/filters/limit, is read-only and flag-safe.
- The failure log renders from that endpoint.
- The printer-card control stays hidden unless all UI eligibility checks pass,
  drives only the existing gated actuation flow, requires every server checklist
  item, displays the server phrase read-only, and refuses stale or competing
  unresolved cycles.
- Focused backend and frontend tests, the repository verification gates, startup
  smoke, and desktop/mobile browser checks pass with both canary flags default-off.
- The Draft PR is current with `farm-main`; physical E2E and merge still require an
  operator-present approval session.

## Architecture boundaries

- Bambuddy stays the sole printer-command authority; the UI only calls existing
  gated endpoints. The list endpoint is read-only.
- Actuation from the UI keeps every gate: canary flags default-off, the checklist is
  ticked by the operator, the confirmation phrase is shown read-only from the server
  — the UI never fabricates either.
- The sequence editor produces reviewed, re-hashed versions; it does not send G-code.

## Milestones

1. Backend read-only cycle listing + test. DONE 2026-07-09
2. `swapmodApi` client + SwapMod settings tab with failure log. DONE 2026-07-09
3. Sequence/speed editor (versioned, re-hashed, reviewed). TODO — operator-approved
4. Printer-card plate-change control + confirmation gate. DRAFT 2026-07-09 — operator-approved (PR pending review + operator-present E2E)

## Progress

- [x] 2026-07-09 `list_swapmod_cycles` service helper +
      `GET /swapmod-state-machine/cycles` (printer_id / manual_review_only / limit),
      serialized via existing `public_swapmod_cycle`.
- [x] 2026-07-09 Integration tests: newest-first ordering, printer filter,
      failure filter, limit, safe read when disabled; full
      `test_swapmod_state_machine_api` class green (22 tests) in the backend image.
- [x] 2026-07-09 Frontend slice 2: `swapmodApi.listCycles` in `client.ts` and a
      read-only SwapMod settings tab rendering the failure log (cycles with
      `manual_review_only`, 15s poll while active). Tab label + content use i18n
      fallback args, so no locale files change and parity stays green. `npm run
      build` + eslint + i18n/paper vitest all pass.
- [x] 2026-07-09 Slice 4 DRAFT: read-only `GET /swapmod-a1-mini-direct-canary/
      confirmation-preview` (returns the exact operator phrase + checklist fields
      for a cycle+step; sends no command) + `confirmation_preview` service method +
      2 integration tests (canary API class 6 tests green). Frontend
      `SwapModPlateChangeControl` component (renders on a printer card only while
      the canary is armed) drives create-cycle -> confirm gate (operator ticks the
      10-item checklist, server phrase shown read-only) -> RELEASE -> verify ->
      LOAD -> verify via the existing gated endpoints; verify-fail -> MANUAL_REVIEW.
      `swapmodApi` actuation methods added. `npm run build` + eslint + i18n parity
      green. DRAFT PR — needs operator review + operator-present E2E before merge.
- [x] 2026-07-13 22:09 KST Refreshed Draft PR #90 onto `origin/farm-main`
      `e82b0488`, resolving the WP-113 printer-card composition and generated
      static-asset conflicts. Added a six-test UI characterization suite. A red
      eligibility test exposed that armed controls also rendered for disconnected,
      read-only, and non-A1 Mini cards; the component now requires canary flags,
      connection, active/control permission, and A1 Mini model eligibility. Only
      eligible cards poll canary status, and repeated cards receive unique control
      IDs. No real printer or actuator command was sent.
- [x] 2026-07-14 00:11 KST Pre-approval safety audit found that all connected
      A1 Mini cards shared the armed control, `COMMAND_FAILED` responses advanced
      to verification, and refresh/cancel could permit another cycle while an
      earlier physical state remained unresolved. Added a default-null named
      target printer ID enforced by route, service, and UI; server-state checks
      after transport and verification; disarm-state clearing; and recent-cycle
      guards in both UI and service. The UI now creates a cycle only after all ten
      checklist items are checked. Missing responses and unexpected states stop in
      manual review with no automatic retry. No real printer command was sent.
- [x] 2026-07-14 00:40 KST Final state-transition review added fail-closed
      handling for an uncertain verification response and a dedicated stale-cycle
      service regression. The final generated bundle, focused tests, full frontend
      suite, shared gates, isolated startup smoke, and desktop/mobile browser
      checks are green. Main port 18000 remained healthy; no real command ran.
- [x] 2026-07-14 02:35 KST Pre-approval transaction audit reproduced four backend safety
      failures before changing production code: a sequence file could change
      between hash and send, the cycle's active state was uncommitted at send,
      a transport exception escaped without durable manual review, and two
      concurrent requests with different canary keys sent twice. The service now
      serializes each named printer with a SQLite writer lock or PostgreSQL
      transaction advisory lock, refreshes the cycle after obtaining that lock,
      commits `START_STEP` before transport, and hashes/sends one immutable byte
      snapshot. Transport exceptions persist a no-retry manual-review state. No
      real printer or actuator command was sent.

## Decisions

- List endpoint returns 200 regardless of the state-machine flag, matching the other
  read endpoints; exposes only already-public cycle fields.
- `manual_review_only` filters on `manual_review_required` (set for
  MANUAL_REVIEW_REQUIRED, BLOCKED_TIMEOUT, BLOCKED_UNKNOWN_STATE) — the failure set.
  Failure reason comes from `blocked_reason`.
- Ship read-only monitoring before any actuation UI so the risky slices land small,
  as operator-approved draft PRs.
- A globally armed flag is insufficient identification for physical control.
  `FARM_SWAPMOD_A1MINI_DIRECT_CANARY_TARGET_PRINTER_ID` is default-null and a
  request must match it at the route and service boundaries.
- Treat returned server state, not a successful HTTP status alone, as the
  authority. Only `COMMAND_SENT` plus the expected verification state advances
  the UI; any other result is manual-review-only.
- Opening or cancelling the confirmation dialog creates no persistent cycle.
  The cycle is created immediately before the first transport request after the
  operator checks every server-owned item.
- Cycles newer than the most recent `READY_FOR_NEXT_PRINT` form the unresolved
  review window. A different cycle in that window blocks direct transport, which
  prevents a refresh or second tab from repeating uncertain motion.
- A physical send requires a durable active-state claim. SQLite uses
  `BEGIN IMMEDIATE`; PostgreSQL uses a per-printer transaction advisory lock. The
  cycle is refreshed under that lock and `START_STEP` is committed before the
  transport call. If the process or final DB write fails after send, the durable
  active state blocks another command and requires reconciliation/manual review.
- Sequence validation and transport use the same byte snapshot. The service reads
  the allowlisted file once, verifies that byte string against the configured
  SHA-256, decodes those exact bytes as UTF-8, and sends only that text.

## Implementation and harness changes

- Manual conflict resolution was limited to `PrintersPage.tsx`, generated
  `static/index.html`, and the generated JavaScript asset. Vite regenerated the
  static bundle from the resolved source.
- The audit adds one default-null target-printer setting and extends the existing
  status response with that ID. It changes no permission, authentication rule,
  dependency, migration, feature-flag default, raw-command boundary, or external
  service contract.
- The transaction hardening is internal to the existing direct-canary service. It
  adds no schema or dependency. The service intentionally commits the active
  transition before crossing the physical transport boundary, then commits the
  sent/failed transition; a final commit failure leaves the earlier active state
  durable and non-retryable.
- Final runtime browser evidence used only the isolated `farm_wp110_audit`
  harness on ports 18110/19110 with a fresh synthetic database and no printer
  records. No production credential, customer data, real printer, MQTT, FTPS, or
  raw G-code path was used.

## Validation

Observed on 2026-07-14 KST:

- `SwapModPlateChangeControl.test.tsx`: 13/13 passed, including target-printer
  eligibility, full server checklist, command-failure and uncertain transport,
  uncertain verification, unexpected state, disarm clearing, and unresolved-cycle
  paths.
- Full frontend: 176 files / 2327 tests passed. ESLint and the production Vite
  build passed; only the existing large-chunk warning remains.
- `make test-swapmod-a1mini-direct-canary`: 2/2 harness mock tests and 27/27
  backend service/architecture/API tests passed, including named-target,
  competing-cycle, stale-cycle, exact-byte send, unreadable/non-UTF-8 sequence,
  durable pre-send intent, transport-exception persistence, SQLite concurrency,
  and PostgreSQL lock-call failures.
- A separate ephemeral PostgreSQL 16.4 run issued two concurrent requests against
  one cycle and observed exactly one synthetic send; the second request failed
  `cycle_state_not_ready_for_step`.
- Ruff 0.14.11 check and format check passed for every changed backend file. A
  diagnostic repository-wide run reported 47 existing findings outside this WP;
  no unrelated file was reformatted.
- `make verify-fast FRONTEND_TESTED=1`: 190 harness tests twice plus 2
  characterization tests passed.
- `make test-unit` and `make test-contract`: 190/190 harness tests each passed.
  `make test-integration` passed against the running isolated harness.
- `make verify-full FRONTEND_TESTED=1` against a fresh PostgreSQL harness on
  18141/19141 passed, including root/health/docs/mock smoke and 2 scenarios.
  Bambuddy started healthy; the stale prior harness volume was preserved, not
  deleted, and bypassed with a fresh Compose project.
- The runtime status reported both real-command flags false and target printer
  `null`. Headless Chrome at 1440x1000 and 390x844 passed with the printer
  operator surface present and the SwapMod control absent by default: no
  horizontal overflow, clipped visible control, failed image, browser/runtime
  error, failed response, or failed load.
- The main Bambuddy instance at port 18000 remained healthy throughout.
- A fresh isolated setup followed by Chrome verification of the real `/` printer
  operator surface passed at 1440x1000 and 390x844. Both views had meaningful
  content, no error overlay, console/runtime/network/HTTP error, failed visible
  image, horizontal overflow, or default-off SwapMod control. The initial
  `/printers` probe was correctly diagnosed as an undefined route and rerun at
  the application's actual root route.

## Failure and recovery

- UI preview/list failures remain read-only failures. Existing backend gates reject
  invalid actuation attempts; verification failure terminates in `MANUAL_REVIEW`.
- A missing/incorrect named canary, uncertain transport or verification response,
  unexpected returned state, stale cycle, or competing unresolved cycle fails
  closed before another physical command.
  Cancelling before confirmation leaves no cycle.
- A transport exception is treated as an uncertain physical outcome and is
  committed to manual review with retry disabled. If the process stops after the
  durable active claim, subsequent state checks keep that active state blocked
  until manual inspection; it is never restored to a ready state automatically.
- Do not automatically retry or resume an uncertain physical bed action. An
  operator must inspect the printer before any new attempt.
- Rollback is the Draft PR merge commit; there is no migration or persistent schema
  change to reverse. Both canary flags remain default-off.

## Outcomes

- PR #90 is intentionally Draft and excluded from delegated routine merge because
  it contains physical-actuation UI and safety-gate-adjacent behavior.
- Required next gate: explicit operator approval plus operator-present physical E2E
  using the WP-076 checklist. Simulation and browser success are not physical
  safety evidence.
- Bambuddy remains the sole command authority. No arbitrary G-code endpoint exists
  or is introduced by this Work Package.

## Risks and human gates

- Slice 3 edits reviewed sequences and slice 4 can trigger real actuation. Keep the
  PR Draft, flags default-off, checklist and phrase server-owned, and raw G-code
  unavailable until the operator-present gate is complete.
