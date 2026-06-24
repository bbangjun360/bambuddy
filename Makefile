.PHONY: harness-config harness-up harness-up-slicer harness-up-observability harness-down harness-reset harness-health \
        harness-persistence harness-backup harness-restore harness-orca-health harness-orca-slice \
        harness-observability-health test-unit test-characterization test-contract test-integration \
        test-scenario test-observability verify-fast verify-full context-check workpack-check hooks-check

HARNESS_ENV ?= .env.harness
HARNESS_COMPOSE ?= harness/docker-compose.harness.yml
HARNESS_OBSERVABILITY_COMPOSE ?= harness/docker-compose.observability.yml
COMPOSE = COMPOSE_PROJECT_NAME=farm_harness docker compose --env-file $(HARNESS_ENV) -f $(HARNESS_COMPOSE)
COMPOSE_OBSERVABILITY = COMPOSE_PROJECT_NAME=farm_harness docker compose --env-file $(HARNESS_ENV) -f $(HARNESS_COMPOSE) -f $(HARNESS_OBSERVABILITY_COMPOSE)

harness-config:
	$(COMPOSE) config >/dev/null

harness-up:
	$(COMPOSE) up -d --build postgres mock-services bambuddy

harness-up-slicer:
	$(COMPOSE) --profile slicer up -d --build postgres mock-services orca-slicer-api bambuddy

harness-up-observability:
	$(COMPOSE_OBSERVABILITY) --profile slicer --profile observability up -d --build postgres mock-services orca-slicer-api bambuddy harness-observer prometheus grafana

harness-down:
	$(COMPOSE) down --remove-orphans

harness-reset:
	@echo "This deletes only the isolated harness project volumes."
	@test "$${COMPOSE_PROJECT_NAME:-farm_harness}" = "farm_harness"
	$(COMPOSE) down -v --remove-orphans

harness-health:
	python3 harness/scripts/smoke.py

harness-orca-health:
	python3 harness/scripts/orca_health.py

harness-orca-slice:
	python3 harness/scripts/orca_direct_slice.py

harness-observability-health:
	python3 harness/scripts/observability_health.py

harness-persistence:
	python3 harness/scripts/persistence.py

harness-backup:
	python3 harness/scripts/backup_restore.py

harness-restore: harness-backup

context-check:
	python3 harness/scripts/check_context_budget.py

workpack-check:
	python3 harness/scripts/check_workpack.py workpacks/WP-000_BASELINE_AND_HARNESS.md

hooks-check:
	python3 -m py_compile .codex/hooks/*.py

test-unit:
	python3 -m py_compile backend/app/main.py backend/app/core/config.py backend/app/core/database.py
	python3 -m unittest discover -s harness/tests -p 'test_*.py'

test-characterization:
	python3 -m unittest discover -s harness/tests -p 'characterization_*.py'

test-contract:
	python3 -m unittest discover -s harness/tests -p 'test_*.py'

test-integration:
	python3 harness/scripts/smoke.py

test-scenario:
	python3 -m unittest discover -s harness/tests -p 'scenario_*.py'

test-observability:
	python3 -m unittest discover -s harness/tests -p 'test_observability_*.py'

verify-fast: context-check workpack-check hooks-check test-contract test-unit test-characterization
	@echo "Fast deterministic gate passed."

verify-full: verify-fast test-unit test-characterization test-integration test-scenario
	@echo "Full gate passed."
