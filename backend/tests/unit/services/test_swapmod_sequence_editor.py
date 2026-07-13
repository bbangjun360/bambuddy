from __future__ import annotations

import hashlib
import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.services import swapmod_sequence_editor as sequence_editor_module
from backend.app.services.swapmod_sequence_editor import (
    SwapmodSequenceEditorError,
    SwapmodSequenceEditorService,
)


class SwapmodSequenceEditorServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.release_text = (
            "; reviewed release sequence\nG91\nG1 X-14 F5000 ; park\nG1 Y182 F10000 ; eject\nM400\nG90\n"
        )
        self.load_text = "G91\r\nG0 Y180 F2000 ; pull plate\r\nG90\r\n"
        (self.root / "release.gcode").write_bytes(self.release_text.encode("utf-8"))
        (self.root / "load.gcode").write_bytes(self.load_text.encode("utf-8"))
        self.release_sha = hashlib.sha256(self.release_text.encode("utf-8")).hexdigest()
        self.load_sha = hashlib.sha256(self.load_text.encode("utf-8")).hexdigest()
        self.service = SwapmodSequenceEditorService()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _config(self) -> dict[str, object]:
        return {
            "enabled": True,
            "direct_canary_enabled": False,
            "allow_real_commands": False,
            "sequence_root": self.root,
            "release_sequence_file": "release.gcode",
            "release_sequence_sha256": self.release_sha,
            "load_sequence_file": "load.gcode",
            "load_sequence_sha256": self.load_sha,
        }

    def _snapshot(self) -> dict[str, object]:
        return self.service.status_snapshot(**self._config())

    def test_snapshot_returns_structured_actions_without_raw_content_or_paths(self) -> None:
        snapshot = self._snapshot()

        self.assertTrue(snapshot["enabled"])
        self.assertFalse(snapshot["direct_canary_armed"])
        release = snapshot["sequences"][0]
        self.assertEqual(release["step"], "RELEASE_PLATE")
        self.assertTrue(release["integrity_verified"])
        self.assertEqual(release["base_sha256"], self.release_sha)
        self.assertEqual(
            [(action["target"], action["feedrate"]) for action in release["actions"]],
            [("X-14", 5000), ("Y182", 10000)],
        )
        serialized = json.dumps(snapshot)
        self.assertNotIn("reviewed release sequence", serialized)
        self.assertNotIn("G1 ", serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn("release.gcode", serialized)

    def test_save_creates_immutable_pending_candidate_and_leaves_source_unchanged(self) -> None:
        release = self._snapshot()["sequences"][0]
        actions = [
            {"action_id": action["action_id"], "feedrate": action["feedrate"] + 250} for action in release["actions"]
        ]

        candidate = self.service.create_candidate(
            **self._config(),
            step="RELEASE_PLATE",
            base_sha256=self.release_sha,
            actions=actions,
            created_by="test-operator",
        )

        self.assertFalse(candidate["active"])
        self.assertEqual(candidate["review_status"], "PENDING_REVIEW")
        self.assertTrue(candidate["operator_review_required"])
        self.assertFalse(candidate["activation_supported"])
        self.assertEqual((self.root / "release.gcode").read_text(encoding="utf-8"), self.release_text)

        candidate_dir = self.root / ".bambuddy-swapmod-candidates"
        generated = list(candidate_dir.glob("*.gcode"))
        manifests = list(candidate_dir.glob("*.json"))
        self.assertEqual(len(generated), 1)
        self.assertEqual(len(manifests), 1)
        self.assertEqual(stat.S_IMODE(candidate_dir.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(generated[0].stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(manifests[0].stat().st_mode), 0o600)
        expected = self.release_text.replace("F5000", "F5250").replace("F10000", "F10250")
        self.assertEqual(generated[0].read_text(encoding="utf-8"), expected)
        self.assertEqual(candidate["sha256"], hashlib.sha256(expected.encode("utf-8")).hexdigest())

        manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
        self.assertEqual(manifest["version_id"], candidate["version_id"])
        self.assertEqual(manifest["sha256"], candidate["sha256"])
        self.assertEqual(manifest["review_status"], "PENDING_REVIEW")
        self.assertFalse(manifest["active"])
        for key in self._nested_keys(candidate):
            self.assertNotIn(key, {"path", "file_path", "sequence_path", "raw_gcode", "gcode"})

    def test_save_emits_redacted_audit_log_without_sequence_content_or_path(self) -> None:
        release = self._snapshot()["sequences"][0]
        with self.assertLogs("backend.app.services.swapmod_sequence_editor", level="INFO") as captured:
            candidate = self.service.create_candidate(
                **self._config(),
                step="RELEASE_PLATE",
                base_sha256=self.release_sha,
                actions=[
                    {"action_id": action["action_id"], "feedrate": action["feedrate"]} for action in release["actions"]
                ],
                created_by="operator\nforged-line",
            )

        log = "\n".join(captured.output)
        self.assertIn(candidate["version_id"], log)
        self.assertIn(candidate["sha256"], log)
        self.assertNotIn("G1 X-14", log)
        self.assertNotIn(str(self.root), log)
        self.assertNotIn("\nforged-line", log)

    def test_save_preserves_crlf_and_changes_only_feedrate_digits(self) -> None:
        load = self._snapshot()["sequences"][1]
        candidate = self.service.create_candidate(
            **self._config(),
            step="LOAD_NEXT_PLATE",
            base_sha256=self.load_sha,
            actions=[{"action_id": load["actions"][0]["action_id"], "feedrate": 1750}],
            created_by="test-operator",
        )

        generated = self.root / ".bambuddy-swapmod-candidates" / f"{candidate['version_id']}.gcode"
        self.assertEqual(generated.read_bytes(), self.load_text.replace("F2000", "F1750").encode("utf-8"))

    def test_save_rejects_stale_base_hash_without_writing(self) -> None:
        release = self._snapshot()["sequences"][0]
        with self.assertRaisesRegex(SwapmodSequenceEditorError, "base sequence changed") as raised:
            self.service.create_candidate(
                **self._config(),
                step="RELEASE_PLATE",
                base_sha256="0" * 64,
                actions=[
                    {"action_id": action["action_id"], "feedrate": action["feedrate"]} for action in release["actions"]
                ],
                created_by="test-operator",
            )

        self.assertEqual(raised.exception.code, "sequence_base_stale")
        self.assertFalse((self.root / ".bambuddy-swapmod-candidates").exists())

    def test_save_rejects_source_whose_bytes_no_longer_match_pinned_hash(self) -> None:
        release = self._snapshot()["sequences"][0]
        (self.root / "release.gcode").write_text("G1 X1 F1\n", encoding="utf-8")

        with self.assertRaises(SwapmodSequenceEditorError) as raised:
            self.service.create_candidate(
                **self._config(),
                step="RELEASE_PLATE",
                base_sha256=self.release_sha,
                actions=[
                    {"action_id": action["action_id"], "feedrate": action["feedrate"]} for action in release["actions"]
                ],
                created_by="test-operator",
            )

        self.assertEqual(raised.exception.code, "sequence_sha256_mismatch")
        self.assertFalse((self.root / ".bambuddy-swapmod-candidates").exists())

    def test_save_rejects_when_direct_canary_is_armed(self) -> None:
        release = self._snapshot()["sequences"][0]
        config = self._config()
        config["direct_canary_enabled"] = True

        with self.assertRaises(SwapmodSequenceEditorError) as raised:
            self.service.create_candidate(
                **config,
                step="RELEASE_PLATE",
                base_sha256=self.release_sha,
                actions=[
                    {"action_id": action["action_id"], "feedrate": action["feedrate"]} for action in release["actions"]
                ],
                created_by="test-operator",
            )

        self.assertEqual(raised.exception.code, "direct_canary_must_be_disarmed")

    def test_save_requires_the_exact_server_action_set(self) -> None:
        release = self._snapshot()["sequences"][0]
        with self.assertRaises(SwapmodSequenceEditorError) as raised:
            self.service.create_candidate(
                **self._config(),
                step="RELEASE_PLATE",
                base_sha256=self.release_sha,
                actions=[
                    {
                        "action_id": release["actions"][0]["action_id"],
                        "feedrate": release["actions"][0]["feedrate"],
                    }
                ],
                created_by="test-operator",
            )

        self.assertEqual(raised.exception.code, "sequence_actions_mismatch")

    def test_each_save_gets_a_distinct_version_without_overwriting(self) -> None:
        release = self._snapshot()["sequences"][0]
        actions = [{"action_id": action["action_id"], "feedrate": action["feedrate"]} for action in release["actions"]]
        first = self.service.create_candidate(
            **self._config(),
            step="RELEASE_PLATE",
            base_sha256=self.release_sha,
            actions=actions,
            created_by="test-operator",
        )
        second = self.service.create_candidate(
            **self._config(),
            step="RELEASE_PLATE",
            base_sha256=self.release_sha,
            actions=actions,
            created_by="test-operator",
        )

        self.assertNotEqual(first["version_id"], second["version_id"])
        self.assertEqual(len(list((self.root / ".bambuddy-swapmod-candidates").glob("*.gcode"))), 2)

    def test_save_rejects_symbolic_link_candidate_directory(self) -> None:
        release = self._snapshot()["sequences"][0]
        with tempfile.TemporaryDirectory() as outside:
            (self.root / ".bambuddy-swapmod-candidates").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(SwapmodSequenceEditorError) as raised:
                self.service.create_candidate(
                    **self._config(),
                    step="RELEASE_PLATE",
                    base_sha256=self.release_sha,
                    actions=[
                        {"action_id": action["action_id"], "feedrate": action["feedrate"]}
                        for action in release["actions"]
                    ],
                    created_by="test-operator",
                )

        self.assertEqual(raised.exception.code, "candidate_directory_not_allowed")

    def test_save_tightens_existing_candidate_directory_permissions(self) -> None:
        release = self._snapshot()["sequences"][0]
        candidate_dir = self.root / ".bambuddy-swapmod-candidates"
        candidate_dir.mkdir(mode=0o777)
        candidate_dir.chmod(0o777)

        self.service.create_candidate(
            **self._config(),
            step="RELEASE_PLATE",
            base_sha256=self.release_sha,
            actions=[
                {"action_id": action["action_id"], "feedrate": action["feedrate"]} for action in release["actions"]
            ],
            created_by="test-operator",
        )

        self.assertEqual(stat.S_IMODE(candidate_dir.stat().st_mode), 0o700)

    def test_save_reports_file_write_failure_without_touching_source(self) -> None:
        release = self._snapshot()["sequences"][0]
        with (
            patch(
                "backend.app.services.swapmod_sequence_editor._write_candidate_pair",
                side_effect=OSError("synthetic disk failure"),
            ),
            self.assertRaises(SwapmodSequenceEditorError) as raised,
        ):
            self.service.create_candidate(
                **self._config(),
                step="RELEASE_PLATE",
                base_sha256=self.release_sha,
                actions=[
                    {"action_id": action["action_id"], "feedrate": action["feedrate"]} for action in release["actions"]
                ],
                created_by="test-operator",
            )

        self.assertEqual(raised.exception.code, "candidate_write_failed")
        self.assertEqual((self.root / "release.gcode").read_text(encoding="utf-8"), self.release_text)

    def test_partial_manifest_write_failure_removes_all_candidate_artifacts(self) -> None:
        release = self._snapshot()["sequences"][0]
        with (
            patch.object(sequence_editor_module.os, "fsync", side_effect=[None, OSError("synthetic fsync failure")]),
            self.assertRaises(SwapmodSequenceEditorError) as raised,
        ):
            self.service.create_candidate(
                **self._config(),
                step="RELEASE_PLATE",
                base_sha256=self.release_sha,
                actions=[
                    {"action_id": action["action_id"], "feedrate": action["feedrate"]} for action in release["actions"]
                ],
                created_by="test-operator",
            )

        candidate_dir = self.root / ".bambuddy-swapmod-candidates"
        self.assertEqual(raised.exception.code, "candidate_write_failed")
        self.assertEqual(list(candidate_dir.iterdir()), [])
        self.assertEqual((self.root / "release.gcode").read_text(encoding="utf-8"), self.release_text)

    @staticmethod
    def _nested_keys(value: object) -> set[str]:
        keys: set[str] = set()
        if isinstance(value, dict):
            for key, child in value.items():
                keys.add(str(key))
                keys.update(SwapmodSequenceEditorServiceTest._nested_keys(child))
        elif isinstance(value, list):
            for child in value:
                keys.update(SwapmodSequenceEditorServiceTest._nested_keys(child))
        return keys


if __name__ == "__main__":
    unittest.main()
