from __future__ import annotations

import http.client
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

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
    def _write_env(self, tmpdir: str, body: str) -> Path:
        env_file = Path(tmpdir) / ".env.harness"
        env_file.write_text(body, encoding="utf-8")
        return env_file

    def test_smoke_checks_bambuddy_root_health_docs_and_mock_services(self) -> None:
        with TemporaryDirectory() as tmpdir:
            targets = smoke.resolve_targets(env_file=Path(tmpdir) / "missing.env", environ={})

        self.assertTrue(targets["bambuddy-root"].endswith("/"))
        self.assertTrue(targets["bambuddy-health"].endswith("/health"))
        self.assertTrue(targets["bambuddy-docs"].endswith("/docs"))
        self.assertTrue(targets["mock-services"].endswith("/health"))

    def test_scripts_use_default_ports_from_selected_harness_env(self) -> None:
        with TemporaryDirectory() as tmpdir:
            env_file = self._write_env(
                tmpdir,
                "\n".join(
                    [
                        "BAMBUDDY_PORT=18130",
                        "MOCK_PORT=19130",
                    ]
                ),
            )
            targets = smoke.resolve_targets(env_file=env_file, environ={})

        self.assertEqual(targets["bambuddy-root"], "http://127.0.0.1:18130/")
        self.assertEqual(targets["bambuddy-health"], "http://127.0.0.1:18130/health")
        self.assertEqual(targets["mock-services"], "http://127.0.0.1:19130/health")

    def test_scripts_use_custom_ports_from_selected_harness_env(self) -> None:
        with TemporaryDirectory() as tmpdir:
            env_file = self._write_env(
                tmpdir,
                "\n".join(
                    [
                        "BAMBUDDY_PORT=18131",
                        "MOCK_PORT=19131",
                    ]
                ),
            )
            targets = smoke.resolve_targets(env_file=env_file, environ={})

        self.assertEqual(targets["bambuddy-root"], "http://127.0.0.1:18131/")
        self.assertEqual(targets["bambuddy-health"], "http://127.0.0.1:18131/health")
        self.assertEqual(targets["mock-services"], "http://127.0.0.1:19131/health")

    def test_explicit_endpoint_env_vars_override_selected_harness_env(self) -> None:
        with TemporaryDirectory() as tmpdir:
            env_file = self._write_env(
                tmpdir,
                "\n".join(
                    [
                        "BAMBUDDY_PORT=18131",
                        "MOCK_PORT=19131",
                    ]
                ),
            )
            with mock.patch.dict(
                smoke.os.environ,
                {
                    "BAMBUDDY_BASE_URL": "http://127.0.0.1:28131/",
                    "MOCK_BASE_URL": "http://127.0.0.1:29131/",
                },
                clear=True,
            ):
                targets = smoke.resolve_targets(env_file=env_file)

        self.assertEqual(targets["bambuddy-root"], "http://127.0.0.1:28131/")
        self.assertEqual(targets["bambuddy-health"], "http://127.0.0.1:28131/health")
        self.assertEqual(targets["mock-services"], "http://127.0.0.1:29131/health")

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

    def test_preflight_reports_harness_not_running_before_readiness_loop(self) -> None:
        attempts = []

        def fake_connect(address: tuple[str, int], timeout: float) -> object:
            attempts.append((address, timeout))
            raise ConnectionRefusedError(111, "Connection refused")

        with self.assertRaisesRegex(
            smoke.HarnessNotRunningError,
            "make harness-up",
        ):
            smoke.preflight_harness_targets(
                {"bambuddy-root": "http://127.0.0.1:18000/"},
                connector=fake_connect,
            )

        self.assertEqual(attempts, [(('127.0.0.1', 18000), 1.0)])

    def test_preflight_skips_remote_override_targets(self) -> None:
        attempts = []

        smoke.preflight_harness_targets(
            {"bambuddy-root": "http://harness.example.test:18000/"},
            connector=lambda address, timeout: attempts.append((address, timeout)),
        )

        self.assertEqual(attempts, [])


if __name__ == "__main__":
    unittest.main()
