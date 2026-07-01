from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app/services/swapmod_scheduler_handoff_diagnostics.py"
ROUTE = ROOT / "app/api/routes/swapmod_state_machine.py"
CONFIG = ROOT / "app/core/config.py"
SCHEDULER_NEXT_PRINT_GATE = ROOT / "app/services/swapmod_scheduler_next_print_gate.py"
SWAPMOD_NEXT_PRINT_GATE = ROOT / "app/services/swapmod_next_print_gate.py"
SCHEDULER_QUEUE_READINESS_BINDING = ROOT / "app/services/swapmod_scheduler_queue_readiness_binding.py"
SWAPMOD_QUEUE_READINESS_BINDING = ROOT / "app/services/swapmod_queue_readiness_binding.py"
BLOCKER_REASON_PATTERN = re.compile(
    r'blocked_reasons=\["([^"]+)"\]'
    r'|(?:reasons|identity_blocked_reasons|blocked_reasons)\.append\("([^"]+)"\)'
)


class SwapmodSchedulerHandoffDiagnosticsArchitectureTest(unittest.TestCase):
    def test_existing_scheduler_gate_flags_remain_default_off(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")

        self.assertIn("farm_swapmod_scheduler_next_print_gate_enabled: bool = False", text)
        self.assertIn("farm_swapmod_queue_readiness_binding_enabled: bool = False", text)
        self.assertIn("farm_swapmod_scheduler_queue_readiness_binding_enabled: bool = False", text)
        self.assertIn("farm_bed_automation_enabled: bool = False", text)

    def test_service_exists_and_reuses_existing_scheduler_gates(self) -> None:
        self.assertTrue(SERVICE.exists(), f"missing {SERVICE}")
        text = SERVICE.read_text(encoding="utf-8")

        self.assertIn("evaluate_scheduler_next_print_gate", text)
        self.assertIn("evaluate_scheduler_queue_readiness_binding_gate", text)
        self.assertIn("scheduler_handoff_source_print_run_mismatch", text)
        self.assertIn("scheduler_handoff_source_cycle_mismatch", text)
        self.assertIn("diagnostics_summary", text)
        self.assertIn("blocked_reason_sources", text)
        self.assertIn("blocked_reason_catalog", text)
        self.assertIn("primary_operator_action", text)
        self.assertIn("blocked_reason_details", text)
        self.assertIn("handoff_identity_status", text)

    def test_blocked_reason_catalog_covers_current_gate_emitters(self) -> None:
        from backend.app.services.swapmod_scheduler_handoff_diagnostics import (
            swapmod_scheduler_handoff_diagnostics_blocked_reason_catalog,
        )

        catalog = swapmod_scheduler_handoff_diagnostics_blocked_reason_catalog()
        catalog_reasons = {
            source: {entry["reason"] for entry in entries}
            for source, entries in catalog["sources"].items()
        }

        expected_by_source = {
            "scheduler_next_print_gate": _emitted_blocker_reasons(
                SCHEDULER_NEXT_PRINT_GATE,
                SWAPMOD_NEXT_PRINT_GATE,
            ),
            "scheduler_queue_readiness_binding_gate": _emitted_blocker_reasons(
                SCHEDULER_QUEUE_READINESS_BINDING,
                SWAPMOD_QUEUE_READINESS_BINDING,
            ),
            "handoff_identity": _emitted_blocker_reasons(SERVICE),
        }
        for source, emitted_reasons in expected_by_source.items():
            with self.subTest(source=source):
                missing_reasons = emitted_reasons - catalog_reasons[source]
                self.assertEqual(missing_reasons, set())

    def test_service_does_not_import_scheduler_dispatch_or_external_clients(self) -> None:
        text = SERVICE.read_text(encoding="utf-8") if SERVICE.exists() else ""
        forbidden = (
            "print_scheduler",
            "PrintScheduler",
            "_start_print",
            "consume_scheduler_queue_readiness_binding",
            "printer_manager",
            "bambu_mqtt",
            "bambu_ftp",
            "upload_file_async",
            "delete_file_async",
            "with_ftp_retry",
            "cache_3mf_download",
            "spawn_background_task",
            "background_dispatch",
            "erp_draft_write",
            "obico_shadow",
            "send_gcode",
            "db.commit",
            "db.flush",
            "item.status",
            "started_at",
            "HTTPConnection",
            "HTTPSConnection",
            "httpx",
            "requests",
            "socket",
            "serial",
            "gpio",
            "usb",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, text)


    def test_api_route_is_read_only_and_reuses_diagnostics_service(self) -> None:
        text = ROUTE.read_text(encoding="utf-8")

        self.assertIn("evaluate_swapmod_scheduler_handoff_diagnostics", text)
        self.assertIn("@router.get(\"/scheduler-handoff-diagnostics\")", text)
        handler = text.split("async def get_swapmod_scheduler_handoff_diagnostics(", 1)[1].split("\n\n@router", 1)[0]
        self.assertIn("Permission.PRINTERS_READ", handler)
        self.assertNotIn("Permission.PRINTERS_CONTROL", handler)
        self.assertNotIn("_require_enabled()", handler)
        self.assertNotIn("_require_next_print_gate_enabled()", handler)
        self.assertNotIn("_require_queue_readiness_binding_enabled()", handler)
        forbidden = (
            "_start_print",
            "consume_scheduler_queue_readiness_binding",
            "printer_manager",
            "bambu_mqtt",
            "bambu_ftp",
            "upload_file_async",
            "delete_file_async",
            "with_ftp_retry",
            "cache_3mf_download",
            "spawn_background_task",
            "background_dispatch",
            "erp_draft_write",
            "obico_shadow",
            "send_gcode",
            "db.commit",
            "db.flush",
            "item.status",
            "started_at",
            "HTTPConnection",
            "HTTPSConnection",
            "httpx",
            "requests",
            "socket",
            "serial",
            "gpio",
            "usb",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, handler)


    def test_status_api_route_is_read_only_and_does_not_open_handler_db_session(self) -> None:
        text = ROUTE.read_text(encoding="utf-8")

        self.assertIn("@router.get(\"/scheduler-handoff-diagnostics/status\")", text)
        handler = text.split("async def get_swapmod_scheduler_handoff_diagnostics_status", 1)[1].split(
            "\n\n@router", 1
        )[0]
        self.assertIn("Permission.PRINTERS_READ", handler)
        self.assertNotIn("Permission.PRINTERS_CONTROL", handler)
        self.assertNotIn("Depends(get_db)", handler)
        self.assertNotIn("AsyncSession", handler)
        self.assertNotIn("evaluate_swapmod_scheduler_handoff_diagnostics", handler)
        self.assertIn("required_query_parameters", handler)
        self.assertIn("required_permission", handler)
        self.assertIn("response_contract_version", handler)
        self.assertIn("diagnostics_summary_contract_version", handler)
        self.assertIn("blocked_reason_details_contract_version", handler)
        self.assertIn("supported_summary_fields", handler)
        self.assertIn("supported_blocked_reason_detail_fields", handler)
        self.assertIn("supported_gate_statuses", handler)
        self.assertIn("supported_summary_boolean_fields", handler)
        self.assertIn("supported_summary_count_fields", handler)
        self.assertIn("supported_summary_nullable_fields", handler)
        self.assertIn("supported_summary_collection_fields", handler)
        self.assertIn("supported_handoff_identity_statuses", handler)
        self.assertIn("supported_blocked_reason_sources", handler)
        self.assertIn("blocked_reason_catalog", handler)
        self.assertIn("mutates_state", handler)
        forbidden = (
            "_start_print",
            "consume_scheduler_queue_readiness_binding",
            "printer_manager",
            "bambu_mqtt",
            "bambu_ftp",
            "send_gcode",
            "db.commit",
            "db.flush",
            "item.status",
            "started_at",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, handler)


def _emitted_blocker_reasons(*paths: Path) -> set[str]:
    emitted: set[str] = set()
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for match in BLOCKER_REASON_PATTERN.finditer(text):
            emitted.add(next(group for group in match.groups() if group))
    return emitted


if __name__ == "__main__":
    unittest.main()
