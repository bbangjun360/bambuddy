# Work Package Backlog

Ordered list of the remaining gaps between the current repository and the
acceptance criteria in `docs/archive/FULL_SPEC_v1.1.md` §23. Pick the highest
unblocked item unless the operator names a task. A new Work Package that is
not on this list needs an operator decision first — add it here in the same
PR that creates it.

Status 2026-07-02: WP-000..WP-106 built the full software skeleton
(Orca slicing, ERP read/draft, bed automation simulator, SwapMod chain,
diagnostics, release/acceptance packets). Everything is default-off,
mock-targeted, and harness-validated only. The remaining work is mostly
OUTSIDE the code: deployment, real integrations, physical rollout.

## Priority order

1. **Harness and process debt** — resolve the OPEN items in
   `docs/KNOWN_ISSUES.md` (smoke fail-fast; scenario target; ExecPlan
   hygiene pass; frontend gate decision). Git object repair done 2026-07-02.
   Small, unblocks everything else.
2. **Farm production deploy — completed by WP-109** (spec WP-01/WP-02)
   — production compose/deploy story for Prometheus + Grafana + ntfy wiring,
   Caddy TLS entry, and backup/restore drill. The farm stack now lives under
   `deploy/` with pinned service images, local TLS, backup mount, runbook, and
   config tests. Future production hardening should be operator-named or folded
   into the owning capability instead of reopening this backlog item.
3. **SwapMod enablement rollout — COMPLETE (S1..S9 done 2026-07-08).** The
   full chain (state machine → transport → readiness → next-print gate →
   scheduler gate) was validated on the A1 Mini canary across supervised
   sessions S1..S9 (`docs/runbooks/SWAPMOD_ROLLOUT_SCHEDULE.md`); the §23
   acceptance loop and all gate safety invariants are evidenced in
   `docs/releases/SWAPMOD_ROLLOUT_S1_S9_ACCEPTANCE_LEDGER.md`. S9 go/no-go
   decision: **GO** to charter the autonomous (not per-step human-phrase)
   actuation design WP. Open precondition for that WP: the S1 front-hook jam
   root cause is still mechanically unconfirmed and must be closed with
   evidence before autonomous actuation is enabled in steady state. The
   autonomous-actuation design WP is a separate operator-approved item (next
   SwapMod work); allocate its WP number per the AGENTS.md rule when starting.
4. **Real ERPNext integration — completed by WP-111** (spec WP-04 completion).
   The standard Frappe Resource API contract, token authentication, Work Order
   read, Draft-only result creation, timeout recovery, and external idempotency
   were validated against ERPNext v16.26.2 on 2026-07-10. The reproducible
   sandbox/bootstrap/live probe and production handoff gates are documented in
   docs/runbooks/ERPNEXT_SANDBOX_VALIDATION.md. Durable production provisioning
   and least-privilege credentials remain operator deployment work.
5. **Actual cost ledger** (spec WP-05) — estimate snapshot vs actual
   material/energy/machine-time, failed/reprint cost separation, KRW.
   Untouched so far. The ERP payload dependency is unblocked by WP-111.
6. **Obico phase 2** (spec WP-09) — assisted pause after shadow-mode sample
   collection. Blocked on: enough production shadow samples, which needs 2.
7. **WP-9xx off-track tooling closure** — WP-901 Paper UI export: DONE
   2026-07-08 (committed PR #86, human-gated first upload complete). Not on the
   acceptance path; do not let it preempt items 1–6.
8. **SwapMod control UI (WP-110)** — operator-approved 2026-07-09. Replace the
   curl-driven S1..S9 flow with in-app controls: a plate-change control on each
   connected printer card, a confirmation gate (10-item checklist + server
   read-only phrase), and a SwapMod settings tab with a failure log and a
   sequence/speed editor. Design iterated in Paper first (WP-901 pipeline).
   Follow-on to the completed rollout (item 3); operability, not on the §23
   acceptance path. SAFETY: actuation + sequence-editor changes are
   operator-approved (draft PR); the sequence editor writes a NEW reviewed
   version with a fresh SHA-256, never a live raw G-code push (preserves the
   WP-076 allowlist+hash model); flags stay default-off; the UI never
   auto-fills the checklist or phrase. Read-only monitoring (failure log,
   overview) ships first and is routine-mergeable.
9. **Operator UI redesign — started by WP-112** — operator-approved 2026-07-13
   after upstream v0.2.4.9 integration. WP-112 changes only the shared operator
   shell and was visually approved and merged as PR #93. WP-113 is Draft PR #94
   and changes only the printer fleet surface: status summary,
   responsive tools, and printer-card scan hierarchy. Queue,
   library/inventory, and settings redesigns follow as separate observable Work
   Packages after operators review each preceding slice; no page workflow,
   printer command, or backend contract is changed by WP-112 or WP-113.

## Explicitly deferred (do not start without operator approval)

- ERP Stage C–E (automatic queue, auto-submit) — spec gates these on a full
  reconciliation cycle and finance approval.
- Multi-fork governance apparatus (spec WP-00 full form: fork catalog,
  farm-contracts, components.lock) — right-size later; current single-repo
  reality does not need it.
- Further diagnostics/contract/validator/template hardening WPs — the
  WP-084..WP-106 series is closed. Fold any genuinely needed hardening into
  the WP that owns the capability.
