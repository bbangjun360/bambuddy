"""Structural safety checks for the WP-114 farm extension."""

from pathlib import Path

from backend.app.core.config import settings
from backend.app.core.database import Base

ROOT = Path(__file__).resolve().parents[2]
FARM_FILES = [
    ROOT / "app/api/routes/farm_cost_ledger.py",
    ROOT / "app/models/farm_cost_ledger.py",
    ROOT / "app/schemas/farm_cost_ledger.py",
    ROOT / "app/services/farm_cost_ledger.py",
]


def test_actual_cost_ledger_is_disabled_and_unpriced_by_default():
    assert settings.farm_actual_cost_ledger_enabled is False
    assert settings.farm_cost_ledger_machine_rate_per_hour_krw == 0.0
    assert settings.farm_cost_ledger_estimated_power_kw == 0.0
    assert settings.farm_cost_ledger_policy_version == ""


def test_snapshot_table_is_registered_with_one_row_per_print_log_entry():
    table = Base.metadata.tables["farm_cost_ledger_snapshots"]

    assert table.c.print_log_entry_id.foreign_keys
    assert any(constraint.name == "uq_farm_cost_ledger_print_log_entry" for constraint in table.constraints)


def test_route_is_read_only_and_stats_permission_protected():
    route_source = (ROOT / "app/api/routes/farm_cost_ledger.py").read_text(encoding="utf-8")

    assert '@router.get("",' in route_source
    assert "@router.post" not in route_source
    assert "@router.put" not in route_source
    assert "@router.patch" not in route_source
    assert "@router.delete" not in route_source
    assert "RequirePermissionIfAuthEnabled(Permission.STATS_READ)" in route_source


def test_farm_cost_ledger_has_no_external_or_printer_command_boundary():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in FARM_FILES)
    forbidden = (
        "bambu_mqtt",
        "bambu_ftp",
        "printer_manager",
        "print_scheduler",
        "PrintQueueItem",
        "ErpDraftWriteRecord",
        "ErpReadOnlyClient",
        "requests.",
        "httpx.",
        "subprocess.",
        "socket.",
    )

    for token in forbidden:
        assert token not in combined
