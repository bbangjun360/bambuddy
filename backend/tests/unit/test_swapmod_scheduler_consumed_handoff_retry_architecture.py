from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEDULER_BINDING = ROOT / "app/services/swapmod_scheduler_queue_readiness_binding.py"
SCHEDULER = ROOT / "app/services/print_scheduler.py"


class SwapmodSchedulerConsumedHandoffRetryArchitectureTest(unittest.TestCase):
    def test_scheduler_binding_gate_blocks_consumed_bindings_before_scheduler_start(self) -> None:
        binding_text = SCHEDULER_BINDING.read_text(encoding="utf-8")
        scheduler_text = SCHEDULER.read_text(encoding="utf-8")

        consumed_check = binding_text.index("if binding.consumed_at is not None:")
        consumed_reason = binding_text.index('"queue_readiness_binding_consumed"', consumed_check)
        self.assertLess(consumed_check, consumed_reason)

        gate_index = scheduler_text.index("await evaluate_scheduler_queue_readiness_binding_gate(")
        ftp_settings_index = scheduler_text.index("get_ftp_retry_settings", gate_index)
        delete_index = scheduler_text.index("delete_file_async", gate_index)
        upload_index = scheduler_text.index("upload_file_async", gate_index)
        status_index = scheduler_text.index('item.status = "printing"', gate_index)
        clear_index = scheduler_text.index("set_awaiting_plate_clear", gate_index)
        start_index = scheduler_text.index("printer_manager.start_print", gate_index)
        self.assertLess(gate_index, ftp_settings_index)
        self.assertLess(gate_index, delete_index)
        self.assertLess(gate_index, upload_index)
        self.assertLess(gate_index, status_index)
        self.assertLess(gate_index, clear_index)
        self.assertLess(gate_index, start_index)


if __name__ == "__main__":
    unittest.main()
