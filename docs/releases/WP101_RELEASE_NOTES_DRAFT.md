# WP-101 Release Notes Draft

## Release Scope

This draft covers the farm fork acceptance release after WP-000 through WP-100.
It packages the current read-only diagnostics and default-off farm integration
work into a release candidate without enabling new physical automation.

## Release Candidate

- Repository: `bbangjun360/bambuddy`
- Branch: `farm-main`
- WP-100 baseline commit: `d20e5f94b5c7f87ca3bed84501e39fd6f3849685`
- Candidate tag name after WP-101 acceptance passes: `farm-v0.1.0-acceptance`
- Final tag target: accepted `farm-main` merge commit after WP-101 post-merge
  checks pass.

## Validation Evidence

Required release evidence:

- `make test-release-readiness-acceptance`
- `make verify-fast`
- `make verify-full`, or a recorded environment blocker with narrower passing
  checks
- `python3 harness/scripts/check_workpack.py workpacks/exec/WP-101_RELEASE_READINESS_AND_ACCEPTANCE.md`
- `git diff --check`
- no-network Bambuddy app import smoke with `bambuddy_app_import_ok True`
- GitHub Actions `Validation` success
- GitHub Actions `Security Audit` success on `farm-main` after merge

## Changed Contracts

WP-000 through WP-100 introduced and hardened farm-facing contracts while
keeping automation disabled by default. The final WP-100 diagnostics status
contract advertises status version fields:

- `response_contract_version`
- `diagnostics_summary_contract_version`
- `blocked_reason_details_contract_version`

The diagnostics status response also advertises supported summary fields,
summary boolean fields, summary count fields, summary nullable fields, summary
collection fields, status boolean fields, and status string fields.

## Feature Flags

No feature flag defaults are changed by WP-101. Existing gates remain
default-off, including:

- `FARM_SWAPMOD_SCHEDULER_NEXT_PRINT_GATE_ENABLED=false`
- `FARM_SWAPMOD_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_SWAPMOD_SCHEDULER_QUEUE_READINESS_BINDING_ENABLED=false`
- `FARM_BED_AUTOMATION_ENABLED=false`

## Migration And Rollback

No database migration is part of WP-101. Rollback is redeploying the previous
accepted tag or merge commit and keeping physical automation gates disabled.
If bed or printer state is uncertain during rollback, stop and record
MANUAL_REVIEW.

## Hardware Test Position

WP-101 does not require a physical printer test because it adds release
readiness documentation and harness checks only. Hardware canary testing is
required before any later release enables physical printer, bed, actuator,
queue dispatch, or scheduler dispatch behavior.

## Known Risks

- Simulation success is not physical safety evidence.
- A release tag is not sufficient by itself; the operator must also verify the
  deployment environment and post-release monitoring gates.
- The acceptance release should not be promoted beyond controlled use if
  `Validation`, `Security Audit`, startup smoke, or diagnostics status checks
  fail.
