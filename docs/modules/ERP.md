# ERP Module

## Ownership

ERPNext owns commercial and accounting data. Bambuddy owns print execution.

## Integration order

1. mock ERP read
2. ERPNext sandbox read
3. production-order Draft creation in Bambuddy
4. completion event to mock ERP
5. ERPNext Draft document creation
6. reconciliation
7. limited automatic submission only after finance approval

## Rules

- ERPNext never controls a printer.
- Adapter uses public APIs, not direct database access.
- Every outbound event has a stable event UUID.
- Repeated delivery produces the same external result.
- HTTP timeout after a write triggers lookup, not blind re-create.
- Initial inventory/accounting documents remain Draft.
- Synthetic SKUs, customers, and amounts are used in CI.

## Harness scenarios

- valid Work Order
- missing artifact mapping
- duplicate Work Order
- expired token
- 429 with retry-after
- 500 transient error
- request timeout after document creation
- duplicate completion event
- reconciliation mismatch

## Real ERPNext Contract

WP-111 validates the existing adapter against the standard Frappe Resource API:

- site root from FARM_ERP_BASE_URL
- Resource API prefix from FARM_ERP_API_PREFIX (default /api)
- token header value from FARM_ERP_API_TOKEN
- Frappe Datetime conversion in FARM_ERP_TIMEZONE (default Asia/Seoul)
- Work Order read at /api/resource/Work Order/{name}
- Draft lookup with JSON filters and fields
- lookup-before-create plus lookup-after-timeout using unique farm_event_id

Both FARM_ERP_IMPORT_ENABLED and FARM_ERP_DRAFT_POSTING_ENABLED remain disabled
by default. The live contract rejects duplicate lookup results and any
non-Draft response. ERPNext submission, inventory, accounting, and printer
control remain out of scope.

Use docs/runbooks/ERPNEXT_SANDBOX_VALIDATION.md for the disposable ERPNext
bootstrap, synthetic data, live probe, rollback, and production handoff gates.
