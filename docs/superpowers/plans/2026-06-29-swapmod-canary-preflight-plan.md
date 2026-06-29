# SwapMod Canary Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build WP-066: a default-off SwapMod canary preflight workflow that packages one reviewed WP-065 dry-run candidate for human canary review without executing printer commands.

**Architecture:** Add a focused `swapmod_canary_preflight` schema, service, and route under the existing plate-change 3MF API area. The service accepts only redacted WP-065 response data, validates one candidate id, A1 Mini scope, checklist truth, and the exact confirmation phrase, then returns redacted package evidence with zero side-effect sentinels.

**Tech Stack:** FastAPI routes, Pydantic v2 schemas, Python `unittest`, existing Bambuddy settings and Makefile harness patterns.

---

## Current Constraint

The local `.git` object database is corrupt: `HEAD` points at a zero-byte loose object and `git status` fails. Do not run destructive Git repair. Implementation can continue with file edits, but commit/status evidence must be deferred until the repo is repaired from `origin/farm-main` or a clean clone.

## File Structure

- Create `backend/app/schemas/swapmod_canary_preflight.py` for strict package request and checklist schemas.
- Create `backend/app/services/swapmod_canary_preflight.py` for pure preflight validation and redacted package generation.
- Create `backend/app/api/routes/swapmod_canary_preflight.py` for status/package endpoints.
- Modify `backend/app/core/config.py` with default-off WP-066 config.
- Modify `backend/app/main.py` to include the new router.
- Modify `Makefile` with `harness-swapmod-canary-preflight` and `test-swapmod-canary-preflight`.
- Create focused tests under `backend/tests/unit/services/`, `backend/tests/unit/`, `backend/tests/integration/`, and `harness/tests/`.
- Create `docs/architecture/WP066_SWAPMOD_CANARY_PREFLIGHT.md` and `docs/runbooks/WP066_SWAPMOD_CANARY_PREFLIGHT.md`.
- Update `workpacks/exec/WP-066.md` with plan, harness changes, implementation, validation evidence, and outcomes.

### Task 1: RED Harness Contract

**Files:**
- Create: `harness/tests/test_swapmod_canary_preflight_mock.py`
- Modify later: `Makefile`

- [ ] **Step 1: Write the failing harness test**

```python
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SwapmodCanaryPreflightHarnessContractTest(unittest.TestCase):
    def test_makefile_exposes_swapmod_canary_preflight_targets(self) -> None:
        makefile = (ROOT / "Makefile").read_text()
        self.assertIn("harness-swapmod-canary-preflight:", makefile)
        self.assertIn("test-swapmod-canary-preflight: harness-swapmod-canary-preflight", makefile)

    def test_mock_services_do_not_expose_swapmod_canary_hardware_routes(self) -> None:
        text = (ROOT / "harness/mock_services.py").read_text()
        forbidden = [
            "/swapmod/v1/send-gcode",
            "/swapmod/v1/raw-command",
            "/swapmod/v1/start-next-print",
            "/swapmod-canary/v1/upload",
            "/swapmod-canary/v1/start",
            "swapmod_canary_printer_commands",
            "swapmod_canary_queue_dispatches",
        ]
        for needle in forbidden:
            self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest harness.tests.test_swapmod_canary_preflight_mock`

Expected: FAIL because `Makefile` does not expose the WP-066 targets.

### Task 2: RED Service Tests

**Files:**
- Create: `backend/tests/unit/services/test_swapmod_canary_preflight.py`
- Create later: `backend/app/services/swapmod_canary_preflight.py`

- [ ] **Step 1: Write service behavior tests**

Use helpers that build a redacted WP-065-like plan:

```python
from __future__ import annotations

import json
import unittest

from backend.app.services.swapmod_canary_preflight import SwapmodCanaryPreflightService


CHECKLIST = {
    "operator_present": True,
    "printer_visible": True,
    "emergency_stop_ready": True,
    "power_cutoff_ready": True,
    "bed_clear_confirmed": True,
    "correct_plate_confirmed": True,
    "no_other_job_running": True,
    "swapmod_hardware_installed": True,
    "plate_stack_loaded": True,
    "original_print_finished": True,
    "bed_state_reviewed": True,
}


def dry_run_plan(status: str = "SWAPMOD_DRY_RUN_READY") -> dict[str, object]:
    line_range_hash = "a" * 64
    return {
        "status": status,
        "mode": "DRY_RUN_ONLY",
        "expected_printer_model_family": "A1 Mini",
        "candidate_blocks": [
            {
                "candidate_id": "swapmod:inter_job_swap:aaaaaaaaaaaa",
                "candidate_kind": "inter_job_swap",
                "line_count": 42,
                "line_range_hash": line_range_hash,
                "command_family_counts": {"G1": 12, "G4": 4},
                "review_required": True,
                "raw_gcode_included": False,
                "real_execution_supported": False,
            }
        ],
        "sentinels": {"printer_commands": 0, "queue_dispatches": 0},
    }


class SwapmodCanaryPreflightServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = SwapmodCanaryPreflightService()

    def request(self, **overrides: object) -> dict[str, object]:
        plan = dry_run_plan()
        candidate = plan["candidate_blocks"][0]
        body: dict[str, object] = {
            "dry_run_plan": plan,
            "candidate_id": candidate["candidate_id"],
            "target_printer_id": "101",
            "expected_printer_model_family": "A1 Mini",
            "checklist": dict(CHECKLIST),
            "operator_confirmation_phrase": (
                f"CONFIRM_SWAPMOD_CANARY_PREFLIGHT 101 {candidate['candidate_id']} "
                f"{candidate['line_range_hash']}"
            ),
        }
        body.update(overrides)
        return body

    def test_status_is_default_disabled_and_preflight_only(self) -> None:
        status = self.service.status_snapshot(enabled=False)

        self.assertFalse(status["enabled"])
        self.assertEqual(status["mode"], "CANARY_PREFLIGHT_ONLY")
        self.assertFalse(status["real_execution_supported"])
        self.assertFalse(status["printer_command_supported"])
        self.assertTrue(all(value == 0 for value in status["sentinels"].values()))

    def test_ready_package_returns_redacted_candidate_and_zero_sentinels(self) -> None:
        result = self.service.create_package(self.request(), enabled=True)

        self.assertEqual(result["status"], "SWAPMOD_CANARY_PREFLIGHT_READY")
        self.assertEqual(result["target_printer_id"], "101")
        self.assertEqual(result["selected_candidate"]["candidate_kind"], "inter_job_swap")
        self.assertFalse(result["real_execution_supported"])
        self.assertFalse(result["printer_command_supported"])
        self.assertFalse(result["printer_upload_supported"])
        self.assertFalse(result["printer_start_supported"])
        self.assertTrue(all(value == 0 for value in result["sentinels"].values()))
        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("G1 ", rendered)
        self.assertNotIn("access_code", rendered)

    def test_non_ready_plan_candidate_mismatch_non_a1_and_bad_phrase_require_review(self) -> None:
        cases = [
            self.request(dry_run_plan=dry_run_plan(status="SWAPMOD_DRY_RUN_REVIEW_REQUIRED")),
            self.request(candidate_id="missing-candidate"),
            self.request(expected_printer_model_family="A1"),
            self.request(operator_confirmation_phrase="CONFIRM_SWAPMOD_CANARY_PREFLIGHT wrong"),
        ]
        for body in cases:
            with self.subTest(body=body["candidate_id"]):
                result = self.service.create_package(body, enabled=True)
                self.assertEqual(result["status"], "SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED")
                self.assertFalse(result["real_execution_supported"])

    def test_incomplete_checklist_requires_review(self) -> None:
        checklist = dict(CHECKLIST)
        checklist["bed_state_reviewed"] = False

        result = self.service.create_package(self.request(checklist=checklist), enabled=True)

        self.assertEqual(result["status"], "SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED")
        self.assertIn("checklist_incomplete", result["review_reasons"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest backend.tests.unit.services.test_swapmod_canary_preflight`

Expected: FAIL because `backend.app.services.swapmod_canary_preflight` does not exist.

### Task 3: RED API and Architecture Tests

**Files:**
- Create: `backend/tests/integration/test_swapmod_canary_preflight_api.py`
- Create: `backend/tests/unit/test_swapmod_canary_preflight_architecture.py`
- Create later: route/schema/service files

- [ ] **Step 1: Write API tests**

Cover disabled status, default-disabled package POST, enabled package response, and schema rejection of `raw_gcode`.

- [ ] **Step 2: Write architecture tests**

Scan `backend/app/services/swapmod_canary_preflight.py`, `backend/app/api/routes/swapmod_canary_preflight.py`, and `backend/app/schemas/swapmod_canary_preflight.py` for forbidden imports and names:

```python
forbidden = [
    "backend.app.services.printer_manager",
    "backend.app.services.bambu_mqtt",
    "backend.app.services.bambu_ftp",
    "backend.app.services.print_scheduler",
    "backend.app.api.routes.print_queue",
    "backend.app.services.erp",
    "backend.app.services.obico",
    "backend.app.models.bed_automation",
    ".send_gcode(",
    ".start_print(",
    "upload_file_async",
    "raw-command",
    "send-gcode",
    "execute-gcode",
    "start-next-print",
]
```

- [ ] **Step 3: Run RED**

Run:

```bash
python3 -m unittest backend.tests.integration.test_swapmod_canary_preflight_api
python3 -m unittest backend.tests.unit.test_swapmod_canary_preflight_architecture
```

Expected: FAIL because route/schema/service files do not exist.

### Task 4: GREEN Service and Schema

**Files:**
- Create: `backend/app/schemas/swapmod_canary_preflight.py`
- Create: `backend/app/services/swapmod_canary_preflight.py`
- Modify: `backend/app/core/config.py`

- [ ] **Step 1: Add config**

Add defaults near WP-065 settings:

```python
# WP-066 SwapMod canary preflight. Disabled by default and packages redacted
# candidate evidence only; it never executes printer commands.
farm_swapmod_canary_preflight_enabled: bool = False
farm_swapmod_canary_preflight_require_human_confirmation: bool = True
farm_swapmod_canary_preflight_single_printer_only: bool = True
```

- [ ] **Step 2: Add strict schemas**

Define `SwapmodCanaryPreflightChecklist` with all required boolean fields and `SwapmodCanaryPreflightPackageRequest` with `extra="forbid"`.

- [ ] **Step 3: Add pure service**

Implement `SwapmodCanaryPreflightService.status_snapshot()` and `create_package()`. Return `SWAPMOD_CANARY_PREFLIGHT_REVIEW_REQUIRED` instead of throwing for review failures; throw only `feature_disabled` when disabled. Redact output to candidate id, kind, line count, line range hash, command-family counts, stop conditions, confirmation phrase metadata, and zero sentinels.

- [ ] **Step 4: Run service tests GREEN**

Run: `python3 -m unittest backend.tests.unit.services.test_swapmod_canary_preflight`

Expected: PASS.

### Task 5: GREEN Route and Make Target

**Files:**
- Create: `backend/app/api/routes/swapmod_canary_preflight.py`
- Modify: `backend/app/main.py`
- Modify: `Makefile`

- [ ] **Step 1: Add route**

Expose:

- `GET /api/v1/plate-change-3mf/swapmod-canary-preflight/status`
- `POST /api/v1/plate-change-3mf/swapmod-canary-preflight/packages`

Use `PRINTERS_READ` for status and `PRINTERS_CONTROL` for package creation.

- [ ] **Step 2: Include router**

Import `swapmod_canary_preflight` in `backend/app/main.py` and include it with `app_settings.api_prefix`.

- [ ] **Step 3: Add Make targets**

Add `harness-swapmod-canary-preflight` and `test-swapmod-canary-preflight`. The test target must run harness, service, architecture, and Docker-backed API tests using the existing `$(COMPOSE_PROJECT_NAME)-bambuddy:latest` pattern.

- [ ] **Step 4: Run focused tests GREEN**

Run:

```bash
python3 -m unittest harness.tests.test_swapmod_canary_preflight_mock
python3 -m unittest backend.tests.unit.services.test_swapmod_canary_preflight
python3 -m unittest backend.tests.unit.test_swapmod_canary_preflight_architecture
```

Expected: PASS.

### Task 6: Docs, Workpack, and Validation

**Files:**
- Create: `docs/architecture/WP066_SWAPMOD_CANARY_PREFLIGHT.md`
- Create: `docs/runbooks/WP066_SWAPMOD_CANARY_PREFLIGHT.md`
- Modify: `workpacks/exec/WP-066.md`

- [ ] **Step 1: Add architecture doc**

Document the boundary, request/response shape, no-execution flags, forbidden imports, and rollback.

- [ ] **Step 2: Add runbook**

Document feature flag default, safe status check, package request shape, exact confirmation phrase, stop conditions, and rollback by leaving `FARM_SWAPMOD_CANARY_PREFLIGHT_ENABLED=false`.

- [ ] **Step 3: Update Work Package**

Mark implementation plan and tests completed only after evidence exists. Add harness changes, implementation files, validation command results, risks, and outcomes.

- [ ] **Step 4: Run required validation**

Run:

```bash
python3 -m unittest harness.tests.test_swapmod_canary_preflight_mock
python3 -m unittest backend.tests.unit.services.test_swapmod_canary_preflight
python3 -m unittest backend.tests.unit.test_swapmod_canary_preflight_architecture
make test-swapmod-canary-preflight
make verify-fast
git diff --check
```

Expected: focused tests pass. `git diff --check` may remain blocked until Git object corruption is repaired.

## Self-Review

- Spec coverage: config, status, package endpoint, candidate selection, A1 Mini scope, checklist, exact phrase, no-execution flags, side-effect sentinels, tests, docs, rollback, and workpack evidence are covered.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: request field names match the design spec and planned tests.
