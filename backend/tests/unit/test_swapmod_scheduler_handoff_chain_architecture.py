from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEDULER = ROOT / "app/services/print_scheduler.py"


class SwapmodSchedulerHandoffChainArchitectureTest(unittest.TestCase):
    def test_scheduler_compares_both_gate_identities_before_upload_status_or_start(self) -> None:
        text = SCHEDULER.read_text(encoding="utf-8")

        queue_gate_index = text.index("scheduler_queue_readiness_binding_gate = await")
        identity_index = text.index("_scheduler_handoff_identity_blocked_reasons(", queue_gate_index)
        upload_index = text.index("upload_file_async", identity_index)
        status_index = text.index('item.status = "printing"', identity_index)
        clear_index = text.index("set_awaiting_plate_clear", identity_index)
        start_index = text.index("printer_manager.start_print", identity_index)

        self.assertLess(identity_index, upload_index)
        self.assertLess(identity_index, status_index)
        self.assertLess(identity_index, clear_index)
        self.assertLess(identity_index, start_index)
        self.assertIn("scheduler_handoff_source_print_run_mismatch", text)
        self.assertIn("scheduler_handoff_source_cycle_mismatch", text)


if __name__ == "__main__":
    unittest.main()
