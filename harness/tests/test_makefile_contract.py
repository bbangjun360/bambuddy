from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
DOCKERFILE = ROOT / "Dockerfile"
HARNESS_COMPOSE = ROOT / "harness/docker-compose.harness.yml"


def _target_body(text: str, target: str) -> str:
    match = re.search(rf"^{re.escape(target)}(?:[: ].*)?\n(?P<body>(?:\t.*\n)+)", text, re.MULTILINE)
    assert match is not None, f"missing Makefile target {target}"
    return match.group("body")


class MakefileContractTest(unittest.TestCase):
    def test_wp000_validation_targets_are_real_commands(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")

        for target in ("test-unit", "test-characterization", "verify-fast"):
            body = _target_body(text, target)
            self.assertNotIn("TODO WP-000", body)
            self.assertNotIn("exit 2", body)


    def test_harness_build_passes_git_branch_for_worktree_builds(self) -> None:
        makefile = MAKEFILE.read_text(encoding="utf-8")
        compose = HARNESS_COMPOSE.read_text(encoding="utf-8")
        dockerfile = DOCKERFILE.read_text(encoding="utf-8")

        self.assertIn("git branch --show-current", makefile)
        self.assertIn("GIT_BRANCH=$(GIT_BRANCH)", makefile)
        self.assertIn("GIT_BRANCH: ${GIT_BRANCH:-main}", compose)
        self.assertIn("ARG GIT_BRANCH=main", dockerfile)
        self.assertIn("ENV GIT_BRANCH=${GIT_BRANCH}", dockerfile)
        self.assertIn("COPY .git ./.git", dockerfile)
        dockerfile_lines = {line.strip() for line in dockerfile.splitlines()}
        self.assertNotIn("COPY .git/HEAD ./.git/HEAD", dockerfile_lines)


    def test_wp030_erp_readonly_target_runs_focused_tests(self) -> None:
        body = _target_body(MAKEFILE.read_text(encoding="utf-8"), "test-erp-readonly")

        self.assertIn("harness.tests.test_mock_services", body)
        self.assertIn("backend/tests/unit/services/test_erp_readonly.py", body)
        self.assertIn("backend/tests/unit/test_erp_readonly_architecture.py", body)
        self.assertIn("backend/tests/integration/test_erp_readonly_api.py", body)

    def test_wp070_obico_shadow_target_runs_focused_tests(self) -> None:
        body = _target_body(MAKEFILE.read_text(encoding="utf-8"), "test-obico-shadow")

        self.assertIn("backend.tests.unit.services.test_obico_shadow", body)
        self.assertIn("backend.tests.unit.test_obico_shadow_architecture", body)
        self.assertIn("harness.tests.test_obico_shadow_mock", body)
        self.assertIn("backend.tests.integration.test_obico_shadow_api", body)

    def test_wp070_harness_shadow_target_opts_in_explicitly(self) -> None:
        body = _target_body(MAKEFILE.read_text(encoding="utf-8"), "harness-obico-shadow")

        self.assertIn("FARM_OBICO_SHADOW_ENABLED=true", body)
        self.assertIn("harness/scripts/obico_shadow.py", body)

    def test_harness_reset_is_guarded_to_configured_project(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        body = _target_body(text, "harness-reset")

        self.assertIn("COMPOSE_PROJECT_NAME", text)
        self.assertIn(".env.harness", text)
        self.assertIn("COMPOSE_PROJECT_NAME", body)
        self.assertIn("farm_wp030", body)
        self.assertIn("down -v --remove-orphans", body)

    def test_scenario_target_has_checked_in_scenarios_to_discover(self) -> None:
        body = _target_body(MAKEFILE.read_text(encoding="utf-8"), "test-scenario")

        self.assertIn("-p 'scenario_*.py'", body)
        self.assertGreater(
            len(list((ROOT / "harness/tests").glob("scenario_*.py"))),
            0,
            "test-scenario must not be a zero-test gate",
        )

    def test_frontend_gate_policy_is_encoded_in_make_targets(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        test_frontend = _target_body(text, "test-frontend")
        frontend_gate = _target_body(text, "frontend-gate-check")

        self.assertIn("npm --prefix frontend", test_frontend)
        self.assertIn("test:run", test_frontend)
        self.assertIn("harness/scripts/check_frontend_gate.py", frontend_gate)
        self.assertRegex(text, r"(?m)^verify-fast: .*frontend-gate-check")
        self.assertRegex(text, r"(?m)^verify-full: .*frontend-gate-check")


if __name__ == "__main__":
    unittest.main()
