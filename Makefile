.PHONY: harness-config harness-up harness-up-slicer harness-up-observability harness-down harness-reset harness-health \
        harness-persistence harness-backup harness-restore harness-orca-health harness-orca-slice \
        harness-observability-health harness-bed-automation harness-erp-draft-write harness-obico-shadow \
        harness-printflow-canary harness-plate-change-command harness-plate-change-transport harness-plate-change-3mf-postprocess \
        harness-plate-change-3mf-physical-canary harness-swapmod-3mf-dry-run harness-swapmod-canary-preflight \
        harness-swapmod-state-machine harness-swapmod-operator-trigger harness-swapmod-verification-adapter harness-swapmod-transport-boundary \
        harness-swapmod-canary-execution-gate harness-swapmod-a1mini-direct-canary harness-swapmod-bed-readiness harness-swapmod-next-print-gate harness-swapmod-scheduler-next-print-gate harness-swapmod-queue-readiness-binding harness-swapmod-scheduler-queue-readiness-binding harness-swapmod-scheduler-handoff-chain harness-swapmod-scheduler-consumed-handoff-retry \
        test-unit test-characterization test-contract test-integration test-scenario test-observability \
        test-erp-readonly test-erp-draft-write test-bed-automation test-obico-shadow test-printflow-canary test-plate-change-command test-plate-change-transport test-plate-change-3mf-postprocess test-plate-change-3mf-physical-canary test-plate-change-3mf-insertion test-swapmod-3mf-dry-run test-swapmod-canary-preflight \
        test-swapmod-state-machine test-swapmod-operator-trigger test-swapmod-verification-adapter test-swapmod-transport-boundary \
        test-swapmod-canary-execution-gate test-swapmod-a1mini-direct-canary test-swapmod-bed-readiness test-swapmod-next-print-gate test-swapmod-scheduler-next-print-gate test-swapmod-queue-readiness-binding test-swapmod-scheduler-queue-readiness-binding test-swapmod-scheduler-handoff-chain test-swapmod-scheduler-consumed-handoff-retry \
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

harness-plate-change-transport:
	python3 -m unittest harness.tests.test_plate_change_command_mock

harness-plate-change-3mf-postprocess:
	python3 -m unittest harness.tests.test_plate_change_3mf_postprocess_mock

harness-plate-change-3mf-physical-canary:
	python3 -m unittest harness.tests.test_plate_change_3mf_physical_canary_mock

harness-swapmod-3mf-dry-run:
	python3 -m unittest harness.tests.test_swapmod_3mf_dry_run_mock

harness-swapmod-canary-preflight:
	python3 -m unittest harness.tests.test_swapmod_canary_preflight_mock

harness-swapmod-state-machine:
	python3 -m unittest harness.tests.test_swapmod_state_machine_mock

harness-swapmod-operator-trigger:
	python3 -m unittest harness.tests.test_swapmod_state_machine_mock

harness-swapmod-verification-adapter:
	python3 -m unittest harness.tests.test_swapmod_state_machine_mock

harness-swapmod-transport-boundary:
	python3 -m unittest harness.tests.test_swapmod_state_machine_mock

harness-swapmod-canary-execution-gate:
	python3 -m unittest harness.tests.test_swapmod_state_machine_mock

harness-swapmod-a1mini-direct-canary:
	python3 -m unittest harness.tests.test_swapmod_state_machine_mock

harness-swapmod-bed-readiness:
	python3 -m unittest harness.tests.test_swapmod_bed_readiness_mock

harness-swapmod-next-print-gate:
	python3 -m unittest harness.tests.test_swapmod_next_print_gate_mock

harness-swapmod-scheduler-next-print-gate:
	python3 -m unittest harness.tests.test_swapmod_scheduler_next_print_gate_mock

harness-swapmod-queue-readiness-binding:
	python3 -m unittest harness.tests.test_swapmod_queue_readiness_binding_mock

harness-swapmod-scheduler-queue-readiness-binding:
	python3 -m unittest harness.tests.test_swapmod_scheduler_queue_readiness_binding_mock

harness-swapmod-scheduler-handoff-chain:
	python3 -m unittest harness.tests.test_swapmod_scheduler_handoff_chain_mock

harness-swapmod-scheduler-consumed-handoff-retry:
	python3 -m unittest harness.tests.test_swapmod_scheduler_consumed_handoff_retry_mock

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

test-plate-change-transport: harness-plate-change-transport
	python3 -m unittest backend.tests.unit.services.test_plate_change_command backend.tests.unit.test_plate_change_command_architecture
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp063-transport-tests -e LOG_DIR=/tmp/bambuddy-wp063-transport-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.integration.test_plate_change_command_api

test-plate-change-3mf-postprocess: harness-plate-change-3mf-postprocess
	python3 -m unittest backend.tests.unit.services.test_plate_change_3mf_postprocess backend.tests.unit.test_plate_change_3mf_postprocess_architecture
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp064-tests -e LOG_DIR=/tmp/bambuddy-wp064-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.integration.test_plate_change_3mf_postprocess_api

test-plate-change-3mf-physical-canary: harness-plate-change-3mf-physical-canary
	python3 -m unittest backend.tests.unit.services.test_plate_change_3mf_physical_canary backend.tests.unit.test_plate_change_3mf_physical_canary_architecture
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp064d-tests -e LOG_DIR=/tmp/bambuddy-wp064d-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.integration.test_plate_change_3mf_physical_canary_api

test-swapmod-3mf-dry-run: harness-swapmod-3mf-dry-run
	python3 -m unittest backend.tests.unit.services.test_swapmod_3mf_dry_run backend.tests.unit.test_swapmod_3mf_dry_run_architecture
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp065-tests -e LOG_DIR=/tmp/bambuddy-wp065-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.integration.test_swapmod_3mf_dry_run_api

test-swapmod-canary-preflight: harness-swapmod-canary-preflight
	python3 -m unittest backend.tests.unit.services.test_swapmod_canary_preflight backend.tests.unit.test_swapmod_canary_preflight_architecture
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp066-tests -e LOG_DIR=/tmp/bambuddy-wp066-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.integration.test_swapmod_canary_preflight_api

test-swapmod-state-machine: harness-swapmod-state-machine
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-state-machine-tests -e LOG_DIR=/tmp/bambuddy-swapmod-state-machine-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_state_machine backend.tests.unit.test_swapmod_state_machine_architecture backend.tests.integration.test_swapmod_state_machine_api

test-swapmod-operator-trigger: harness-swapmod-operator-trigger
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-operator-trigger-tests -e LOG_DIR=/tmp/bambuddy-swapmod-operator-trigger-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_state_machine backend.tests.unit.test_swapmod_state_machine_architecture backend.tests.integration.test_swapmod_state_machine_api

test-swapmod-verification-adapter: harness-swapmod-verification-adapter
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-verification-adapter-tests -e LOG_DIR=/tmp/bambuddy-swapmod-verification-adapter-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_state_machine backend.tests.unit.test_swapmod_state_machine_architecture backend.tests.integration.test_swapmod_state_machine_api

test-swapmod-transport-boundary: harness-swapmod-transport-boundary
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-transport-boundary-tests -e LOG_DIR=/tmp/bambuddy-swapmod-transport-boundary-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_state_machine backend.tests.unit.test_swapmod_state_machine_architecture backend.tests.integration.test_swapmod_state_machine_api

test-swapmod-canary-execution-gate: harness-swapmod-canary-execution-gate
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-canary-execution-gate-tests -e LOG_DIR=/tmp/bambuddy-swapmod-canary-execution-gate-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_state_machine backend.tests.unit.test_swapmod_state_machine_architecture backend.tests.integration.test_swapmod_state_machine_api

test-swapmod-a1mini-direct-canary: harness-swapmod-a1mini-direct-canary
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-a1mini-direct-canary-tests -e LOG_DIR=/tmp/bambuddy-swapmod-a1mini-direct-canary-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_a1mini_direct_canary backend.tests.unit.test_swapmod_a1mini_direct_canary_architecture backend.tests.integration.test_swapmod_a1mini_direct_canary_api

test-swapmod-bed-readiness: harness-swapmod-bed-readiness
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-bed-readiness-tests -e LOG_DIR=/tmp/bambuddy-swapmod-bed-readiness-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_bed_readiness backend.tests.unit.test_swapmod_bed_readiness_architecture backend.tests.integration.test_swapmod_bed_readiness_api

test-swapmod-next-print-gate: harness-swapmod-next-print-gate
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-next-print-gate-tests -e LOG_DIR=/tmp/bambuddy-swapmod-next-print-gate-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_next_print_gate backend.tests.unit.test_swapmod_next_print_gate_architecture backend.tests.integration.test_swapmod_next_print_gate_api

test-swapmod-scheduler-next-print-gate: harness-swapmod-scheduler-next-print-gate
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-scheduler-next-print-gate-tests -e LOG_DIR=/tmp/bambuddy-swapmod-scheduler-next-print-gate-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_scheduler_next_print_gate backend.tests.unit.test_swapmod_scheduler_next_print_gate_architecture

test-swapmod-queue-readiness-binding: harness-swapmod-queue-readiness-binding
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-queue-readiness-binding-tests -e LOG_DIR=/tmp/bambuddy-swapmod-queue-readiness-binding-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_queue_readiness_binding backend.tests.unit.test_swapmod_queue_readiness_binding_architecture backend.tests.integration.test_swapmod_queue_readiness_binding_api

test-swapmod-scheduler-queue-readiness-binding: harness-swapmod-scheduler-queue-readiness-binding
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-scheduler-queue-readiness-binding-tests -e LOG_DIR=/tmp/bambuddy-swapmod-scheduler-queue-readiness-binding-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_scheduler_queue_readiness_binding backend.tests.unit.test_swapmod_scheduler_queue_readiness_binding_architecture

test-swapmod-scheduler-handoff-chain: harness-swapmod-scheduler-handoff-chain
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-scheduler-handoff-chain-tests -e LOG_DIR=/tmp/bambuddy-swapmod-scheduler-handoff-chain-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_scheduler_handoff_chain backend.tests.unit.test_swapmod_scheduler_handoff_chain_architecture

test-swapmod-scheduler-consumed-handoff-retry: harness-swapmod-scheduler-consumed-handoff-retry
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-swapmod-scheduler-consumed-handoff-retry-tests -e LOG_DIR=/tmp/bambuddy-swapmod-scheduler-consumed-handoff-retry-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(CURDIR):/workspace:ro -w /workspace --entrypoint python $(COMPOSE_PROJECT_NAME)-bambuddy:latest -m unittest backend.tests.unit.services.test_swapmod_scheduler_consumed_handoff_retry backend.tests.unit.test_swapmod_scheduler_consumed_handoff_retry_architecture

test-plate-change-3mf-insertion:
	python3 -m unittest \
		backend.tests.unit.services.test_plate_change_3mf_postprocess.PlateChange3mfPostprocessServiceTest.test_deterministic_insertion_produces_same_output_hash_for_same_input \
		backend.tests.unit.services.test_plate_change_3mf_postprocess.PlateChange3mfPostprocessServiceTest.test_insertion_marker_appears_exactly_once \
		backend.tests.unit.services.test_plate_change_3mf_postprocess.PlateChange3mfPostprocessServiceTest.test_only_target_internal_gcode_member_changes_and_others_are_byte_preserved \
		backend.tests.unit.services.test_plate_change_3mf_postprocess.PlateChange3mfPostprocessServiceTest.test_unknown_or_unsupported_3mf_structure_returns_safe_blocked_result \
		backend.tests.unit.services.test_plate_change_3mf_postprocess.PlateChange3mfPostprocessServiceTest.test_real_sample_output_review_blocked_by_default_config \
		backend.tests.unit.services.test_plate_change_3mf_postprocess.PlateChange3mfPostprocessServiceTest.test_real_sample_output_review_requires_all_explicit_flags \
		backend.tests.unit.services.test_plate_change_3mf_postprocess.PlateChange3mfPostprocessServiceTest.test_real_sample_input_must_be_under_sample_root \
		backend.tests.unit.services.test_plate_change_3mf_postprocess.PlateChange3mfPostprocessServiceTest.test_real_sample_output_must_be_under_output_root \
		backend.tests.unit.services.test_plate_change_3mf_postprocess.PlateChange3mfPostprocessServiceTest.test_real_sample_output_blocks_repo_path_output \
		backend.tests.unit.services.test_plate_change_3mf_postprocess.PlateChange3mfPostprocessServiceTest.test_real_sample_output_review_manifest_only_returns_required_metadata

verify-fast: context-check workpack-check hooks-check test-contract test-unit test-characterization
	@echo "Fast deterministic gate passed."

verify-full: verify-fast test-unit test-characterization test-integration test-scenario
	@echo "Full gate passed."
