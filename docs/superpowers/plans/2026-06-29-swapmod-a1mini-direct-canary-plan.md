# SwapMod A1 Mini Direct Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a default-off A1 Mini direct plate-change canary boundary that can send one server-side allowlisted SwapMod transport sequence after exact human gates.

**Architecture:** Keep the WP-075 dry-run state machine unchanged and add a separate direct-canary schema, service, and route. The new service reads a configured sequence file, checks its SHA-256, verifies the SwapMod cycle state and printer idle state, sends through an injected Bambuddy printer transport, and advances the cycle to verification on success.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy async sessions, Python `hashlib`/`pathlib`, `unittest`, existing Bambuddy printer manager injection pattern.

---

### Task 1: RED Tests

**Files:**
- Create: `backend/tests/unit/services/test_swapmod_a1mini_direct_canary.py`
- Create: `backend/tests/integration/test_swapmod_a1mini_direct_canary_api.py`
- Create: `backend/tests/unit/test_swapmod_a1mini_direct_canary_architecture.py`
- Modify: `harness/tests/test_swapmod_state_machine_mock.py`
- Modify: `Makefile`

- [ ] Add a unit test proving the route is disabled unless the new feature and allow-real flags are both true.
- [ ] Add a unit test proving the request is blocked unless the cycle is in `READY_TO_RELEASE` or `READY_TO_LOAD` for the matching step.
- [ ] Add a unit test proving the exact phrase includes printer id, cycle key, step, and configured sequence SHA.
- [ ] Add a unit test proving a successful fake transport advances to `VERIFY_RELEASED` or `VERIFY_LOADED`.
- [ ] Add a unit test proving send failure blocks into manual review and does not expose retry.
- [ ] Add an API test proving default-off returns 404.
- [ ] Add an API test proving schema rejects `raw_gcode`.
- [ ] Add an API test proving a mocked transport sends only configured file content.

### Task 2: Implementation

**Files:**
- Create: `backend/app/services/swapmod_a1mini_direct_canary.py`
- Create: `backend/app/schemas/swapmod_a1mini_direct_canary.py`
- Create: `backend/app/api/routes/swapmod_a1mini_direct_canary.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/swapmod_state_machine.py`

- [ ] Add default-off config flags and sequence file/hash settings.
- [ ] Add strict request/checklist schemas.
- [ ] Add service gate validation, SHA validation, redacted status, and response payloads.
- [ ] Add a route dependency that wraps `printer_manager.get_client(printer_id).send_gcode(...)`.
- [ ] Add a state-machine success event for real canary command sent.
- [ ] Add a state-machine failure path that blocks into manual review without retry.

### Task 3: Docs and Validation

**Files:**
- Create: `workpacks/exec/WP-076_SWAPMOD_A1_MINI_DIRECT_CANARY.md`
- Create: `docs/runbooks/WP076_SWAPMOD_A1_MINI_DIRECT_CANARY.md`
- Modify: `Makefile`

- [ ] Add focused Make target `test-swapmod-a1mini-direct-canary`.
- [ ] Run the RED tests, then implementation, then focused target.
- [ ] Run `make test-swapmod-state-machine`.
- [ ] Run `make verify-fast`.
- [ ] Run proof scans for generated artifacts, secrets, and forbidden arbitrary command endpoints.
- [ ] Commit all code/docs/test changes, leaving real execution disabled by default.
