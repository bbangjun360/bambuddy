# WP-110 SwapMod Control UI

## Observable outcome

An operator runs the SwapMod plate-change flow from the Bambuddy UI instead of raw
`curl`: a plate-change control on each connected printer card, a confirmation gate
(10-item checklist + server read-only phrase), and a SwapMod settings tab with a
failure log and a per-action sequence/speed editor. Sessions S1..S9 proved the
backend chain by hand; this WP surfaces it safely. Design iterated in Paper first
via the WP-901 pipeline.

This slice's observable outcome: `GET /api/v1/swapmod-state-machine/cycles` returns
SwapMod cycles newest-first (with `printer_id`, `manual_review_only`, `limit`
filters), read-only, feeding the overview and failure log.

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

- Slice 1 (this PR): `GET /cycles` exists with ordering/filters/limit, is read-only
  and flag-safe, and the integration test class is green (22 tests).
- Slices 2-4: failure log + overview render from the list endpoint; the sequence
  editor produces reviewed re-hashed versions (never a live push); the printer-card
  control drives the existing gated actuation flow with the operator ticking the
  checklist and the server-provided phrase shown read-only, flags default-off.

## Architecture boundaries

- Bambuddy stays the sole printer-command authority; the UI only calls existing
  gated endpoints. The list endpoint is read-only.
- Actuation from the UI keeps every gate: canary flags default-off, the checklist is
  ticked by the operator, the confirmation phrase is shown read-only from the server
  — the UI never fabricates either.
- The sequence editor produces reviewed, re-hashed versions; it does not send G-code.

## Milestones

1. Backend read-only cycle listing + test. DONE 2026-07-09
2. `swapmodApi` client + SwapMod settings tab with failure log. TODO
3. Sequence/speed editor (versioned, re-hashed, reviewed). TODO — operator-approved
4. Printer-card plate-change control + confirmation gate. TODO — operator-approved

## Progress

- [x] 2026-07-09 `list_swapmod_cycles` service helper +
      `GET /swapmod-state-machine/cycles` (printer_id / manual_review_only / limit),
      serialized via existing `public_swapmod_cycle`.
- [x] 2026-07-09 Integration tests: newest-first ordering, printer filter,
      failure filter, limit, safe read when disabled; full
      `test_swapmod_state_machine_api` class green (22 tests) in the backend image.

## Decisions

- List endpoint returns 200 regardless of the state-machine flag, matching the other
  read endpoints; exposes only already-public cycle fields.
- `manual_review_only` filters on `manual_review_required` (set for
  MANUAL_REVIEW_REQUIRED, BLOCKED_TIMEOUT, BLOCKED_UNKNOWN_STATE) — the failure set.
  Failure reason comes from `blocked_reason`.
- Ship read-only monitoring before any actuation UI so the risky slices land small,
  as operator-approved draft PRs.

## Validation

```bash
docker run --rm --network none -e LOG_TO_FILE=false \
  -e DATA_DIR=/tmp/bambuddy-wp110-tests -e LOG_DIR=/tmp/bambuddy-wp110-tests/logs \
  -e PYTHONDONTWRITEBYTECODE=1 -v "$(pwd)":/workspace:ro -w /workspace \
  --entrypoint python farm_wp030-bambuddy:latest \
  -m unittest backend.tests.integration.test_swapmod_state_machine_api
```

Expected: 22 tests OK.

## Risks and human gates

- Slices 3-4 trigger real actuation and edit control sequences → operator-approved
  draft PRs, flags default-off, no auto-filled checklist/phrase, no raw G-code push.
  This slice is read-only and routine-mergeable.
