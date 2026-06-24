from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)

PRINT_HEALTH_OK = "PRINT_HEALTH_OK"
POSSIBLE_SPAGHETTI = "POSSIBLE_SPAGHETTI"
POSSIBLE_LAYER_SHIFT = "POSSIBLE_LAYER_SHIFT"
POSSIBLE_DETACHMENT = "POSSIBLE_DETACHMENT"
CAMERA_UNAVAILABLE = "CAMERA_UNAVAILABLE"
MONITORING_TIMEOUT = "MONITORING_TIMEOUT"
INVALID_EVENT_PAYLOAD = "INVALID_EVENT_PAYLOAD"
SHADOW_REVIEW_REQUIRED = "SHADOW_REVIEW_REQUIRED"

OBSERVED = "OBSERVED"
REVIEW_RECOMMENDED = "REVIEW_RECOMMENDED"
IGNORED_DUPLICATE = "IGNORED_DUPLICATE"
INVALID = "INVALID"
RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
SHADOW_ONLY = "SHADOW_ONLY"

EVENT_TYPES = frozenset(
    {
        PRINT_HEALTH_OK,
        POSSIBLE_SPAGHETTI,
        POSSIBLE_LAYER_SHIFT,
        POSSIBLE_DETACHMENT,
        CAMERA_UNAVAILABLE,
        MONITORING_TIMEOUT,
        INVALID_EVENT_PAYLOAD,
        SHADOW_REVIEW_REQUIRED,
    }
)
REVIEW_EVENT_TYPES = frozenset({POSSIBLE_SPAGHETTI, POSSIBLE_LAYER_SHIFT, POSSIBLE_DETACHMENT, SHADOW_REVIEW_REQUIRED})
RETRYABLE_EVENT_TYPES = frozenset({CAMERA_UNAVAILABLE, MONITORING_TIMEOUT})


class ObicoShadowService:
    def __init__(self) -> None:
        self._lock = RLock()
        self.clear()

    def clear(self) -> None:
        with self._lock:
            self._records: OrderedDict[str, dict[str, Any]] = OrderedDict()
            self._status_counts: Counter[str] = Counter()
            self._event_status_counts: Counter[tuple[str, str]] = Counter()
            self._invalid_events = 0
            self._duplicate_events = 0
            self._total_ingests = 0

    def ingest_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._total_ingests += 1
            normalized, error = self._normalize(payload)
            if error is not None:
                observation = self._invalid_observation(payload, error)
                self._store(observation)
                self._invalid_events += 1
                self._count(observation["event_type"], observation["status"])
                logger.info(
                    "Obico shadow event classified event_type=%s status=%s shadow_only=true",
                    observation["event_type"],
                    observation["status"],
                )
                return self._public(observation)

            event_id = normalized["event_id"]
            fingerprint = self._fingerprint(normalized)
            existing = self._records.get(event_id)
            if existing is not None:
                if existing.get("fingerprint") == fingerprint:
                    self._duplicate_events += 1
                    self._count(existing["event_type"], IGNORED_DUPLICATE)
                    duplicate = self._public(existing)
                    duplicate["status"] = IGNORED_DUPLICATE
                    duplicate["duplicate_of"] = existing["observation_id"]
                    duplicate["stored"] = False
                    logger.info(
                        "Obico shadow event classified event_type=%s status=%s shadow_only=true",
                        duplicate["event_type"],
                        duplicate["status"],
                    )
                    return duplicate
                observation = self._invalid_observation(payload, "duplicate event_id has different payload")
                self._store(observation)
                self._invalid_events += 1
                self._count(observation["event_type"], observation["status"])
                return self._public(observation)

            observation = self._observation_from_normalized(normalized, fingerprint)
            self._store(observation)
            self._count(observation["event_type"], observation["status"])
            logger.info(
                "Obico shadow event classified event_id=%s event_type=%s status=%s shadow_only=true",
                observation["event_id"],
                observation["event_type"],
                observation["status"],
            )
            return self._public(observation)

    def status_snapshot(self) -> dict[str, Any]:
        with self._lock:
            recent = [self._public(record) for record in list(self._records.values())[-10:]]
            return {
                "mode": SHADOW_ONLY,
                "stored_observations": len(self._records),
                "total_ingests": self._total_ingests,
                "duplicate_events": self._duplicate_events,
                "invalid_events": self._invalid_events,
                "status_counts": dict(sorted(self._status_counts.items())),
                "event_counts": {
                    f"{event_type}:{status}": count
                    for (event_type, status), count in sorted(self._event_status_counts.items())
                },
                "recent_observations": recent,
            }

    def render_metrics(self) -> str:
        with self._lock:
            lines = [
                "# HELP bambuddy_obico_shadow_events_total Shadow-mode Obico observations by event type and status.",
                "# TYPE bambuddy_obico_shadow_events_total counter",
            ]
            for (event_type, status), count in sorted(self._event_status_counts.items()):
                lines.append(
                    f'bambuddy_obico_shadow_events_total{{event_type="{_escape(event_type)}",status="{_escape(status)}"}} {count}'
                )
            lines.extend(
                [
                    "",
                    "# HELP bambuddy_obico_shadow_store_observations Current local shadow observation records.",
                    "# TYPE bambuddy_obico_shadow_store_observations gauge",
                    f"bambuddy_obico_shadow_store_observations {len(self._records)}",
                    "",
                    "# HELP bambuddy_obico_shadow_duplicates_total Duplicate shadow events ignored idempotently.",
                    "# TYPE bambuddy_obico_shadow_duplicates_total counter",
                    f"bambuddy_obico_shadow_duplicates_total {self._duplicate_events}",
                    "",
                ]
            )
            return "\n".join(lines)

    def _normalize(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        if not isinstance(payload, dict):
            return {}, "payload must be an object"
        event_id = _nonempty(payload.get("event_id"))
        event_type = _nonempty(payload.get("event_type"))
        printer_id = _nonempty(payload.get("printer_id"))
        if event_id is None:
            return {}, "missing event_id"
        if event_type is None:
            return {}, "missing event_type"
        if event_type not in EVENT_TYPES:
            return {}, "unknown event_type"
        if printer_id is None:
            return {}, "missing printer_id"
        confidence, confidence_error = _confidence(payload.get("confidence"))
        if confidence_error is not None:
            return {}, confidence_error
        metadata = payload.get("metadata")
        metadata_keys = sorted(str(key) for key in metadata.keys()) if isinstance(metadata, dict) else []
        return {
            "event_id": event_id,
            "event_type": event_type,
            "printer_id": printer_id,
            "print_id": _nonempty(payload.get("print_id")),
            "observed_at": _nonempty(payload.get("observed_at")) or _now_iso(),
            "confidence": confidence,
            "metadata_keys": metadata_keys,
        }, None

    def _observation_from_normalized(self, normalized: dict[str, Any], fingerprint: str) -> dict[str, Any]:
        event_type = normalized["event_type"]
        if event_type in REVIEW_EVENT_TYPES:
            status = REVIEW_RECOMMENDED
            recommendation = SHADOW_REVIEW_REQUIRED
            retryable = False
            error_category = None
        elif event_type in RETRYABLE_EVENT_TYPES:
            status = RETRYABLE_FAILURE
            recommendation = None
            retryable = True
            error_category = event_type
        else:
            status = OBSERVED
            recommendation = None
            retryable = False
            error_category = None
        return {
            "observation_id": self._observation_id(normalized["event_id"]),
            "event_id": normalized["event_id"],
            "event_type": event_type,
            "printer_id": normalized["printer_id"],
            "print_id": normalized.get("print_id"),
            "observed_at": normalized["observed_at"],
            "recorded_at": _now_iso(),
            "confidence": normalized.get("confidence"),
            "metadata_keys": normalized.get("metadata_keys", []),
            "status": status,
            "mode": SHADOW_ONLY,
            "shadow_only": True,
            "recommendation": recommendation,
            "retryable": retryable,
            "error_category": error_category,
            "printer_action": None,
            "queue_action": None,
            "bed_action": None,
            "erp_action": None,
            "duplicate_of": None,
            "stored": True,
            "fingerprint": fingerprint,
        }

    def _invalid_observation(self, payload: dict[str, Any], reason: str) -> dict[str, Any]:
        digest = self._fingerprint(payload)[:16]
        return {
            "observation_id": f"shadow-invalid:{digest}",
            "event_id": f"invalid:{digest}",
            "event_type": INVALID_EVENT_PAYLOAD,
            "printer_id": _nonempty(payload.get("printer_id")) if isinstance(payload, dict) else None,
            "print_id": None,
            "observed_at": _now_iso(),
            "recorded_at": _now_iso(),
            "confidence": None,
            "metadata_keys": [],
            "status": INVALID,
            "mode": SHADOW_ONLY,
            "shadow_only": True,
            "recommendation": None,
            "retryable": False,
            "error_category": INVALID_EVENT_PAYLOAD,
            "error_reason": reason,
            "printer_action": None,
            "queue_action": None,
            "bed_action": None,
            "erp_action": None,
            "duplicate_of": None,
            "stored": True,
            "fingerprint": digest,
        }

    def _store(self, observation: dict[str, Any]) -> None:
        self._records[observation["event_id"]] = observation

    def _count(self, event_type: str, status: str) -> None:
        self._status_counts[status] += 1
        self._event_status_counts[(event_type, status)] += 1

    def _public(self, observation: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in observation.items() if key != "fingerprint"}

    def _fingerprint(self, payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _observation_id(self, event_id: str) -> str:
        digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:16]
        return f"shadow:{digest}"


def _nonempty(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, int):
        return str(value)
    return None


def _confidence(value: Any) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, bool):
        return None, "confidence must be a number"
    if isinstance(value, int | float):
        confidence = float(value)
        if 0.0 <= confidence <= 1.0:
            return confidence, None
    return None, "confidence must be between 0 and 1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


obico_shadow_service = ObicoShadowService()
