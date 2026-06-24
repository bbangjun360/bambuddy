from __future__ import annotations

import unittest

SYNTHETIC_SECRET = "wp070-synthetic-secret-not-for-logs"


def load_shadow_module():
    try:
        from backend.app.services import obico_shadow
    except ModuleNotFoundError as exc:
        raise AssertionError("missing backend.app.services.obico_shadow") from exc
    return obico_shadow


def healthy_event(**overrides):
    payload = {
        "event_id": "shadow-event-healthy-0001",
        "event_type": "PRINT_HEALTH_OK",
        "printer_id": "printer-fixture-001",
        "print_id": "print-fixture-cube-001",
        "observed_at": "2026-06-24T10:00:00Z",
        "confidence": 0.01,
        "metadata": {"scenario": "healthy"},
    }
    payload.update(overrides)
    return payload


class ObicoShadowServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_shadow_module()
        self.service = self.mod.ObicoShadowService()

    def test_valid_synthetic_event_is_recorded_shadow_only(self) -> None:
        observation = self.service.ingest_event(healthy_event())

        self.assertEqual(observation["event_id"], "shadow-event-healthy-0001")
        self.assertEqual(observation["event_type"], "PRINT_HEALTH_OK")
        self.assertEqual(observation["status"], "OBSERVED")
        self.assertEqual(observation["mode"], "SHADOW_ONLY")
        self.assertIs(observation["shadow_only"], True)
        self.assertIsNone(observation["printer_action"])
        self.assertIsNone(observation["queue_action"])
        self.assertIsNone(observation["bed_action"])
        self.assertIsNone(observation["erp_action"])
        self.assertEqual(self.service.status_snapshot()["stored_observations"], 1)

    def test_suspected_failure_becomes_review_recommendation_only(self) -> None:
        observation = self.service.ingest_event(
            healthy_event(
                event_id="shadow-event-spaghetti-0001",
                event_type="POSSIBLE_SPAGHETTI",
                confidence=0.92,
            )
        )

        self.assertEqual(observation["status"], "REVIEW_RECOMMENDED")
        self.assertEqual(observation["recommendation"], "SHADOW_REVIEW_REQUIRED")
        self.assertEqual(observation["mode"], "SHADOW_ONLY")
        self.assertIsNone(observation["printer_action"])
        self.assertIsNone(observation["queue_action"])
        self.assertIsNone(observation["bed_action"])
        self.assertIsNone(observation["erp_action"])

    def test_duplicate_event_is_idempotent(self) -> None:
        payload = healthy_event(event_id="shadow-event-idempotent-0001")
        first = self.service.ingest_event(payload)
        duplicate = self.service.ingest_event(payload)

        self.assertEqual(first["status"], "OBSERVED")
        self.assertEqual(duplicate["status"], "IGNORED_DUPLICATE")
        self.assertEqual(duplicate["duplicate_of"], first["observation_id"])
        self.assertEqual(self.service.status_snapshot()["stored_observations"], 1)

    def test_invalid_payload_is_recorded_safely_without_actions(self) -> None:
        observation = self.service.ingest_event({"event_type": "POSSIBLE_SPAGHETTI", "printer_id": ""})

        self.assertEqual(observation["event_type"], "INVALID_EVENT_PAYLOAD")
        self.assertEqual(observation["status"], "INVALID")
        self.assertEqual(observation["mode"], "SHADOW_ONLY")
        self.assertIs(observation["shadow_only"], True)
        self.assertIsNone(observation["printer_action"])
        self.assertIsNone(observation["queue_action"])
        self.assertIsNone(observation["bed_action"])
        self.assertIsNone(observation["erp_action"])
        self.assertEqual(self.service.status_snapshot()["invalid_events"], 1)

    def test_timeout_event_is_retryable_shadow_failure(self) -> None:
        observation = self.service.ingest_event(
            healthy_event(
                event_id="shadow-event-timeout-0001",
                event_type="MONITORING_TIMEOUT",
                confidence=None,
            )
        )

        self.assertEqual(observation["status"], "RETRYABLE_FAILURE")
        self.assertIs(observation["retryable"], True)
        self.assertEqual(observation["error_category"], "MONITORING_TIMEOUT")
        self.assertIsNone(observation["printer_action"])
        self.assertIsNone(observation["queue_action"])

    def test_logs_and_metrics_do_not_expose_synthetic_secret(self) -> None:
        payload = healthy_event(
            event_id="shadow-event-secret-probe-0001",
            event_type="POSSIBLE_DETACHMENT",
            metadata={"synthetic_token": SYNTHETIC_SECRET},
        )

        with self.assertLogs("backend.app.services.obico_shadow", level="INFO") as captured:
            self.service.ingest_event(payload)
        metrics = self.service.render_metrics()
        exposed = "\n".join(captured.output) + "\n" + metrics

        self.assertIn("POSSIBLE_DETACHMENT", metrics)
        self.assertIn("REVIEW_RECOMMENDED", metrics)
        self.assertNotIn(SYNTHETIC_SECRET, exposed)


if __name__ == "__main__":
    unittest.main()
