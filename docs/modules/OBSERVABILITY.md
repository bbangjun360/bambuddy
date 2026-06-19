# Observability Module

## Goal

Make every Work Package diagnosable before enabling automation.

## Required fields

- timestamp
- service
- level
- correlation ID
- event ID or command ID
- printer/job identifiers using non-secret internal IDs
- state transition
- result and error category

Do not log access codes, API tokens, raw customer files, or personal data.

## Initial metrics

- application health
- queue depth
- slice duration/failure
- integration delivery success/failure
- bed-cycle state and duration
- ERP dead-letter count
- print success/failure
- actual versus estimated cost when available

## First rollout

Use the existing Bambuddy metrics and logs first. Add custom metrics only for genuinely
new behavior. Do not create a second telemetry database when Prometheus is sufficient.
