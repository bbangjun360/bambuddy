# Harness Stack Cleanup

## Purpose

This runbook describes safe cleanup after WP-060 mock harness and dry-run work.
It is for local harness resources only. It must not be used to control real
printers, PrintFlow devices, ERPNext, Obico, production databases, or production
infrastructure.

## Safety Rules

- Confirm the active environment is the local harness before stopping anything.
- Preserve logs and artifacts before cleanup.
- Do not delete Docker volumes, databases, backups, or audit evidence without
  explicit human approval.
- Do not run production Compose projects, production kube contexts, or production
  service managers from this runbook.
- Do not remove images that may be shared by another local task unless the owner
  approves.
- Do not clean up real printer, PrintFlow, ERPNext, or Obico resources from this
  repo.

## Evidence to Preserve First

Preserve sanitized copies of:

- Test output.
- Harness health output.
- Mock PrintFlow scenario logs.
- Bambuddy logs relevant to state transitions.
- Metrics or dashboard snapshots if used.
- `git status --short` and `git diff --check` output.

Do not preserve `.env` files, tokens, real endpoints, serials, access codes, or
customer data in shared artifacts.

## Cleanup Levels

### Level 0: Evidence Only

Use this when another worker or parent integration may still need the harness.

- [ ] Collect and redact evidence.
- [ ] Leave containers, volumes, and images unchanged.
- [ ] Tell the parent integration owner that the stack is still running.

### Level 1: Soft Stop

Use this when the local harness is no longer needed but data should remain for
inspection.

- [ ] Confirm the Compose project name belongs to the local harness.
- [ ] Dry-run or inspect the stop target before running it.
- [ ] Stop harness containers without removing volumes.
- [ ] Re-check that no production context was targeted.

Repository targets such as `make harness-down` are acceptable only after the
operator confirms the target does not remove volumes for the selected harness
configuration.

### Level 2: Approved Data Removal

Use this only with explicit human approval. The approval record must name the
local project, volumes or databases, artifact retention location, and rollback
impact.

- [ ] Approval recorded.
- [ ] Evidence exported and redacted.
- [ ] Volume or database identifiers reviewed by a human.
- [ ] Removal command reviewed before execution.
- [ ] Post-cleanup state recorded.

Without this approval, do not run volume deletion, database reset, backup
deletion, or broad prune commands.

## Commands to Avoid Without Approval

Do not run destructive cleanup commands from memory. In particular, avoid:

- Compose commands that remove volumes.
- Docker volume removal or broad prune commands.
- Database drop, truncate, or reset commands.
- Git reset or checkout commands that discard local work.
- Any command that contacts real printer, PrintFlow, ERPNext, or Obico services.

If a cleanup target might remove persistent data, stop and ask the parent
integration owner for approval before running it.

## Handoff Note

When cleanup is complete, report:

- Cleanup level used.
- Whether containers were left running or stopped.
- Whether volumes were preserved.
- Where redacted evidence was stored.
- Any unresolved stop condition.
- Any approval required for further cleanup.
