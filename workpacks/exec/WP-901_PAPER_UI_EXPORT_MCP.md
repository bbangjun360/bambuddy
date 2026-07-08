# WP-901 Paper UI Export via Paper Desktop MCP

# Purpose

Give designers and operators an editable, source-derived snapshot of the Bambuddy UI
inside Paper (local desktop design tool) without redesigning the running UI. The export
lets UI review and iteration happen outside the control plane, which keeps the charter
rule "use the existing Bambuddy UI" intact while still enabling measured UI proposals.

# Current Behavior

- `frontend/src/App.tsx` defines all routes (main app, SpoolBuddy kiosk, standalone
  login/setup). `frontend/src/pages/SettingsPage.tsx` defines `validTabs` for settings.
- `frontend/src/index.css` holds the CSS design tokens (`--accent`, `--bg-*`, ...).
- New scripts (this WP, currently uncommitted on `feature/paper-ui-export-mcp`):
  - `frontend/scripts/paper-ui-export-core.mjs` — pure functions that build a route
    manifest (26 mirror artboards + 4 proposed SwapMod console design drafts = 30),
    extract design tokens from CSS, and render inline-style Paper-compatible HTML.
    No network, no filesystem.
  - `frontend/scripts/export-paper-ui.mjs` — writes the bundle to
    `frontend/dist/paper-ui-export/` (`paper-ui-manifest.json`, `paper-tokens.json`,
    `html/*.html`). `--dry-run` validates without writing.
  - `frontend/scripts/upload-paper-ui.mjs` — talks to the local Paper Desktop MCP at
    `http://127.0.0.1:29979/mcp` (streamable HTTP, JSON-RPC). Default is a read-only
    dry run; `--upload` creates a NEW Paper file and populates tokens and artboards.
- Behavior observed by running `make test-paper-export` (vitest suite, export, upload
  dry run) on 2026-07-02.

# Scope

In scope:

- Source-derived export bundle (manifest + tokens + inline-style HTML artboards).
- Parity checks that fail when the manifest drifts from `App.tsx` routes or
  `SettingsPage.tsx` tabs.
- Dry-run-by-default upload through the local Paper MCP.
- npm scripts `paper:export`, `paper:export:dry-run`, `paper:upload`,
  `paper:upload:dry-run` and Makefile targets `test-frontend`, `test-paper-export`.
- Proposed SwapMod design drafts seeded into Paper via the same pipeline as the
  design surface for the upcoming SwapMod control feature. Per operator direction
  (2026-07-08) the design is NOT a standalone console but: (1) a plate-change control
  on each connected printer card in the Printers page, (2) a confirmation gate
  (checklist + server phrase), and (3) a SwapMod settings page holding a failure log
  and a sequence/speed editor. Draft artboards: `/?swapmod=plate-change`,
  `/?swapmod=confirm`, `/settings?tab=swapmod#failures`, `/settings?tab=swapmod#sequences`.
  These are net-new screens that do NOT yet exist in `App.tsx`; they carry
  `source: 'design-draft:swapmod-console'` and `proposed: true`, and are exempt from
  the route-parity check. The React implementation is a separate operator-approved WP.

Out of scope:

- Any change to the running Bambuddy UI, routes, or CSS.
- Screenshot- or DOM-capture-based export.
- Importing edits back from Paper into the codebase (separate, human-driven WP).
- Building the SwapMod React console (separate WP; this WP only seeds its design drafts).
- Remote/non-localhost Paper endpoints.

# Architecture Boundaries

- Export reads only repository files; it never talks to printers, backend, or ERP.
- Upload talks only to the operator's local Paper Desktop MCP (127.0.0.1). It is not a
  service dependency of Bambuddy; nothing in backend or frontend runtime imports it.
- Paper never gains any authority: no printer, queue, or ERP data leaves the repo —
  the bundle contains only route names, layout scaffolding, and design tokens.
- The manifest is documentation of the real UI, not a second source of truth: the
  parity test enforces that every non-proposed artboard path exists in `App.tsx` /
  `validTabs`. Proposed design-draft artboards are explicitly exempt (they are new
  screen proposals, labelled `proposed: true`), so they cannot silently mask drift in
  the real-screen set.

# Milestones

1. Export core + tests green (`npx vitest run src/__tests__/paper-export`). DONE
2. Route/tab parity check guards manifest drift. DONE
3. Harness targets `test-frontend` and `test-paper-export` exist and pass. DONE
4. Commit and open PR for `feature/paper-ui-export-mcp`. DONE 2026-07-08
5. Human-gated first real upload (`npm run paper:upload`) against a running Paper
   Desktop; record the produced file URL here as evidence. DONE 2026-07-08 —
   operator-approved upload of 30 artboards / 51 tokens produced
   `https://app.paper.design/file/01KX0ETDMK3N9VAM8FZM5DV0NY`.
6. Seed proposed SwapMod console design drafts for Paper iteration. DONE 2026-07-08

# Progress

- [x] 2026-07-02 Export/upload scripts and vitest suite exist and pass (4 tests).
- [x] 2026-07-02 Fixed manifest drift: `settings-workflow` (nonexistent tab) replaced
      with `settings-queue`; settings tab pills aligned with `validTabs`.
- [x] 2026-07-02 Added parity test (manifest paths vs `App.tsx` routes and
      `SettingsPage.tsx` `validTabs`); suite now 5 tests, all green.
- [x] 2026-07-02 Added `test-frontend` and `test-paper-export` Makefile targets;
      `make test-paper-export` passes end-to-end (tests + export + upload dry run).
- [x] 2026-07-08 Added 4 proposed SwapMod console design-draft artboards
      (`Farm / SwapMod` section, `proposed: true`, exempt from parity); vitest suite
      updated and green (5 tests); export reports 30 artboards / 51 tokens.
- [x] 2026-07-08 Commit + PR for `feature/paper-ui-export-mcp`.
- [x] 2026-07-08 Operator-approved first real upload; Paper file
      `https://app.paper.design/file/01KX0ETDMK3N9VAM8FZM5DV0NY` (30 artboards).
- [x] 2026-07-08 Revised SwapMod drafts per operator direction (printer-card control +
      confirmation gate + settings failure-log + sequence/speed editor); re-uploaded to
      Paper file `https://app.paper.design/file/01KX0H7ZKKHA09BK1HS1Z23CR2` (30 artboards).

# Decisions

- Hand-curated artboard list instead of parsing routes at export time: keeps rendering
  deliberate (viewport sizes, highlights per screen). Drift risk is handled by the
  parity test instead — a route or tab rename now fails `test-paper-export`.
- Upload is dry-run by default; mutation requires the explicit `--upload` flag. Chosen
  so an agent or CI running package scripts cannot mutate Paper accidentally.
- `test-frontend`/`test-paper-export` are NOT wired into `verify-fast`/`verify-full`
  yet because those gates currently assume a Python-only toolchain and must stay green
  on machines without `node_modules`. Wiring frontend into `verify-full` is a separate
  decision for a future WP; until then this WP's Validation section is the gate.

# Harness Changes

- `frontend/src/__tests__/paper-export/paperUiExport.test.mjs` — token extraction,
  manifest coverage, HTML validity (no class/style-tag/grid/margin/table/screenshot),
  rejection cases, and source parity (routes + settings tabs read from real sources).
- `Makefile`: `test-frontend` (full frontend suite) and `test-paper-export`
  (paper-export vitest + export + upload dry run). Both run without Docker and without
  a running Paper Desktop.

# Implementation

- `frontend/scripts/paper-ui-export-core.mjs`: `buildPaperUiManifest`,
  `buildPaperTokens`, `generatePaperExport`, `validatePaperHtml`.
- `frontend/scripts/export-paper-ui.mjs`: CLI wrapper, exits non-zero on validation
  errors, `--dry-run`/`--out`/`--css`.
- `frontend/scripts/upload-paper-ui.mjs`: minimal MCP client (initialize → session id
  → `tools/call`), chunked `create_tokens`, `create_artboard` + `write_html` per
  artboard, `finish_working_on_nodes`.
- `frontend/package.json`: `paper:*` scripts.

# Validation

```bash
make test-paper-export        # vitest (5 tests) + export + upload dry run
make test-frontend            # full frontend suite incl. i18n parity
cd frontend && npm run paper:export:dry-run
cd frontend && npm run paper:upload:dry-run
```

Expected: all tests pass; export reports 30 artboards / 51 tokens; upload dry run
reads the bundle and prints the MCP endpoint without contacting it.

End-to-end scenario (human-gated): with Paper Desktop running locally,
`npm run paper:upload` creates one Paper file containing 30 artboards and the token
set, and prints its URL.

# Failure and Recovery

- Export failures are fail-fast: validation errors print per-file and exit code 1;
  nothing is partially written before validation passes.
- Upload is NOT idempotent: every `--upload` run creates a new Paper file. Recovery
  from a failed upload is to delete the partial file in Paper and rerun; there is no
  automatic resume. Do not script retry loops around `--upload`.
- Upload failures (no session id, tool error, HTTP >= 400, 120 s timeout) abort with
  the MCP error message; Bambuddy itself is untouched in all cases.

# Risks and Human Gates

- HUMAN GATE: `npm run paper:upload` (or any `--upload` invocation) mutates the
  operator's Paper workspace and creates a new file per run. Agents must not run it
  without explicit human approval in the session. Dry-run variants are always safe.
- Drift risk: the artboard list is curated by hand. Mitigated by the parity test; if
  that test fails after a route change, update `DEFAULT_ARTBOARDS`, do not weaken the
  test.
- Charter guard: this WP must not become a UI redesign channel. Edits made in Paper
  come back only through a future, separately approved WP.
- No secrets: the bundle contains no credentials, serials, IPs, or customer data.

# Outcomes

- Deterministic, source-derived Paper export with drift protection and a dry-run-safe
  MCP upload path. Committed and PR'd; operator-approved first real upload produced
  Paper file `https://app.paper.design/file/01KX0ETDMK3N9VAM8FZM5DV0NY` (30 artboards /
  51 tokens). The bundle also seeds 4 proposed SwapMod console design drafts as the
  Paper design surface for the forthcoming SwapMod console WP (separate, operator-
  approved). Applying any Paper edits back into the codebase remains out of scope here.
