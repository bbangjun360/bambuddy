# Release Readiness Acceptance

## Purpose

This runbook defines the acceptance and release gates for the Bambuddy farm
fork after WP-100. It turns a green development branch into an explicit release
candidate decision without enabling new automation by default.

No physical printer action is executed by this checklist. Hardware work remains
a separate named canary activity with a present operator, visible printer,
ready emergency stop, ready power cutoff, and a reviewed dry-run gate.

## Release Candidate Identity

Record the release candidate before tagging or deployment:

- Repository: `bbangjun360/bambuddy`
- Branch: `farm-main`
- WP-100 baseline commit: `d20e5f94b5c7f87ca3bed84501e39fd6f3849685`
- Final release tag target: the accepted `farm-main` merge commit after the
  release readiness PR is merged and post-merge checks pass.
- Release tag form: `farm-v0.1.0-acceptance`

The candidate is not accepted until the code, CI, contract, safety, data,
rollback, and monitoring gates below are satisfied.

## Code And CI Acceptance

Required evidence:

- `make verify-fast` passes on the release candidate.
- `make verify-full` is attempted before tagging. If it cannot run in the local
  environment, the release decision must record the exact blocker and the
  narrower commands that did pass.
- GitHub Actions `Validation` passes for the release candidate branch or PR.
- GitHub Actions `Security Audit` passes on `farm-main` after the release PR is
  merged.
- A no-network Bambuddy app import smoke passes with `bambuddy_app_import_ok True`.
- There are no open PRs targeting `farm-main` that are part of this release.

A failing required check blocks the release. Do not tag around a failing check.

## Contract Acceptance

Required evidence:

- The diagnostics status response documents its supported summary boolean,
  count, nullable, collection, status boolean, status string, and status version
  field lists.
- The diagnostics status handler remains read-only and DB-free beyond shared
  authentication dependencies.
- The status route still requires `PRINTERS_READ` and does not require
  `PRINTERS_CONTROL`.
- No new endpoint exposes raw G-code, arbitrary command, scheduler dispatch,
  queue mutation, printer command, actuator, MQTT, FTP, ERP, Obico, or slicer
  control.
- Default-off automation gates remain disabled unless a later hardware canary
  WP explicitly changes them.

Bambuddy remains the sole authority for printer state-changing commands.
OrcaSlicer only slices. ERPNext never controls a printer. External modules do
not connect directly to Bambu MQTT or FTPS.

## Safety And Data Acceptance

Required evidence:

- Test fixtures do not contain production printer credentials, access codes,
  ERP tokens, API keys, customer data, serial numbers, or personal information.
- Runtime behavior does not start the next print until bed state is verified
  READY.
- Uncertain physical state becomes MANUAL_REVIEW.
- Never automatically resume an uncertain physical bed action after restart.
- ERP inventory and accounting writes remain idempotent and Draft-only until a
  later release explicitly changes that gate.
- Failed and reprinted runs retain separate history and cost records.
- Rollback instructions identify the exact tag or merge commit to redeploy.

Simulation success is not physical safety evidence.

## Hardware Canary Acceptance

Hardware canary testing is required only when the release turns on or changes
physical printer, bed, transport, queue dispatch, or actuator behavior. WP-101
itself does not do that.

If a later release requires hardware canary testing, all of these gates must be
true before any action:

- Named canary printer and device are selected.
- Operator is present.
- Printer is visible.
- Emergency stop is ready.
- Power cutoff is ready.
- Bed area is clear.
- Plate stack and current plate state are manually verified.
- No other job is running.
- Dry-run gate has been reviewed.
- The operator provides the exact approval phrase required by the canary WP.

If any gate is uncertain, stop and record MANUAL_REVIEW. Do not retry the
physical action automatically.

## Release Tagging

Tag only after all required acceptance gates pass:

```bash
git fetch origin farm-main
git rev-parse origin/farm-main
git tag -a farm-v0.1.0-acceptance origin/farm-main -m "farm v0.1.0 acceptance"
git push origin farm-v0.1.0-acceptance
```

Before pushing a tag, verify that `origin/farm-main` is the accepted merge
commit and that post-merge `Security Audit` is successful.

## Rollback

Rollback uses the last accepted release tag or merge commit:

```bash
git fetch origin --tags
git rev-parse farm-v0.1.0-acceptance
```

Operational rollback must keep automation gates default-off unless a human
explicitly chooses a later canary-tested release. If a physical state is
uncertain during rollback, stop and record MANUAL_REVIEW.

## Post-Release Monitoring

After deployment, verify:

- Bambuddy starts.
- The diagnostics status endpoint returns the expected read-only contract
  metadata.
- Queue, scheduler dispatch, printer command, bed actuator, MQTT, FTP, ERP,
  Obico, and slicer boundaries remain closed unless explicitly enabled by a
  later accepted release.
- Logs show no startup errors.
- Operators can find rollback instructions and canary stop conditions.

A monitoring failure blocks promotion beyond acceptance use.
