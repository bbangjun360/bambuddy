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
2. **Farm production deploy** (spec WP-01/WP-02) — production compose or
   deploy story for the farm layer: Prometheus + Grafana + ntfy wiring,
   Caddy TLS entry, backup/restore drill. Today `deploy/` ships only the
   upstream app; the farm stack exists only in `harness/`. Largest gap to
   acceptance; nothing blocks starting it.
3. **SwapMod enablement rollout** — runbook and staged flag-enable plan for
   the chain (state machine → transport → readiness → next-print gate →
   scheduler gate) on one canary printer; repeated multi-cycle physical
   validation; then the design decision for an autonomous (not per-step
   human-phrase) actuation path. Operator sessions run as an ordered
   sequence (S1..S9) in `docs/runbooks/SWAPMOD_ROLLOUT_SCHEDULE.md`: no
   fixed dates, next session whenever the operator is available, gated
   only on the previous session's validated evidence.
4. **Real ERPNext integration** (spec WP-04 completion) — stand up a real
   ERPNext instance, point the existing adapter at it (config override),
   validate read-only import and Draft-write against it. The adapter code is
   done; only the mock has ever been the target.
5. **Actual cost ledger** (spec WP-05) — estimate snapshot vs actual
   material/energy/machine-time, failed/reprint cost separation, KRW.
   Untouched so far. Depends on 4 for the ERP payload end.
6. **Obico phase 2** (spec WP-09) — assisted pause after shadow-mode sample
   collection. Blocked on: enough production shadow samples, which needs 2.
7. **WP-9xx off-track tooling closure** — WP-901 Paper UI export: commit,
   PR, human-gated first upload. Not on the acceptance path; do not let it
   preempt items 1–6.

## Explicitly deferred (do not start without operator approval)

- ERP Stage C–E (automatic queue, auto-submit) — spec gates these on a full
  reconciliation cycle and finance approval.
- UI redesign (spec WP-12) — only after operators have used the system.
- Multi-fork governance apparatus (spec WP-00 full form: fork catalog,
  farm-contracts, components.lock) — right-size later; current single-repo
  reality does not need it.
- Further diagnostics/contract/validator/template hardening WPs — the
  WP-084..WP-106 series is closed. Fold any genuinely needed hardening into
  the WP that owns the capability.
