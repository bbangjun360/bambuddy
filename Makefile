.PHONY: harness-config harness-up harness-up-slicer harness-up-observability harness-down harness-reset harness-health \
        harness-persistence harness-backup harness-restore harness-orca-health harness-orca-slice \
        harness-observability-health harness-bed-automation harness-erp-draft-write harness-obico-shadow \
        harness-printflow-canary harness-plate-change-command \
        test-unit test-characterization test-contract test-integration test-scenario test-observability \
        test-erp-readonly test-erp-draft-write test-bed-automation test-obico-shadow test-printflow-canary test-plate-change-command \
        verify-fast verify-full context-check workpack-check hooks-check

HARNESS_ENV ?= .env.harness
-include $(HARNESS_ENV)
HARNESS_COMPOSE ?= harness/docker-compose.harness.yml
HARNESS_OBSERVABILITY_COMPOSE ?= harness/docker-compose.observability.yml
GIT_BRANCH ?= $(shell git branch --show-current 2>/dev/null || echo main)
COMPOSE = COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) GIT_BRANCH=$(GIT_BRANCH) docker compose --env-file $(HARNESS_ENV) -f $(HARNESS_COMPOSE)
COMPOSE_OBSERVABILITY = COMPOSE_PROJECT_NAME=$(COMPOSE_PROJECT_NAME) GIT_BRANCH=$(GIT_BRANCH) docker compose --env-file $(HARNESS_ENV) -f $(HARNESS_COMPOSE) -f $(HARNESS_OBSERVABILITY_COMPOSE)

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
	@test "$(COMPOSE_PROJECT_NAME)" = "farm_wp030"
	$(COMPOSE) down -v --remove-orphans

harness-health:
	python3 harness/scripts/smoke.py

harness-orca-health:
	python3 harness/scripts/orca_health.py

harness-orca-slice:
	python3 harness/scripts/orca_direct_slice.py

harness-observability-health:
	python3 harness/scripts/observability_health.py

harness-obico-shadow:
	FARM_OBICO_SHADOW_ENABLED=true $(COMPOSE) up -d --build postgres mock-services bambuddy
	python3 harness/scripts/obico_shadow.py

harness-printflow-canary:
	python3 -m unittest harness.tests.test_printflow_canary_readiness_mock

harness-plate-change-command:
	python3 -m unittest harness.tests.test_plate_change_command_mock

harness-bed-automation:
	python3 -m unittest harness.tests.test_bed_automation_mock

harness-erp-draft-write:
	python3 -m unittest harness.tests.test_erp_draft_write_mock

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

test-erp-readonly:
	python3 -m unittest harness.tests.test_mock_services
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp030-tests -e LOG_DIR=/tmp/bambuddy-wp030-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend/tests/unit/services/test_erp_readonly.py backend/tests/unit/test_erp_readonly_architecture.py backend/tests/integration/test_erp_readonly_api.py

test-erp-draft-write: harness-erp-draft-write
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp040-tests -e LOG_DIR=/tmp/bambuddy-wp040-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend/tests/unit/services/test_erp_draft_write.py backend/tests/unit/test_erp_draft_write_architecture.py backend/tests/integration/test_erp_draft_write_api.py

test-bed-automation: harness-bed-automation
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp050-bed-tests -e LOG_DIR=/tmp/bambuddy-wp050-bed-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m pytest -q -p no:cacheprovider backend/tests/unit/test_bed_automation_simulator.py backend/tests/unit/test_bed_automation_architecture.py

test-scenario:
	python3 -m unittest discover -s harness/tests -p 'scenario_*.py'

test-observability:
	python3 -m unittest discover -s harness/tests -p 'test_observability_*.py'

test-obico-shadow:
	python3 -m unittest backend.tests.unit.services.test_obico_shadow backend.tests.unit.test_obico_shadow_architecture harness.tests.test_obico_shadow_mock
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp070-tests -e LOG_DIR=/tmp/bambuddy-wp070-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.integration.test_obico_shadow_api

test-printflow-canary: harness-printflow-canary
	python3 -m unittest backend.tests.unit.services.test_printflow_canary backend.tests.unit.test_printflow_canary_architecture
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp060-tests -e LOG_DIR=/tmp/bambuddy-wp060-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.integration.test_printflow_canary_api

test-plate-change-command: harness-plate-change-command
	python3 -m unittest backend.tests.unit.services.test_plate_change_command backend.tests.unit.test_plate_change_command_architecture
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp063-tests -e LOG_DIR=/tmp/bambuddy-wp063-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.integration.test_plate_change_command_api

verify-fast: context-check workpack-check hooks-check test-contract test-unit test-characterization
	@echo "Fast deterministic gate passed."

verify-full: verify-fast test-unit test-characterization test-integration test-scenario
	@echo "Full gate passed."
