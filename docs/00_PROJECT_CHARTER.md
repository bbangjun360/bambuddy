# Project Charter

## Product

A LAN-first production system for a Bambu Lab print farm.

## Central system

The forked Bambuddy application remains the running control plane and system of record
for printer state, print queue, dispatch, print history, material usage, and production
execution.

## Initial UI

Use the existing Bambuddy UI. UI changes require a separately measured and approved
Work Package after operators have used the system.

## Modules

- OrcaSlicer API: server-side slicing only
- ERPNext: customer, order, BOM, inventory valuation, and accounting
- ERP Adapter: idempotent translation between Bambuddy and ERPNext
- PrintFlow Adapter: physical bed-device driver only
- Bambuddy bed automation domain: policy and state-machine owner
- Obico: local ML inference, initially notify-only
- Prometheus/Grafana: metrics and dashboards
- ntfy: local notifications
- Caddy: local TLS entry point

## Non-negotiable invariants

1. Only Bambuddy approves and emits printer state-changing commands.
2. External services do not use Bambu printer credentials.
3. No next job is dispatched before bed readiness is verified.
4. Uncertain physical state becomes MANUAL_REVIEW.
5. ERP writes are idempotent and begin as Draft.
6. Failed attempts and reprints are separate production and cost records.
7. Each change keeps Bambuddy runnable and reversible.

## Delivery policy

- One Work Package active at a time.
- One observable behavior per PR.
- Default-off feature flags for new automation.
- Real hardware only after simulator, dry-run, and canary gates.
- A green baseline is restored before starting the next capability.

## Source of detail

The full historical specification is archived at
`docs/archive/FULL_SPEC_v1.1.md`. It is a reference, not an always-loaded prompt.
