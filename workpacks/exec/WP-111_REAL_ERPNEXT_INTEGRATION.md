# Purpose

Connect the existing Bambuddy ERP adapter to a non-production ERPNext site and
prove one read-only Work Order import plus one idempotent Draft-only result write.
This closes the gap between the mock-only WP-030/WP-040 implementation and the
real Frappe Resource API without granting ERPNext any printer authority.

# Current Behavior

- `backend/app/services/erp_readonly.py` fetches Work Orders from the mock-only
  `/erp/api/resource` path.
- `backend/app/services/erp_draft_write.py` creates and looks up `Farm Draft
  Result` documents, but lookup uses a mock-only query shape and expects a
  single object instead of Frappe's collection response.
- `backend/app/core/config.py` keeps both ERP feature flags disabled and points
  at `mock-services` by default.
- `harness/mock_services.py` validates authorization, transient failures,
  timeout recovery, Draft state, and forbidden submit/accounting mutations.
- `make verify-fast` passed on `origin/farm-main` at the WP-111 branch point on
  2026-07-10.

# Scope

In scope:

- Frappe-compatible `/api/resource` paths and collection filters.
- Existing mock compatibility and failure scenarios.
- A disposable, synthetic ERPNext sandbox bootstrap and live contract probe.
- Read-only Work Order import and Draft-only `Farm Draft Result` creation,
  duplicate recovery, and reconciliation.
- Operator documentation for configuration, verification, and cleanup.

Out of scope:

- ERP submission, inventory posting, accounting posting, or automatic queueing.
- Production credentials, production data, printer commands, SwapMod, and UI.
- ERPNext production deployment or direct access to its database.
- Changes to Bambuddy database models or migrations.

# Architecture Boundaries

- Bambuddy remains the sole authority for print execution and printer commands.
- ERPNext is accessed only through its HTTP API; the adapter never reads its
  database.
- `farm_event_id` is the external idempotency key and must be unique in the
  sandbox DocType.
- All outbound documents remain `docstatus = 0` (Draft).
- Both ERP capabilities remain disabled by default.
- Synthetic credentials and records are used for local verification only.

# Milestones

1. Extend the mock and focused tests to express Frappe resource paths,
   collection filters, empty results, duplicate results, and timeout recovery.
2. Add configurable API prefix handling and Frappe collection parsing to both
   clients while preserving the existing safety classifications.
3. Add a reproducible non-production ERPNext sandbox/bootstrap/probe flow.
4. Run focused tests, `make verify-fast`, and the live sandbox scenario; record
   evidence and rollback instructions.

# Progress

- [x] 2026-07-10: Read charter, known issues, backlog, ERP module guide, and
  ExecPlan rules.
- [x] 2026-07-10: Created `feature/wp-111-real-erpnext-integration` from the
  latest `origin/farm-main`; clean baseline `make verify-fast` passed.
- [x] 2026-07-10: Added Frappe-shaped paths, collection responses, empty and
  duplicate lookup failures, and lookup-first timeout recovery tests.
- [x] 2026-07-10: Implemented configurable API prefix and ERP timezone handling.
- [x] 2026-07-10: Bootstrapped ERPNext v16.26.2 and ran the live contract twice.
- [x] 2026-07-10: Focused read-only (14) and Draft-write (24) tests passed.
- [x] 2026-07-10: verify-fast and verify-full passed with 189 harness tests,
  two characterization tests, four smoke targets, and two scenario tests.

# Decisions

- Treat `FARM_ERP_BASE_URL` as the ERPNext site root and add an API-prefix
  setting, rather than embedding the mock's `/erp` segment in service code.
- Use the standard Resource API and JSON `filters`/`fields` parameters. Do not
  add a custom remote method for Bambuddy.
- Enforce idempotency by looking up `farm_event_id` before create and after an
  ambiguous timeout. The HTTP `Idempotency-Key` remains diagnostic metadata,
  not the sole duplicate guard.
- Keep the real ERPNext stack separate from the fast deterministic harness so
  normal CI does not pull or initialize a large ERP image.
- Convert aware completion timestamps to the configured ERP timezone and
  Frappe database format before posting; offset ISO strings fail in MariaDB.

# Harness Changes

- Teach `harness/mock_services.py` the Frappe `/api/resource` path and list
  response for filtered Draft lookup.
- Add focused client tests for URL construction, JSON filters and fields,
  empty lookup, ambiguous duplicate lookup, and timeout-after-create recovery.
- Preserve expired token, 429, 500, invalid payload, and no-submit assertions.

# Implementation

- `backend/app/core/config.py`: API-prefix setting; flags remain default-off.
- `backend/app/api/routes/erp_readonly.py`: pass API-prefix configuration.
- `backend/app/api/routes/erp_draft_write.py`: pass API-prefix configuration.
- `backend/app/services/erp_readonly.py`: standard Resource API URL.
- `backend/app/services/erp_draft_write.py`: standard Resource API URL,
  Frappe collection lookup, and lookup-first idempotency.
- `harness/mock_services.py` and existing ERP tests: updated contracts.
- harness/scripts/erpnext_sandbox_bootstrap.py: repeatable synthetic records
  and owner-only sandbox token file.
- harness/scripts/erpnext_live_contract.py: real read/Draft/idempotency probe.
- docs/runbooks/ERPNEXT_SANDBOX_VALIDATION.md and docs/modules/ERP.md:
  configuration, evidence, rollback, and production handoff gates.

# Validation

Run in this order:

1. Focused ERP unit and architecture tests.
2. `make test-erp-readonly`.
3. `make test-erp-draft-write`.
4. `make verify-fast`.
5. Disposable ERPNext live probe: import a synthetic Work Order, create the
   same Draft event twice, reconcile it, and assert one external Draft document.
6. `make verify-full` only after the required local harness services are up.

# Failure and Recovery

- Authentication and invalid payload failures remain non-retryable.
- 429, timeout, and 5xx failures remain retryable.
- A timeout after create performs lookup by stable event ID and never blindly
  creates a second document.
- Empty lookup means not found; multiple results are treated as an unsafe
  contract violation.
- Rollback disables both ERP flags and removes the sandbox containers/volumes
  only with explicit operator approval. No Bambuddy schema rollback is needed.

# Risks and Human Gates

- ERPNext version changes can alter fields and validation behavior; the live
  probe records the tested image version.
- Draft-write remains a state-changing ERP action, so the PR stays draft and
  requires explicit operator approval under the merge policy.
- Sandbox success is not approval for production ERP credentials or automatic
  document submission.

# Outcomes

WP-111 completed the non-production ERPNext integration contract while leaving
both feature flags disabled and adding no Bambuddy schema migration.

Evidence:

- ERPNext v16.26.2 returned the synthetic Work Order through the standard API.
- FDR-00001 remained docstatus 0 and was reused across repeated probe processes.
- Focused read-only and Draft-write suites, verify-fast, and verify-full passed.

Remaining production work is operational: provision a durable ERPNext instance,
create a least-privilege API user, rotate credentials, and run a supervised
configuration window using the documented stop conditions.
