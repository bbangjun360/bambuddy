from __future__ import annotations

import http.client
import unittest
from unittest import mock

import harness.scripts.orca_direct_slice as orca_direct_slice
import harness.scripts.orca_health as orca_health
import harness.scripts.smoke as smoke


class _FakeResponse:
    status = 200

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return b"ok"


class SmokeTargetsTest(unittest.TestCase):
    def test_smoke_checks_bambuddy_root_health_docs_and_mock_services(self) -> None:
        self.assertTrue(smoke.TARGETS["bambuddy-root"].endswith("/"))
        self.assertTrue(smoke.TARGETS["bambuddy-health"].endswith("/health"))
        self.assertTrue(smoke.TARGETS["bambuddy-docs"].endswith("/docs"))
        self.assertTrue(smoke.TARGETS["mock-services"].endswith("/health"))


    def test_scripts_default_to_harness_env_ports(self) -> None:
        self.assertEqual(smoke.TARGETS["bambuddy-root"], "http://127.0.0.1:18130/")
        self.assertEqual(smoke.TARGETS["bambuddy-health"], "http://127.0.0.1:18130/health")
        self.assertEqual(smoke.TARGETS["mock-services"], "http://127.0.0.1:19130/health")
        self.assertEqual(orca_health.ORCA_BASE_URL, "http://127.0.0.1:13130")
        self.assertEqual(orca_direct_slice.ORCA_BASE_URL, "http://127.0.0.1:13130")

    def test_wait_for_retries_transient_connection_reset_before_success(self) -> None:
        attempts = []

        def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
            attempts.append((url, timeout))
            if len(attempts) == 1:
                raise ConnectionResetError(104, "Connection reset by peer")
            return _FakeResponse()

        with (
            mock.patch.object(smoke.urllib.request, "urlopen", side_effect=fake_urlopen),
            mock.patch.object(smoke.time, "sleep"),
        ):
            result = smoke.wait_for("bambuddy-root", "http://example.test/", timeout=5)

        self.assertEqual(result["status"], 200)
        self.assertEqual(len(attempts), 2)

    def test_wait_for_retries_remote_disconnect_before_success(self) -> None:
        attempts = []

        def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
            attempts.append((url, timeout))
            if len(attempts) == 1:
                raise http.client.RemoteDisconnected("Remote end closed connection")
            return _FakeResponse()

        with (
            mock.patch.object(smoke.urllib.request, "urlopen", side_effect=fake_urlopen),
            mock.patch.object(smoke.time, "sleep"),
        ):
            result = smoke.wait_for("bambuddy-root", "http://example.test/", timeout=5)

        self.assertEqual(result["status"], 200)
        self.assertEqual(len(attempts), 2)

    def test_wait_for_reports_last_transient_error_after_timeout(self) -> None:
        with (
            mock.patch.object(
                smoke.urllib.request,
                "urlopen",
                side_effect=ConnectionAbortedError(103, "Software caused connection abort"),
            ),
            mock.patch.object(smoke.time, "monotonic", side_effect=[0.0, 0.0, 2.0]),
            mock.patch.object(smoke.time, "sleep"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Software caused connection abort"):
                smoke.wait_for("bambuddy-root", "http://example.test/", timeout=1)


if __name__ == "__main__":
    unittest.main()
