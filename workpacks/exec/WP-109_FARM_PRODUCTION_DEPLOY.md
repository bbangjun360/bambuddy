# WP-109 Farm Production Deploy ExecPlan

# Purpose

Add the first production farm-layer deploy wiring around the existing Bambuddy
compose deployment so an operator can run local Prometheus, Grafana, and ntfy
without relying on the harness stack.

# Current Behavior

`docker-compose.yml` starts the upstream Bambuddy application only and still
defaults to `network_mode: host` on Linux. `deploy/` contains
`docker-entrypoint.sh` and `bambuddy.service`, but no production farm compose
stack. The only checked-in Prometheus and Grafana wiring lives under
`harness/docker-compose.observability.yml` and `harness/observability/`.

Observed baseline on 2026-07-02 KST:

- `make verify-fast` passed before edits with 174 harness tests, 2
  characterization tests, and the fast deterministic gate.
- Focused red test
  `python3 -m unittest harness.tests.test_farm_production_deploy` failed with
  five missing-file assertions for the new production deploy artifacts.

# Scope

In scope:

- `deploy/docker-compose.farm.yml` for Prometheus, Grafana, and ntfy.
- `deploy/.env.farm.example` with pinned image references and localhost ports.
- Prometheus scrape config for Bambuddy and ntfy.
- Grafana datasource, dashboard provider, and baseline dashboard.
- A production deploy runbook with validation, rollback, and deferred-work notes.
- Harness tests that validate config shape and secrets/safety exclusions.

Out of scope:

- Caddy TLS entry.
- Backup and restore drill.
- Physical printer, SwapMod, plate-change, bed-automation, or canary logic.
- Feature-flag default changes.
- Auth or permission weakening in Bambuddy.
- UI changes.

# Architecture Boundaries

Bambuddy remains the only service that may issue printer state-changing
commands. Prometheus and Grafana observe metrics only. ntfy is a local
notification endpoint and does not control printers. The new compose file does
not receive Bambu MQTT, FTPS, access-code, ERP, or customer credentials.

# Milestones

- [x] Confirm baseline and read the current BACKLOG 2 scope.
- [x] Add failing tests for missing production deploy observability artifacts.
- [x] Add deploy compose, env example, Prometheus, Grafana, ntfy config, and
      runbook.
- [x] Run focused and fast validation.
- [ ] Open PR and apply AGENTS.md merge policy.

# Progress

- [x] 2026-07-02 KST: Created isolated worktree
      `/tmp/bambuddy-farm-production-deploy` from `origin/farm-main`.
- [x] 2026-07-02 KST: Read latest `AGENTS.md`,
      `docs/00_PROJECT_CHARTER.md`, `docs/KNOWN_ISSUES.md`,
      `workpacks/BACKLOG.md`, relevant archived FULL_SPEC WP-01/WP-02 and
      acceptance sections, and `.agent/PLANS.md`.
- [x] 2026-07-02 KST: `make verify-fast` passed before edits.
- [x] 2026-07-02 KST: Added red config tests and verified they fail because the
      production deploy artifacts are missing.
- [x] 2026-07-02 KST: Added production farm compose overlay, pinned env
      example, Prometheus config, Grafana provisioning/dashboard, ntfy wiring,
      and the production deploy runbook.
- [x] 2026-07-02 KST: `python3 -m unittest harness.tests.test_farm_production_deploy` passed with 5 tests.
- [x] 2026-07-02 KST: `docker compose --project-directory . --env-file deploy/.env.farm.example -f docker-compose.yml -f deploy/docker-compose.farm.yml --profile farm-observability config --quiet` passed.
- [x] 2026-07-02 KST: `make verify-fast` passed after edits with 179 harness tests, 2 characterization tests, and the fast deterministic gate.
- [x] 2026-07-02 KST: `git diff --check` passed. Secret/scope scan hits were limited to test assertions, runbook warnings, the ExecPlan risk text, and the Grafana password env placeholder.

# Decisions

- Use a production compose overlay in `deploy/docker-compose.farm.yml` instead
  of modifying upstream `docker-compose.yml`, preserving upstream deploy
  behavior and keeping rollback file-level.
- Bind Prometheus, Grafana, and ntfy to `127.0.0.1` until Caddy TLS is added.
- Scrape Bambuddy through `host.docker.internal:8000` because upstream
  `docker-compose.yml` defaults Bambuddy to host networking on Linux.
- Keep ntfy anonymous read/write by default only because it is bound to
  localhost in this slice; the runbook documents the operator path for
  `deny-all` with out-of-band credentials.

# Harness Changes

Added `harness/tests/test_farm_production_deploy.py`, a discovery-based test
file under the existing harness target paths. It validates:

- production compose service names, image pin variables, localhost ports, and
  forbidden safety/secret strings;
- env example image digests and ports;
- Prometheus Bambuddy and ntfy scrape config without committed credentials;
- Grafana datasource and dashboard expressions;
- runbook and ExecPlan scope, validation, rollback, and deferred-work notes.

# Implementation

Create:

- `deploy/docker-compose.farm.yml`
- `deploy/.env.farm.example`
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
make verify-fast
git diff --check
```

Operational validation after copying `deploy/.env.farm.example` to a local
ignored `deploy/.env.farm`:

```bash
docker compose --project-directory . --env-file deploy/.env.farm \
  -f docker-compose.yml -f deploy/docker-compose.farm.yml \
  --profile farm-observability config
```

# Failure and Recovery

Rollback is file-level: remove the deploy compose overlay, production
observability config directory, runbook, ExecPlan, and harness test. Runtime
rollback is stopping and removing only `prometheus`, `grafana`, and `ntfy`
containers. Docker volume deletion is destructive and still requires explicit
human approval.

# Risks and Human Gates

This PR adds production dependencies for Prometheus, Grafana, and ntfy. Under
the AGENTS.md merge policy, that is an excluded self-merge category, so the PR
must remain draft until the operator explicitly approves it. It does not touch
physical actuation or safety-gate code, does not include migrations, and does
not commit secrets.

# Outcomes

Implemented the BACKLOG 2 first production deploy slice for Prometheus, Grafana, and ntfy. The stack is localhost-bound, uses pinned image references for the new services, provisions a baseline Grafana dashboard, and documents validation and rollback. Caddy TLS plus backup/restore drill remain explicitly deferred to the next session.

Validation evidence: focused production deploy test passed, Docker Compose config parsing passed with `deploy/.env.farm.example`, `make verify-fast` passed, and `git diff --check` passed. Because this adds production dependencies, the PR must remain draft until explicit operator approval under AGENTS.md merge policy.
