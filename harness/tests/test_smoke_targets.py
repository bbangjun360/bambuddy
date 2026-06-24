from __future__ import annotations

import unittest

import harness.scripts.smoke as smoke


class SmokeTargetsTest(unittest.TestCase):
    def test_smoke_checks_bambuddy_root_health_docs_and_mock_services(self) -> None:
        self.assertTrue(smoke.TARGETS["bambuddy-root"].endswith("/"))
        self.assertTrue(smoke.TARGETS["bambuddy-health"].endswith("/health"))
        self.assertTrue(smoke.TARGETS["bambuddy-docs"].endswith("/docs"))
        self.assertTrue(smoke.TARGETS["mock-services"].endswith("/health"))


if __name__ == "__main__":
    unittest.main()
