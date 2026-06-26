# Test Harness Architecture

## Purpose

The harness gives Codex and humans fast, deterministic evidence that Bambuddy still runs
and that each added module behaves correctly under success and failure.

## Pyramid

### H0 — Static gates

- format, lint, type checks
- secret scan
- dependency and container scan
- customization-boundary check
- context-budget check
- architecture import/dependency rules

### H1 — Unit and characterization

- existing Bambuddy behavior captured before modification
- pure cost and policy calculations
- queue/state transition tests
- permission tests
- database model tests

### H2 — Contract

- OpenAPI and JSON Schema
- ERP event envelope
- PrintFlow adapter API
- Orca slice request/result
- webhook signature and idempotency

### H3 — Container integration

Use real:

- Bambuddy build
- PostgreSQL
- OrcaSlicer sidecar for slicer Work Packages

Use deterministic mock:

- ERPNext HTTP behavior
- PrintFlow adapter behavior
- Obico inference response

### H4 — Scenario and fault injection

Scenarios:

- HTTP timeout
- duplicate callback
- connection reset
- 429/500 response
- delayed acknowledgement
- process restart
- stale state
- database retry
- adapter reports success but post-check fails

### H5 — Protocol simulator

A later Work Package builds a Bambu protocol simulator with sanitized MQTT telemetry,
command acknowledgement, state transitions, and file-transfer behavior.

Until this exists, printer-command CI uses in-process fakes and no real printer
credentials.

### H6 — Hardware canary

- named test printer
- named PrintFlow test device
- non-production material and files
- human checklist
- physical E-stop
- automatic rollout disabled

## Command contract

The repository exposes stable commands:

```bash
make harness-up
make harness-down
make harness-reset
make harness-health
make test-unit
make test-characterization
make test-contract
make test-integration
make test-scenario
make verify-fast
make verify-full
```

Codex should not invent a different command for each PR.

## Evidence

CI retains:

- JUnit/XML or equivalent test report
- service logs
- health response
- migration result
- contract diff
- fixture/scenario name
- image SHA/digest
- Git commit SHA
