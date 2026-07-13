from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.swapmod_a1mini_direct_canary import (
    SwapmodA1MiniDirectCanaryError,
    load_pinned_a1mini_sequence,
)
from backend.app.services.swapmod_state_machine import LOAD_NEXT_PLATE, RELEASE_PLATE

SEQUENCE_CANDIDATE_DIRECTORY = ".bambuddy-swapmod-candidates"
SEQUENCE_REVIEW_PENDING = "PENDING_REVIEW"
FEEDRATE_MIN = 1
FEEDRATE_MAX = 30000
MAX_EDITABLE_ACTIONS = 100

_MOVE_COMMAND = re.compile(r"^\s*G(?:0?0|0?1)(?=\s|[A-Za-z]|$)", re.IGNORECASE | re.ASCII)
_WORD = re.compile(r"([A-Za-z])([+-]?(?:\d+(?:\.\d*)?|\.\d+))", re.ASCII)
_VERSION_ID = re.compile(r"^[a-z0-9-]{1,96}$", re.ASCII)
_SHA256 = re.compile(r"^[a-f0-9]{64}$", re.ASCII)

logger = logging.getLogger(__name__)


class SwapmodSequenceEditorError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class EditableSequenceAction:
    action_id: str
    label: str
    target: str
    feedrate: int
    line_index: int
    value_start: int
    value_end: int

    def public(self, *, feedrate: int | None = None) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "label": self.label,
            "target": self.target,
            "feedrate": self.feedrate if feedrate is None else feedrate,
        }


class SwapmodSequenceEditorService:
    def status_snapshot(
        self,
        *,
        enabled: bool,
        direct_canary_enabled: bool,
        allow_real_commands: bool,
        sequence_root: str | Path | None,
        release_sequence_file: str | None,
        release_sequence_sha256: str | None,
        load_sequence_file: str | None,
        load_sequence_sha256: str | None,
    ) -> dict[str, object]:
        config = {
            "sequence_root": sequence_root,
            "release_sequence_file": release_sequence_file,
            "release_sequence_sha256": release_sequence_sha256,
            "load_sequence_file": load_sequence_file,
            "load_sequence_sha256": load_sequence_sha256,
        }
        return {
            "enabled": bool(enabled),
            "direct_canary_armed": bool(direct_canary_enabled or allow_real_commands),
            "feedrate_min": FEEDRATE_MIN,
            "feedrate_max": FEEDRATE_MAX,
            "activation_supported": False,
            "sequences": [
                self._sequence_snapshot(step=RELEASE_PLATE, enabled=enabled, **config),
                self._sequence_snapshot(step=LOAD_NEXT_PLATE, enabled=enabled, **config),
            ],
        }

    def create_candidate(
        self,
        *,
        step: str,
        base_sha256: str,
        actions: list[dict[str, object]],
        created_by: str,
        enabled: bool,
        direct_canary_enabled: bool,
        allow_real_commands: bool,
        sequence_root: str | Path | None,
        release_sequence_file: str | None,
        release_sequence_sha256: str | None,
        load_sequence_file: str | None,
        load_sequence_sha256: str | None,
    ) -> dict[str, object]:
        if not enabled:
            raise SwapmodSequenceEditorError("sequence_editor_disabled", "SwapMod sequence editor is disabled")
        if direct_canary_enabled or allow_real_commands:
            raise SwapmodSequenceEditorError(
                "direct_canary_must_be_disarmed",
                "Disarm the A1 Mini direct canary before creating a sequence candidate",
            )
        if step not in {RELEASE_PLATE, LOAD_NEXT_PLATE}:
            raise SwapmodSequenceEditorError("unsupported_step", "Unsupported SwapMod sequence step")

        sequence_text, actual_sha = self._load_pinned(
            step=step,
            sequence_root=sequence_root,
            release_sequence_file=release_sequence_file,
            release_sequence_sha256=release_sequence_sha256,
            load_sequence_file=load_sequence_file,
            load_sequence_sha256=load_sequence_sha256,
        )
        if base_sha256.lower() != actual_sha:
            raise SwapmodSequenceEditorError(
                "sequence_base_stale",
                "The base sequence changed; reload the editor before saving",
            )

        parsed_actions = _parse_editable_actions(sequence_text, step=step)
        requested_ids = [str(action.get("action_id") or "") for action in actions]
        expected_ids = [action.action_id for action in parsed_actions]
        if len(requested_ids) != len(set(requested_ids)) or set(requested_ids) != set(expected_ids):
            raise SwapmodSequenceEditorError(
                "sequence_actions_mismatch",
                "The submitted action set does not match the pinned sequence",
            )

        requested_feedrates: dict[str, int] = {}
        for action in actions:
            action_id = str(action.get("action_id") or "")
            feedrate = action.get("feedrate")
            if isinstance(feedrate, bool) or not isinstance(feedrate, int):
                raise SwapmodSequenceEditorError("feedrate_invalid", "Each feedrate must be a whole number")
            if not FEEDRATE_MIN <= feedrate <= FEEDRATE_MAX:
                raise SwapmodSequenceEditorError(
                    "feedrate_out_of_range",
                    f"Feedrate must be between {FEEDRATE_MIN} and {FEEDRATE_MAX}",
                )
            requested_feedrates[action_id] = feedrate

        candidate_text = _render_candidate(sequence_text, parsed_actions, requested_feedrates)
        candidate_bytes = candidate_text.encode("utf-8")
        candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
        created_at = datetime.now(timezone.utc)
        public_actions = [action.public(feedrate=requested_feedrates[action.action_id]) for action in parsed_actions]
        actor = _sanitize_audit_actor(created_by)
        candidate = {
            "version_id": "",
            "step": step,
            "base_sha256": actual_sha,
            "sha256": candidate_sha,
            "created_at": created_at.isoformat().replace("+00:00", "Z"),
            "created_by": actor,
            "review_status": SEQUENCE_REVIEW_PENDING,
            "active": False,
            "activation_supported": False,
            "operator_review_required": True,
            "actions": public_actions,
        }
        directory = _candidate_directory(sequence_root)
        directory_fd = _open_candidate_directory(directory)
        try:
            for _attempt in range(5):
                version_id = _new_version_id(step=step, created_at=created_at)
                candidate["version_id"] = version_id
                try:
                    _write_candidate_pair(
                        directory_fd=directory_fd,
                        version_id=version_id,
                        candidate_bytes=candidate_bytes,
                        manifest=candidate,
                    )
                except FileExistsError:
                    continue
                except OSError as exc:
                    raise SwapmodSequenceEditorError(
                        "candidate_write_failed",
                        "Candidate version could not be written",
                    ) from exc
                logger.info(
                    "SwapMod sequence candidate created; version_id=%s step=%s base_sha256=%s "
                    "candidate_sha256=%s created_by=%s review_status=%s active=false",
                    version_id,
                    step,
                    actual_sha,
                    candidate_sha,
                    actor,
                    SEQUENCE_REVIEW_PENDING,
                )
                return dict(candidate)
        finally:
            os.close(directory_fd)
        raise SwapmodSequenceEditorError(
            "candidate_version_collision",
            "Could not allocate a unique candidate version",
        )

    def _sequence_snapshot(
        self,
        *,
        step: str,
        enabled: bool,
        sequence_root: str | Path | None,
        release_sequence_file: str | None,
        release_sequence_sha256: str | None,
        load_sequence_file: str | None,
        load_sequence_sha256: str | None,
    ) -> dict[str, object]:
        configured_sha = release_sequence_sha256 if step == RELEASE_PLATE else load_sequence_sha256
        configured_file = release_sequence_file if step == RELEASE_PLATE else load_sequence_file
        configured = bool(sequence_root and configured_file and configured_sha)
        snapshot: dict[str, object] = {
            "step": step,
            "configured": configured,
            "integrity_verified": False,
            "editable": False,
            "base_sha256": configured_sha if configured else None,
            "error_code": None,
            "actions": [],
            "latest_candidate": None,
        }
        if not enabled or not configured:
            return snapshot
        try:
            sequence_text, actual_sha = self._load_pinned(
                step=step,
                sequence_root=sequence_root,
                release_sequence_file=release_sequence_file,
                release_sequence_sha256=release_sequence_sha256,
                load_sequence_file=load_sequence_file,
                load_sequence_sha256=load_sequence_sha256,
            )
            snapshot["integrity_verified"] = True
            actions = _parse_editable_actions(sequence_text, step=step)
            snapshot.update(
                {
                    "editable": True,
                    "base_sha256": actual_sha,
                    "actions": [action.public() for action in actions],
                    "latest_candidate": _latest_candidate(sequence_root, step=step),
                }
            )
        except SwapmodSequenceEditorError as exc:
            snapshot["error_code"] = exc.code
        return snapshot

    @staticmethod
    def _load_pinned(
        *,
        step: str,
        sequence_root: str | Path | None,
        release_sequence_file: str | None,
        release_sequence_sha256: str | None,
        load_sequence_file: str | None,
        load_sequence_sha256: str | None,
    ) -> tuple[str, str]:
        try:
            return load_pinned_a1mini_sequence(
                step=step,
                sequence_root=sequence_root,
                release_sequence_file=release_sequence_file,
                release_sequence_sha256=release_sequence_sha256,
                load_sequence_file=load_sequence_file,
                load_sequence_sha256=load_sequence_sha256,
            )
        except SwapmodA1MiniDirectCanaryError as exc:
            raise SwapmodSequenceEditorError(exc.code, exc.message) from exc


def _parse_editable_actions(sequence_text: str, *, step: str) -> list[EditableSequenceAction]:
    actions: list[EditableSequenceAction] = []
    step_slug = "release" if step == RELEASE_PLATE else "load"
    label_prefix = "Release" if step == RELEASE_PLATE else "Load"
    for line_index, line in enumerate(sequence_text.splitlines(keepends=True)):
        code = line.split(";", 1)[0]
        executable_code = _mask_parenthesized_comments(code)
        if not _MOVE_COMMAND.match(executable_code):
            continue
        words = list(_WORD.finditer(executable_code))
        feedrate_words = [word for word in words if word.group(1).upper() == "F"]
        if len(feedrate_words) != 1:
            continue
        feedrate_word = feedrate_words[0]
        feedrate_text = feedrate_word.group(2)
        if not feedrate_text.isascii() or not feedrate_text.isdecimal():
            continue
        feedrate = int(feedrate_text)
        if not FEEDRATE_MIN <= feedrate <= FEEDRATE_MAX:
            continue

        targets = [
            f"{word.group(1).upper()}{word.group(2)}" for word in words if word.group(1).upper() in {"X", "Y", "Z", "E"}
        ]
        value_start, value_end = feedrate_word.span(2)
        skeleton = f"{code[:value_start]}<feedrate>{code[value_end:]}".strip().upper()
        digest = hashlib.sha256(skeleton.encode("utf-8")).hexdigest()[:10]
        ordinal = len(actions) + 1
        actions.append(
            EditableSequenceAction(
                action_id=f"{step_slug}-{ordinal:03d}-{digest}",
                label=f"{label_prefix} action {ordinal}",
                target=" ".join(targets) if targets else "Feedrate only",
                feedrate=feedrate,
                line_index=line_index,
                value_start=value_start,
                value_end=value_end,
            )
        )
        if len(actions) > MAX_EDITABLE_ACTIONS:
            raise SwapmodSequenceEditorError(
                "too_many_editable_actions",
                f"A sequence may expose at most {MAX_EDITABLE_ACTIONS} editable actions",
            )
    if not actions:
        raise SwapmodSequenceEditorError(
            "sequence_has_no_editable_actions",
            "The pinned sequence has no editable G0/G1 feedrates",
        )
    return actions


def _mask_parenthesized_comments(code: str) -> str:
    """Hide comment text while preserving offsets into the original line."""
    chars = list(code)
    depth = 0
    for index, char in enumerate(chars):
        if char == "(":
            depth += 1
            chars[index] = " "
        elif char == ")" and depth:
            chars[index] = " "
            depth -= 1
        elif depth:
            chars[index] = " "
    return "".join(chars)


def _render_candidate(
    sequence_text: str,
    actions: list[EditableSequenceAction],
    feedrates: dict[str, int],
) -> str:
    lines = sequence_text.splitlines(keepends=True)
    for action in actions:
        line = lines[action.line_index]
        lines[action.line_index] = (
            f"{line[: action.value_start]}{feedrates[action.action_id]}{line[action.value_end :]}"
        )
    return "".join(lines)


def _candidate_directory(sequence_root: str | Path | None) -> Path:
    if not sequence_root:
        raise SwapmodSequenceEditorError("sequence_not_configured", "Sequence root is not configured")
    root = Path(sequence_root).expanduser().resolve()
    if not root.is_dir():
        raise SwapmodSequenceEditorError("sequence_root_not_found", "Configured sequence root was not found")
    directory = root / SEQUENCE_CANDIDATE_DIRECTORY
    if directory.is_symlink():
        raise SwapmodSequenceEditorError(
            "candidate_directory_not_allowed",
            "Candidate directory must not be a symbolic link",
        )
    try:
        directory.mkdir(mode=0o700, exist_ok=True)
    except OSError as exc:
        raise SwapmodSequenceEditorError(
            "candidate_directory_write_failed",
            "Candidate directory could not be created",
        ) from exc
    resolved = directory.resolve()
    if not resolved.is_relative_to(root):
        raise SwapmodSequenceEditorError(
            "candidate_directory_not_allowed",
            "Candidate directory is outside the configured sequence root",
        )
    return directory


def _open_candidate_directory(directory: Path) -> int:
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise SwapmodSequenceEditorError(
            "candidate_directory_not_supported",
            "Candidate storage requires no-follow directory access",
        )
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        directory_fd = os.open(directory, flags)
    except OSError as exc:
        raise SwapmodSequenceEditorError(
            "candidate_directory_not_allowed",
            "Candidate directory could not be opened without following links",
        ) from exc
    try:
        os.fchmod(directory_fd, 0o700)
    except OSError as exc:
        os.close(directory_fd)
        raise SwapmodSequenceEditorError(
            "candidate_directory_write_failed",
            "Candidate directory permissions could not be secured",
        ) from exc
    return directory_fd


def _new_version_id(*, step: str, created_at: datetime) -> str:
    step_slug = "release" if step == RELEASE_PLATE else "load"
    timestamp = created_at.strftime("%Y%m%dT%H%M%S%fZ").lower()
    return f"a1mini-{step_slug}-{timestamp}-{uuid.uuid4().hex[:12]}"


def _write_candidate_pair(
    *,
    directory_fd: int,
    version_id: str,
    candidate_bytes: bytes,
    manifest: dict[str, object],
) -> None:
    candidate_name = f"{version_id}.gcode"
    manifest_name = f"{version_id}.json"
    candidate_created = False
    manifest_created = False
    try:
        _write_exclusive(directory_fd, candidate_name, candidate_bytes)
        candidate_created = True
        manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8")
        _write_exclusive(directory_fd, manifest_name, manifest_bytes)
        manifest_created = True
        os.fsync(directory_fd)
    except BaseException:
        if manifest_created:
            _unlink_candidate(directory_fd, manifest_name)
        if candidate_created:
            _unlink_candidate(directory_fd, candidate_name)
        raise


def _write_exclusive(directory_fd: int, name: str, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(fd, "wb") as handle:
            fd = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        _unlink_candidate(directory_fd, name)
        raise
    finally:
        if fd >= 0:
            os.close(fd)


def _unlink_candidate(directory_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=directory_fd)
    except OSError:
        pass


def _latest_candidate(sequence_root: str | Path | None, *, step: str) -> dict[str, object] | None:
    if not sequence_root:
        return None
    root = Path(sequence_root).expanduser().resolve()
    directory = root / SEQUENCE_CANDIDATE_DIRECTORY
    if not directory.is_dir() or directory.is_symlink():
        return None
    step_slug = "release" if step == RELEASE_PLATE else "load"
    manifests = sorted(directory.glob(f"a1mini-{step_slug}-*.json"), reverse=True)[:100]
    for manifest_path in manifests:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            version_id = str(manifest.get("version_id") or "")
            if not _VERSION_ID.fullmatch(version_id) or manifest_path.stem != version_id:
                continue
            if not _is_pending_candidate_manifest(manifest, step=step):
                continue
            candidate_bytes = (directory / f"{version_id}.gcode").read_bytes()
            if hashlib.sha256(candidate_bytes).hexdigest() != manifest.get("sha256"):
                continue
            return _public_candidate_manifest(manifest)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            continue
    return None


def _is_pending_candidate_manifest(manifest: dict[str, object], *, step: str) -> bool:
    if manifest.get("step") != step:
        return False
    if manifest.get("review_status") != SEQUENCE_REVIEW_PENDING:
        return False
    if manifest.get("active") is not False or manifest.get("activation_supported") is not False:
        return False
    if manifest.get("operator_review_required") is not True:
        return False
    if not isinstance(manifest.get("created_at"), str) or not isinstance(manifest.get("created_by"), str):
        return False
    if not _SHA256.fullmatch(str(manifest.get("base_sha256") or "")):
        return False
    if not _SHA256.fullmatch(str(manifest.get("sha256") or "")):
        return False

    actions = manifest.get("actions")
    if not isinstance(actions, list) or not 1 <= len(actions) <= MAX_EDITABLE_ACTIONS:
        return False
    action_ids: set[str] = set()
    for action in actions:
        if not isinstance(action, dict):
            return False
        action_id = action.get("action_id")
        feedrate = action.get("feedrate")
        if not isinstance(action_id, str) or not _VERSION_ID.fullmatch(action_id) or action_id in action_ids:
            return False
        if not isinstance(action.get("label"), str) or not isinstance(action.get("target"), str):
            return False
        if isinstance(feedrate, bool) or not isinstance(feedrate, int):
            return False
        if not FEEDRATE_MIN <= feedrate <= FEEDRATE_MAX:
            return False
        action_ids.add(action_id)
    return True


def _sanitize_audit_actor(created_by: str) -> str:
    value = created_by or "local-auth-disabled"
    return "".join(char if char.isprintable() else " " for char in value)[:128]


def _public_candidate_manifest(manifest: dict[str, object]) -> dict[str, object]:
    public_actions: list[dict[str, object]] = []
    actions = manifest.get("actions")
    if isinstance(actions, list):
        for action in actions:
            if isinstance(action, dict):
                public_actions.append(
                    {
                        "action_id": action.get("action_id"),
                        "label": action.get("label"),
                        "target": action.get("target"),
                        "feedrate": action.get("feedrate"),
                    }
                )
    return {
        "version_id": manifest.get("version_id"),
        "step": manifest.get("step"),
        "base_sha256": manifest.get("base_sha256"),
        "sha256": manifest.get("sha256"),
        "created_at": manifest.get("created_at"),
        "created_by": manifest.get("created_by"),
        "review_status": manifest.get("review_status"),
        "active": False,
        "activation_supported": False,
        "operator_review_required": True,
        "actions": public_actions,
    }


swapmod_sequence_editor_service = SwapmodSequenceEditorService()
