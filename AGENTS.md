# Repository Instructions

## Mission

Keep the upstream Bambuddy application runnable while adding one independently
testable farm capability at a time.

## Read order for every task

1. Read `docs/00_PROJECT_CHARTER.md`.
2. Read `docs/KNOWN_ISSUES.md`. If the task would hit a listed defect, fix or
   unblock that defect first instead of adding another workaround.
3. Read exactly one current file under `workpacks/`. When choosing what to work
   on, take the highest unblocked item from `workpacks/BACKLOG.md`.
4. Read only the module documents referenced by that Work Package.
5. Read `docs/archive/FULL_SPEC_v1.1.md` only when the Work Package explicitly
   requests it.
6. For complex work, create and maintain an ExecPlan following `.agent/PLANS.md`.

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

## Work Package selection and numbering

- A Work Package must deliver one capability an operator can observe in the
  running system or harness. Hardening, contract tests, validators, templates,
  runbooks, or docs for an existing capability belong to that capability's
  Work Package: they never mint a new WP number, runbook, release note, or
  Makefile target. Reopen the finished WP and extend it instead.
- Before allocating a WP number, check `workpacks/exec/` on `origin/farm-main`
  AND all open `feature/wp-*` branches; the next number is the maximum found
  plus one. The WP-9xx range is reserved for off-track tooling and process work.
- New tests go into existing discovery paths (`harness/tests/test_*.py`,
  frontend vitest under `src/`). Do not add a per-WP Makefile target; the
  discovery-based targets already run new test files.
- Repairing the harness, validation gates, or this guide is always in scope
  and needs no new WP number. If you find yourself working around a defect
  that a previous session also worked around, stop the feature task, add the
  defect to `docs/KNOWN_ISSUES.md`, fix it, then resume.
- A PR that completes or changes a milestone updates that ExecPlan's Progress
  and Outcomes sections in the same PR. Stale ExecPlans mislead the next session.

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

When a validation target is missing or broken, fixing it is part of the current
task (see Work Package selection and numbering). Never substitute a throwaway
local workaround for a broken shared gate without recording the defect in
`docs/KNOWN_ISSUES.md`.

Every PR must include:

- tests demonstrating the behavior,
- failure-path tests,
- migration and rollback notes,
- feature-flag default,
- changed contracts,
- logs/metrics needed to diagnose failure,
- and a statement that Bambuddy still starts.

## Merge policy

The operator has delegated routine merges (2026-07-02). A session may merge its
own PR into `farm-main` only when ALL of the following hold:

- The work is the current `workpacks/BACKLOG.md` item, a `docs/KNOWN_ISSUES.md`
  repair, or an operator-named task.
- `make verify-fast` and every focused target the PR claims are shown passing
  in the PR description.
- The diff contains NO: feature-flag default change, destructive or schema
  migration, change to physical actuation or safety-gate code
  (`swapmod_*`, `plate_change*`, `bed_automation*`, canary sequence files,
  `allow_real_*` handling), auth/permission weakening, new production
  dependency, or secrets.
- The PR description states which of these exclusions were checked.

A PR that touches ANY excluded category stays open as a draft PR and waits for
explicit operator approval in that session's channel. Never merge someone
else's open PR, and never bypass a failing gate to merge.

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
- Upstream-update integration PRs are always operator-approved; the Merge
  policy self-merge rule does not apply to them.
