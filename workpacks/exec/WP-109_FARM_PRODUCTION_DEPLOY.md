# WP-109 Farm Production Deploy ExecPlan

# Purpose

Add production farm-layer deploy wiring around the existing Bambuddy compose
deployment so an operator can run local Prometheus, Grafana, ntfy, Caddy local
TLS, and a guarded backup/restore drill without relying on the harness stack.

# Current Behavior

`docker-compose.yml` starts the upstream Bambuddy application and defaults to
`network_mode: host` on Linux. WP-109 PR #72 added
`deploy/docker-compose.farm.yml` for Prometheus, Grafana, and ntfy, plus
production observability config and a runbook. Before this continuation, Caddy
TLS and backup/restore drill were still explicitly deferred.

Observed baselines on 2026-07-02 KST:

- PR #72 merged to `farm-main` at `e90fcec2be3ca10be89a3c88d00323f19e15647d`.
- New continuation branch: `feature/wp-109-farm-production-caddy-backup`.
- `make verify-fast` passed before edits with 179 harness tests, 2
  characterization tests, and the fast deterministic gate.
- Focused red test `python3 -m unittest harness.tests.test_farm_production_deploy`
  failed on missing Caddy compose/env/config, missing backup drill script, and
  old deferred runbook text.

# Scope

In scope:

- Add Caddy service to `deploy/docker-compose.farm.yml` with local TLS entry for
  Bambuddy, Grafana, and ntfy.
- Add a backup bind mount for the existing Bambuddy service.
- Add `deploy/caddy/Caddyfile` with Caddy internal CA routing.
- Add `deploy/scripts/farm_backup_drill.py` with dry-run backup planning,
  explicit backup execution, and guarded restore-check validation.
- Update `deploy/.env.farm.example` with pinned Caddy image, hostnames, ports,
  and backup directory.
- Update the production deploy runbook and this ExecPlan.
- Extend harness tests to validate Caddy, backup mount, restore guards, and
  secrets/safety exclusions.

Out of scope:

- Public ACME certificates or internet exposure.
- ERPNext production deployment.
- Physical printer, SwapMod, plate-change, bed-automation, or canary logic.
- Feature-flag default changes.
- Auth or permission weakening in Bambuddy.
- UI changes.

# Architecture Boundaries

Bambuddy remains the only service that may issue printer state-changing
commands. Prometheus and Grafana observe metrics only. ntfy is a local
notification endpoint and does not control printers. Caddy is the local TLS
entry point for operator-facing HTTP services. The backup drill script does not
execute destructive restore commands against the live production stack.

# Milestones

- [x] Confirm baseline and read the current BACKLOG 2 scope.
- [x] Add failing tests for missing production deploy observability artifacts.
- [x] Add deploy compose, env example, Prometheus, Grafana, ntfy config, and
      runbook.
- [x] Merge PR #72 with operator approval because it added production
      dependencies.
- [x] Add failing tests for Caddy TLS and backup/restore drill completion.
- [x] Add Caddy compose/config, backup mount, backup drill script, runbook, and
      ExecPlan updates.
- [x] Run focused, compose, and fast validation.
- [ ] Open PR and apply AGENTS.md merge policy.

# Progress

- [x] 2026-07-02 KST: Created isolated worktree
      `/tmp/bambuddy-farm-production-deploy` from `origin/farm-main`.
- [x] 2026-07-02 KST: Read latest `AGENTS.md`,
      `docs/00_PROJECT_CHARTER.md`, `docs/KNOWN_ISSUES.md`,
      `workpacks/BACKLOG.md`, relevant archived FULL_SPEC WP-01/WP-02 and
      acceptance sections, and `.agent/PLANS.md`.
- [x] 2026-07-02 KST: `make verify-fast` passed before first WP-109 slice.
- [x] 2026-07-02 KST: Added production farm compose overlay, pinned env
      example, Prometheus config, Grafana provisioning/dashboard, ntfy wiring,
      production deploy runbook, and tests; PR #72 merged after operator
      approval.
- [x] 2026-07-02 KST: Read current AGENTS/charter/known issues/BACKLOG, archived
      TLS/backup/spec acceptance sections, `.agent/PLANS.md`, and this ExecPlan
      for the continuation.
- [x] 2026-07-02 KST: `make verify-fast` passed on
      `feature/wp-109-farm-production-caddy-backup` before continuation edits.
- [x] 2026-07-02 KST: Added red Caddy/backup drill tests; focused test failed
      with 12 assertion failures for missing Caddy service/env/config, missing
      backup drill script, and old deferred runbook text.
- [x] 2026-07-02 KST: Added Caddy service/config, backup bind mount, pinned
      Caddy env, guarded backup drill script, and updated runbook/ExecPlan.
- [x] 2026-07-02 KST: `python3 -m unittest harness.tests.test_farm_production_deploy` passed with 8 tests.
- [x] 2026-07-02 KST: `python3 -m py_compile deploy/scripts/farm_backup_drill.py` passed.
- [x] 2026-07-02 KST: `docker compose --project-directory . --env-file deploy/.env.farm.example -f docker-compose.yml -f deploy/docker-compose.farm.yml --profile farm-observability config --quiet` passed.
- [x] 2026-07-02 KST: `python3 deploy/scripts/farm_backup_drill.py backup --env-file deploy/.env.farm.example` passed as a DRY RUN and modified no production data.
- [x] 2026-07-02 KST: `python3 deploy/scripts/farm_backup_drill.py restore-check ... --confirm CONFIRM_FARM_PRODUCTION_RESTORE` passed against a synthetic `/tmp` backup file and printed isolated restore-drill steps.
- [x] 2026-07-02 KST: `make verify-fast` passed with 182 harness tests, 2 characterization tests, and the fast deterministic gate.
- [x] 2026-07-02 KST: `git diff --check` passed. Scope scan hits were limited to test assertions, runbook warnings, ExecPlan risk text, and the Grafana password env placeholder.

# Decisions

- Continue WP-109 instead of minting WP-110 because Caddy and backup/restore
  complete the same BACKLOG 2 Farm production deploy capability.
- Use a production compose overlay instead of modifying upstream
  `docker-compose.yml`, preserving upstream deploy behavior and keeping rollback
  file-level.
- Bind Prometheus/Grafana/ntfy direct ports to loopback, while Caddy owns the
  operator-facing TLS hostnames.
- Use Caddy `tls internal` for LAN-first local TLS; public ACME certificates are
  out of scope.
- Keep restore execution human-gated and outside the live production stack. The
  script validates backup selection and prints restore-drill steps, but it does
  not run destructive restore commands.

# Harness Changes

`harness/tests/test_farm_production_deploy.py` validates:

- production compose service names, image pin variables, Caddy ports, backup
  mount, localhost observability ports, and forbidden safety/secret strings;
- env example image digests, Caddy hostnames, and backup path;
- Caddyfile hostnames, internal TLS, reverse proxy targets, and no Prometheus
  exposure through Caddy;
- Prometheus Bambuddy and ntfy scrape config without committed credentials;
- Grafana datasource and dashboard expressions;
- backup drill script dry-run defaults and restore confirmation/path guards;
- runbook and ExecPlan scope, validation, rollback, and completion notes.

# Implementation

Create or modify:

- `deploy/docker-compose.farm.yml`
- `deploy/.env.farm.example`
- `deploy/caddy/Caddyfile`
- `deploy/scripts/farm_backup_drill.py`
- `deploy/observability/prometheus/prometheus.yml`
- `deploy/observability/grafana/provisioning/datasources/prometheus.yml`
- `deploy/observability/grafana/provisioning/dashboards/dashboards.yml`
- `deploy/observability/grafana/dashboards/farm-production.json`
- `docs/runbooks/FARM_PRODUCTION_DEPLOY.md`
- `workpacks/exec/WP-109_FARM_PRODUCTION_DEPLOY.md`
- `harness/tests/test_farm_production_deploy.py`

# Validation

Required commands:

```bash
python3 -m unittest harness.tests.test_farm_production_deploy
python3 -m py_compile deploy/scripts/farm_backup_drill.py
docker compose --project-directory . --env-file deploy/.env.farm.example   -f docker-compose.yml -f deploy/docker-compose.farm.yml   --profile farm-observability config --quiet
make verify-fast
git diff --check
```

Operational validation after copying `deploy/.env.farm.example` to a local
ignored `deploy/.env.farm`:

```bash
docker compose --project-directory . --env-file deploy/.env.farm   -f docker-compose.yml -f deploy/docker-compose.farm.yml   --profile farm-observability up -d bambuddy prometheus grafana ntfy caddy
```

# Failure and Recovery

Rollback is file-level: remove the deploy compose overlay, Caddy config,
production observability config directory, backup drill script, runbook,
ExecPlan, and harness test. Runtime rollback is stopping and removing only
`caddy`, `prometheus`, `grafana`, and `ntfy` containers. Docker volume deletion,
backup deletion, database restore, or Caddy CA deletion is destructive and still
requires explicit human approval.

# Risks and Human Gates

This PR adds/extends production dependencies for Caddy plus previously merged
Prometheus, Grafana, and ntfy. Under the AGENTS.md merge policy, new production
dependency remains an excluded self-merge category, so the PR must remain draft
until the operator explicitly approves it. It does not touch physical actuation
or safety-gate code, does not include migrations, and does not commit secrets.

# Outcomes

Implemented the remaining BACKLOG 2 Farm production deploy scope: Caddy local TLS entry, backup mount, and a guarded backup/restore drill story on top of the previously merged Prometheus, Grafana, and ntfy production wiring. The deploy stack now has pinned image references, Caddy internal-CA routing for operator surfaces, localhost-only direct observability ports, a host backup mount, and restore-check guards that do not execute destructive commands against the live production stack.

Validation evidence: focused production deploy tests passed, backup drill script compilation passed, Docker Compose config parsing passed with `deploy/.env.farm.example`, backup dry-run passed without modifying production data, restore-check validation passed against a synthetic `/tmp` backup file, `make verify-fast` passed, and `git diff --check` passed. Because this extends production dependencies with Caddy, the PR must remain draft until explicit operator approval under AGENTS.md merge policy.
