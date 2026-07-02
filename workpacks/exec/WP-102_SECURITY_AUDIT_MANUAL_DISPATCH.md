# WP-102 Security Audit Manual Dispatch

## ID and title

WP-102 Security Audit Manual Dispatch

## Observable outcome

The Security Audit workflow can be manually dispatched on `farm-main` for a
docs-only or harness-only release PR without failing because repository Issues
are disabled. Manual dispatch still runs Bandit, Trivy, pip-audit, and npm
audit and still uploads their artifacts and SARIF results.

## Why now

WP-101 merged after a passing PR `Validation` check, but its docs/harness-only
changes did not match the Security Audit push path filter. A manual
post-merge `Security Audit` run was dispatched on `farm-main` and failed in the
frontend issue-management step with `HttpError: Issues has been disabled in
this repository`. The audit checks themselves continued to run; the failure was
caused by issue creation on `workflow_dispatch`.

## Read these files

- `docs/00_PROJECT_CHARTER.md`
- `.github/workflows/security.yml`
- `harness/tests/test_security_workflow_dispatch_mock.py`

## In scope

- Keep manual `Security Audit` dispatch available.
- Restrict automatic creation or closure of pip and npm security issues to the
  scheduled weekly run.
- Add deterministic harness coverage for the workflow condition.
- Add `make test-security-workflow-dispatch`.

## Out of scope

- Runtime Bambuddy code.
- UI changes.
- Database migrations.
- Dependency updates.
- Vulnerability triage changes.
- Printer, bed, actuator, queue dispatch, scheduler dispatch, FTP, MQTT, raw
  G-code, ERP, Obico, or slicer execution.
- Enabling GitHub Issues in repository settings.

## Contract changes

No API or runtime contract changes are added. The repository validation
contract adds:

- `make test-security-workflow-dispatch`

The workflow behavior changes only for issue management:

- `workflow_dispatch` runs audit checks and artifact uploads.
- `schedule` runs audit checks, artifact uploads, and automated issue
  create-or-close steps.

## Harness first

`harness-security-workflow-dispatch` verifies that both pip and npm
`Create or close ... security issue` steps are guarded by
`always() && github.event_name == 'schedule'` and do not include
`workflow_dispatch`.

## Validation commands

- `python3 -m unittest harness.tests.test_security_workflow_dispatch_mock`
- `make test-security-workflow-dispatch`
- `make verify-fast`
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-102_SECURITY_AUDIT_MANUAL_DISPATCH.md`
- `git diff --check`
- Post-merge manual `gh workflow run security.yml --ref farm-main`

Evidence from this branch:

- RED check failed because both pip and npm issue-management steps included
  `workflow_dispatch`.
- GREEN check passed after both issue-management steps were restricted to
  `always() && github.event_name == 'schedule'` and artifact upload
  steps were verified to remain `if: always()`.
- `make test-security-workflow-dispatch COMPOSE_PROJECT_NAME=farm_wp030`
  passed.
- `make verify-fast COMPOSE_PROJECT_NAME=farm_wp030` passed with 134 harness
  tests and 2 characterization tests.
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-102_SECURITY_AUDIT_MANUAL_DISPATCH.md`
  passed.
- `git diff --check` passed.
- Placeholder scan for this workpack returned no matches.

## Manual demonstration

No physical printer test is required. This slice changes only a GitHub Actions
workflow condition and deterministic harness coverage.

## Migration and rollback

No migration is added. Rollback is restoring the prior `if:` condition on the
two security issue-management steps and removing the WP-102 harness target,
test, and workpack. Runtime behavior remains unchanged.

## Logs and metrics

No application logs or metrics are added. GitHub Actions remains the diagnostic
surface. Release operators should record the post-merge `Security Audit` run ID
and whether Bandit, Trivy, pip-audit, and npm audit jobs complete.

## Risks and human gates

This change stops manual dispatch from creating or closing security issues.
Scheduled weekly audits remain the only automated issue-management path. A
manual audit with vulnerabilities still preserves artifacts and SARIF uploads,
but repository owners must review the run if issues are disabled.

## Done when

- The focused security workflow dispatch target passes.
- `verify-fast`, workpack check, and diff check pass.
- PR `Validation` passes.
- The PR is merged to `farm-main`.
- A manual post-merge `Security Audit` run on `farm-main` passes.
