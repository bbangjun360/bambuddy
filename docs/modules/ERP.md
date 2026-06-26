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
