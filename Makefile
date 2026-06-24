.PHONY: harness-config harness-up harness-down harness-reset harness-health \
        test-unit test-characterization test-contract test-integration test-scenario \
        verify-fast verify-full context-check workpack-check hooks-check

HARNESS_ENV ?= .env.harness
HARNESS_COMPOSE ?= harness/docker-compose.harness.yml
COMPOSE = docker compose --env-file $(HARNESS_ENV) -f $(HARNESS_COMPOSE)

harness-config:
	$(COMPOSE) config >/dev/null

harness-up:
	$(COMPOSE) up -d --build postgres mock-services bambuddy

harness-down:
	$(COMPOSE) down --remove-orphans

harness-reset:
	@echo "This deletes only the isolated harness project volumes."
	@test "$${COMPOSE_PROJECT_NAME:-farm_harness}" != "production"
	$(COMPOSE) down -v --remove-orphans

harness-health:
	python3 harness/scripts/smoke.py

context-check:
	python3 harness/scripts/check_context_budget.py

workpack-check:
	python3 harness/scripts/check_workpack.py workpacks/WP-000_BASELINE_AND_HARNESS.md

hooks-check:
	python3 -m py_compile .codex/hooks/*.py

# WP-000 must replace these placeholders with the actual upstream commands.
test-unit:
	@echo "TODO WP-000: map to Bambuddy unit-test command" && exit 2

test-characterization:
	@echo "TODO WP-000: add baseline characterization target" && exit 2

test-contract:
	python3 -m unittest discover -s harness/tests -p 'test_*.py'

test-integration:
	python3 harness/scripts/smoke.py

test-scenario:
	python3 -m unittest discover -s harness/tests -p 'scenario_*.py'

verify-fast: context-check hooks-check test-contract
	@echo "Fast deterministic gate passed."

verify-full: verify-fast test-unit test-characterization test-integration test-scenario
	@echo "Full gate passed."
