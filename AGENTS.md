# Repository Instructions

## Mission

Keep the upstream Bambuddy application runnable while adding one independently
testable farm capability at a time.

## Read order for every task

1. Read `docs/00_PROJECT_CHARTER.md`.
2. Read exactly one current file under `workpacks/`.
3. Read only the module documents referenced by that Work Package.
4. Read `docs/archive/FULL_SPEC_v1.1.md` only when the Work Package explicitly
   requests it.
5. For complex work, create and maintain an ExecPlan following `.agent/PLANS.md`.

## Development method

- Start from a green, running Bambuddy baseline.
- One PR implements one observable vertical slice.
- Keep `farm-main` deployable.
- Prefer configuration, an adapter, a sidecar, a hook, or an extension package
  before modifying upstream core code.
- Add a characterization test before changing existing Bambuddy behavior.
- Add or update the harness before implementing a new external integration.
- New features must be disabled by default until their tests and canary criteria pass.
- Do not redesign the Bambuddy UI during the initial phases.

## Hard architecture rules

- Bambuddy is the sole authority for printer state-changing commands.
- External modules must not connect directly to Bambu MQTT or FTPS.
- OrcaSlicer only slices; it never starts or controls a printer.
- ERPNext never controls a printer.
- Do not access another service's database directly.
- Do not start the next print until the bed state is verified READY.
- Never automatically resume an uncertain physical bed action after restart.
- ERP inventory and accounting writes must be idempotent and initially Draft only.
- Failed and reprinted runs retain separate history and cost records.
- Never expose a general arbitrary G-code endpoint.

## Scope control

Before editing, state:

- Goal
- Files and modules in scope
- Constraints
- Done-when behavior
- Tests to run

Stop and revise the plan if the change requires:

- more than one service contract change,
- an unrelated UI change,
- more than one destructive migration,
- a new production dependency not required by the Work Package,
- or a core patch not recorded in `.fuzzyline/PATCH_LEDGER.yaml`.

## Required validation

Use the narrowest applicable commands first:

```bash
make verify-fast
make test-unit
make test-contract
make test-integration
make verify-full
```

When a target is not implemented yet, implement it in WP-000 instead of silently
skipping validation.

Every PR must include:

- tests demonstrating the behavior,
- failure-path tests,
- migration and rollback notes,
- feature-flag default,
- changed contracts,
- logs/metrics needed to diagnose failure,
- and a statement that Bambuddy still starts.

## Safety and data

- Never use production printer credentials, ERP tokens, or real customer data in tests.
- Never execute destructive Docker volume, database, Git, printer, or actuator commands
  without explicit human approval.
- Hardware tests use a named canary device and a human checklist.
- Simulation success is not evidence that the physical system is safe.
- Redact serial numbers, access codes, API keys, IPs, and personal information from fixtures.

## Fork updates

- `main` is an upstream-only mirror.
- Custom development belongs on `farm-main` and feature branches.
- Integrate upstream in `integration/upstream-*`.
- Read the upstream-update skill and produce an impact report.
- AI-generated update changes never merge automatically.
