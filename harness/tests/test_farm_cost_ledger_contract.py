"""Static contract backstops for the default-off WP-114 ledger."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FarmCostLedgerContractTest(unittest.TestCase):
    def test_feature_defaults_are_fail_closed(self) -> None:
        config = (ROOT / "backend/app/core/config.py").read_text(encoding="utf-8")

        self.assertIn("farm_actual_cost_ledger_enabled: bool = False", config)
        self.assertIn("farm_cost_ledger_machine_rate_per_hour_krw: float = 0.0", config)
        self.assertIn("farm_cost_ledger_estimated_power_kw: float = 0.0", config)
        self.assertIn('farm_cost_ledger_policy_version: str = ""', config)

    def test_contract_is_read_only_and_stats_protected(self) -> None:
        route = (ROOT / "backend/app/api/routes/farm_cost_ledger.py").read_text(encoding="utf-8")

        self.assertIn('@router.get("",', route)
        self.assertIn("Permission.STATS_READ", route)
        for mutation in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
            self.assertNotIn(mutation, route)

    def test_ledger_does_not_cross_external_command_boundaries(self) -> None:
        files = [
            ROOT / "backend/app/api/routes/farm_cost_ledger.py",
            ROOT / "backend/app/models/farm_cost_ledger.py",
            ROOT / "backend/app/services/farm_cost_ledger.py",
        ]
        combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
        for token in (
            "bambu_mqtt",
            "bambu_ftp",
            "printer_manager",
            "print_scheduler",
            "PrintQueueItem",
            "ErpDraftWriteRecord",
            "requests.",
            "httpx.",
            "subprocess.",
            "socket.",
        ):
            with self.subTest(token=token):
                self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
