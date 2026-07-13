"""Failure-path tests for the optional WP-114 print-log hook."""

from sqlalchemy import func, select

from backend.app.core.config import settings
from backend.app.models.farm_cost_ledger import FarmCostLedgerSnapshot
from backend.app.models.print_log import PrintLogEntry
from backend.app.services import farm_cost_ledger
from backend.app.services.print_log import write_log_entry


async def test_snapshot_exception_never_removes_canonical_print_log(db_session, monkeypatch):
    monkeypatch.setattr(settings, "farm_actual_cost_ledger_enabled", True)

    async def fail_capture(*_args, **_kwargs):
        raise RuntimeError("synthetic snapshot failure")

    monkeypatch.setattr(farm_cost_ledger, "capture_cost_snapshot", fail_capture)

    entry = await write_log_entry(db_session, status="failed", cost=125.0)
    await db_session.commit()

    assert await db_session.get(PrintLogEntry, entry.id) is not None
    assert await db_session.scalar(select(func.count(FarmCostLedgerSnapshot.id))) == 0
