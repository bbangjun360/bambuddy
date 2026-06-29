# WP-065 SwapMod Dry-Run Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a default-off dry-run API that compares original and SwapMod 3MF artifacts, returns redacted plate-change candidate summaries, and simulates the future post-print workflow without hardware side effects.

**Architecture:** Add a focused `swapmod_3mf_dry_run` service, schema, and route under the existing plate-change 3MF API area. The service reads only local controlled 3MF ZIP files, extracts `.gcode` members for comparison, redacts all command content, and returns dry-run workflow states plus zeroed forbidden side-effect sentinels.

**Tech Stack:** FastAPI routes, Pydantic schemas, Python `zipfile`, `hashlib`, `unittest`, existing Makefile/harness patterns.

---

## File Map

- Create `backend/app/services/swapmod_3mf_dry_run.py`: path validation, 3MF reading, exact-match extraction, redacted candidate summaries, dry-run status.
- Create `backend/app/schemas/swapmod_3mf_dry_run.py`: strict request schemas.
- Create `backend/app/api/routes/swapmod_3mf_dry_run.py`: status and plan endpoints.
- Modify `backend/app/main.py`: include the new router.
- Modify `backend/app/core/config.py`: add default-off dry-run settings.
- Create `backend/tests/unit/services/test_swapmod_3mf_dry_run.py`: service behavior and failure tests.
- Create `backend/tests/integration/test_swapmod_3mf_dry_run_api.py`: API behavior and schema rejection tests.
- Create `backend/tests/unit/test_swapmod_3mf_dry_run_architecture.py`: forbidden import/name checks.
- Create `harness/tests/test_swapmod_3mf_dry_run_mock.py`: Makefile target and no external mock route checks.
- Modify `Makefile`: add focused WP-065 targets.
- Create `workpacks/exec/WP-065.md`: active Work Package record.
- Create `docs/architecture/WP065_SWAPMOD_DRY_RUN_WORKFLOW.md`: architecture summary.
- Create `docs/runbooks/WP065_SWAPMOD_DRY_RUN_REVIEW.md`: review/runbook.

## Task 1: Workpack, Harness, and RED Service Tests

**Files:**
- Create: `workpacks/exec/WP-065.md`
- Create: `harness/tests/test_swapmod_3mf_dry_run_mock.py`
- Create: `backend/tests/unit/services/test_swapmod_3mf_dry_run.py`
- Modify: `Makefile`

- [ ] **Step 1: Create WP-065 workpack**

Add a Work Package stating that WP-065 is dry-run only, default-off, no hardware, no upload/start, no direct MQTT/FTPS, no queue/scheduler dispatch, no raw G-code endpoint, and no software resume.

- [ ] **Step 2: Add harness RED test**

Create `harness/tests/test_swapmod_3mf_dry_run_mock.py` with:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_makefile_exposes_swapmod_dry_run_targets() -> None:
    makefile = (ROOT / "Makefile").read_text()
    assert "harness-swapmod-3mf-dry-run:" in makefile
    assert "test-swapmod-3mf-dry-run: harness-swapmod-3mf-dry-run" in makefile


def test_mock_services_do_not_expose_swapmod_hardware_routes() -> None:
    text = (ROOT / "harness/mock_services.py").read_text()
    forbidden = [
        "/swapmod/v1/send-gcode",
        "/swapmod/v1/raw-command",
        "/swapmod/v1/start-next-print",
        "swapmod_printer_commands",
        "swapmod_queue_dispatches",
    ]
    for needle in forbidden:
        assert needle not in text
```

- [ ] **Step 3: Add unit RED test fixture helpers**

Create `backend/tests/unit/services/test_swapmod_3mf_dry_run.py` with helpers that build temporary 3MF ZIP files containing `Metadata/plate_1.gcode`.

```python
import tempfile
import unittest
import zipfile
from pathlib import Path

from backend.app.services.swapmod_3mf_dry_run import Swapmod3mfDryRunService, Swapmod3mfDryRunError


def write_3mf(root: Path, name: str, gcode: str) -> Path:
    path = root / name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Metadata/plate_1.gcode", gcode)
        zf.writestr("3D/3dmodel.model", "<model />")
    return path
```

- [ ] **Step 4: Add unit RED tests**

Add tests named:

```python
class Swapmod3mfDryRunServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.service = Swapmod3mfDryRunService()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_default_status_is_disabled_and_dry_run_only(self) -> None:
        status = self.service.status_snapshot(enabled=False, dry_run=True, allowed_roots=[self.root])
        self.assertFalse(status["enabled"])
        self.assertEqual(status["mode"], "DRY_RUN_ONLY")
        self.assertFalse(status["real_execution_supported"])

    def test_exact_swapmod_pair_returns_three_redacted_candidates(self) -> None:
        original = "G28\n; print\nG1 X1\nM400\n"
        swapmod = "; load\nG1 Y1\n" + original + "; swap\nG1 Y2\nG4 P100\n" + original + "; final\nG1 Y3\n"
        original_path = write_3mf(self.root, "original.3mf", original)
        swapmod_path = write_3mf(self.root, "swapmod.3mf", swapmod)

        result = self.service.create_plan(
            original_path=original_path,
            swapmod_path=swapmod_path,
            enabled=True,
            dry_run=True,
            request_dry_run=True,
            allowed_roots=[self.root],
        )

        self.assertEqual(result["status"], "SWAPMOD_DRY_RUN_READY")
        self.assertEqual([b["candidate_kind"] for b in result["candidate_blocks"]], [
            "plate_load_only",
            "inter_job_swap",
            "final_swap",
        ])
        self.assertTrue(all(b["raw_gcode_included"] is False for b in result["candidate_blocks"]))
        self.assertNotIn("G1 Y2", str(result))

    def test_ambiguous_swapmod_pair_requires_review(self) -> None:
        original_path = write_3mf(self.root, "original.3mf", "G28\nG1 X1\n")
        swapmod_path = write_3mf(self.root, "swapmod.3mf", "G28\nG1 X1\n; only once\n")
        result = self.service.create_plan(
            original_path=original_path,
            swapmod_path=swapmod_path,
            enabled=True,
            dry_run=True,
            request_dry_run=True,
            allowed_roots=[self.root],
        )
        self.assertEqual(result["status"], "SWAPMOD_DRY_RUN_REVIEW_REQUIRED")
        self.assertEqual(result["candidate_blocks"], [])

    def test_repository_path_is_rejected(self) -> None:
        with self.assertRaises(Swapmod3mfDryRunError) as raised:
            self.service.create_plan(
                original_path=Path("repo.3mf"),
                swapmod_path=Path("repo-swap.3mf"),
                enabled=True,
                dry_run=True,
                request_dry_run=True,
                allowed_roots=[Path.cwd()],
                repository_root=Path.cwd(),
            )
        self.assertEqual(raised.exception.code, "source_path_not_allowed")
```

- [ ] **Step 5: Run RED commands**

Run:

```bash
python3 -m unittest harness.tests.test_swapmod_3mf_dry_run_mock
python3 -m unittest backend.tests.unit.services.test_swapmod_3mf_dry_run
```

Expected: harness fails before Makefile target exists; unit tests fail because `backend.app.services.swapmod_3mf_dry_run` does not exist.

## Task 2: Minimal Service Implementation

**Files:**
- Create: `backend/app/services/swapmod_3mf_dry_run.py`
- Modify: `Makefile`

- [ ] **Step 1: Add Makefile targets**

Add:

```make
.PHONY: harness-swapmod-3mf-dry-run
harness-swapmod-3mf-dry-run:
	python3 -m unittest harness.tests.test_swapmod_3mf_dry_run_mock

.PHONY: test-swapmod-3mf-dry-run
test-swapmod-3mf-dry-run: harness-swapmod-3mf-dry-run
	python3 -m unittest backend.tests.unit.services.test_swapmod_3mf_dry_run backend.tests.unit.test_swapmod_3mf_dry_run_architecture
	docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp065-tests -e LOG_DIR=/tmp/bambuddy-wp065-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(PWD):/workspace:ro -w /workspace --entrypoint python farm_wp030-bambuddy:latest -m unittest backend.tests.integration.test_swapmod_3mf_dry_run_api
```

- [ ] **Step 2: Implement service constants and errors**

Create `Swapmod3mfDryRunError`, `Swapmod3mfDryRunService`, status constants, workflow trace constants, and forbidden sentinel names.

- [ ] **Step 3: Implement path and 3MF helpers**

Implement `_resolve_allowed_3mf_path`, `_read_gcode_members`, `_sha256_file`, `_redacted_name`, `_new_sentinels`, `_command_family_counts`, and `_candidate`.

- [ ] **Step 4: Implement exact extraction**

Implement exact line sequence matching. Return ready only when exactly two original occurrences are found in the SwapMod G-code.

- [ ] **Step 5: Verify GREEN unit tests**

Run:

```bash
python3 -m unittest backend.tests.unit.services.test_swapmod_3mf_dry_run
```

Expected: all service tests pass.

## Task 3: API, Schema, and Integration Tests

**Files:**
- Create: `backend/app/schemas/swapmod_3mf_dry_run.py`
- Create: `backend/app/api/routes/swapmod_3mf_dry_run.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/integration/test_swapmod_3mf_dry_run_api.py`

- [ ] **Step 1: Add strict schema**

Create `Swapmod3mfDryRunPlanRequest` with `extra="forbid"`, fields `original_path`, `swapmod_path`, `dry_run=True`, and optional `expected_printer_model_family`.

- [ ] **Step 2: Add default-off config**

Add:

```python
farm_swapmod_3mf_dry_run_enabled: bool = False
farm_swapmod_3mf_dry_run_required: bool = True
farm_swapmod_3mf_sample_root: str | None = None
```

- [ ] **Step 3: Add route**

Add status and plan endpoints under `/plate-change-3mf/swapmod-dry-run`.

- [ ] **Step 4: Register router**

Import and include the route in `backend/app/main.py` with the existing API prefix.

- [ ] **Step 5: Add integration tests**

Test default disabled `404`, enabled dry-run success with temp 3MF fixtures, and schema rejection of `raw_gcode`.

- [ ] **Step 6: Verify API tests**

Run:

```bash
docker run --rm --network none -e LOG_TO_FILE=false -e DATA_DIR=/tmp/bambuddy-wp065-tests -e LOG_DIR=/tmp/bambuddy-wp065-tests/logs -e PYTHONDONTWRITEBYTECODE=1 -v $(PWD):/workspace:ro -w /workspace --entrypoint python farm_wp030-bambuddy:latest -m unittest backend.tests.integration.test_swapmod_3mf_dry_run_api
```

Expected: all integration tests pass.

## Task 4: Architecture, Docs, and Full Focused Validation

**Files:**
- Create: `backend/tests/unit/test_swapmod_3mf_dry_run_architecture.py`
- Create: `docs/architecture/WP065_SWAPMOD_DRY_RUN_WORKFLOW.md`
- Create: `docs/runbooks/WP065_SWAPMOD_DRY_RUN_REVIEW.md`
- Modify: `workpacks/exec/WP-065.md`

- [ ] **Step 1: Add architecture tests**

Check the new service and route do not contain forbidden strings: `printer_manager`, `bambu_mqtt`, `bambu_ftp`, `send_gcode`, `start_print`, `queue_dispatch`, `scheduler_dispatch`, `erp`, `obico`, `BedAutomationCycle`.

- [ ] **Step 2: Add architecture doc**

Document the default-off dry-run boundary, request/response redaction, exact-match limitation, and WP-066 real-canary handoff.

- [ ] **Step 3: Add runbook**

Document how to run a local dry-run review with synthetic or reviewed local sample artifacts, and stop conditions for ambiguous extraction.

- [ ] **Step 4: Update workpack progress**

Record RED/GREEN evidence and required validation commands in `workpacks/exec/WP-065.md`.

- [ ] **Step 5: Run focused target**

Run:

```bash
make test-swapmod-3mf-dry-run
```

Expected: harness, unit, architecture, and Docker-backed integration tests pass.

- [ ] **Step 6: Run fast validation**

Run:

```bash
make verify-fast
git diff --check
git ls-files -- '*.3mf' '*.gcode' '*.gcode.3mf'
git status --short -- '*.3mf' '*.gcode' '*.gcode.3mf'
```

Expected: verification passes and no generated 3MF/G-code files are tracked or staged.
