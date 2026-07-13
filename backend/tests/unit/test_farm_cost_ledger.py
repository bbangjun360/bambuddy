"""WP-114 snapshot capture tests."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from backend.app.api.routes.settings import set_setting
from backend.app.core.config import settings
from backend.app.models.farm_cost_ledger import FarmCostLedgerSnapshot
from backend.app.models.print_log import PrintLogEntry
from backend.app.services.farm_cost_ledger import capture_cost_snapshot
from backend.app.services.print_log import write_log_entry


async def _configure_krw(db_session) -> None:
    await set_setting(db_session, "currency", "KRW")
    await set_setting(db_session, "default_filament_cost", "20000")
    await set_setting(db_session, "energy_cost_per_kwh", "180")
    await db_session.commit()


def _enable_policy(monkeypatch) -> None:
    monkeypatch.setattr(settings, "farm_actual_cost_ledger_enabled", True)
    monkeypatch.setattr(settings, "farm_cost_ledger_machine_rate_per_hour_krw", 3000.0)
    monkeypatch.setattr(settings, "farm_cost_ledger_estimated_power_kw", 0.1)
    monkeypatch.setattr(settings, "farm_cost_ledger_policy_version", "kr-farm-2026-07")


@pytest.mark.asyncio
async def test_capture_snapshots_original_and_reprint_with_versioned_krw_policy(
    db_session,
    printer_factory,
    archive_factory,
    monkeypatch,
):
    _enable_policy(monkeypatch)
    await _configure_krw(db_session)
    printer = await printer_factory(name="Ledger Printer")
    archive = await archive_factory(
        printer.id,
        with_run=False,
        print_name="Ledger Part",
        filament_used_grams=100.0,
        print_time_seconds=7200,
    )
    started = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)

    await write_log_entry(
        db_session,
        archive_id=archive.id,
        status="failed",
        printer_id=printer.id,
        started_at=started,
        completed_at=started + timedelta(minutes=30),
        filament_used_grams=40.0,
        cost=800.0,
        energy_kwh=0.06,
        energy_cost=10.8,
    )
    await write_log_entry(
        db_session,
        archive_id=archive.id,
        status="completed",
        printer_id=printer.id,
        started_at=started + timedelta(hours=1),
        completed_at=started + timedelta(hours=3),
        filament_used_grams=100.0,
        cost=2000.0,
        energy_kwh=0.2,
        energy_cost=36.0,
    )
    await db_session.commit()

    snapshots = list(
        (await db_session.execute(select(FarmCostLedgerSnapshot).order_by(FarmCostLedgerSnapshot.print_log_entry_id)))
        .scalars()
        .all()
    )

    assert [(row.attempt_number, row.attempt_kind) for row in snapshots] == [
        (1, "original"),
        (2, "reprint"),
    ]
    assert snapshots[0].currency == "KRW"
    assert snapshots[0].policy_version == "kr-farm-2026-07"
    assert snapshots[0].material_rate_per_kg == 20000.0
    assert snapshots[0].energy_rate_per_kwh == 180.0
    assert snapshots[0].machine_rate_per_hour == 3000.0
    assert snapshots[0].estimated_material_cost == 2000.0
    assert snapshots[0].estimated_energy_kwh == 0.2
    assert snapshots[0].estimated_energy_cost == 36.0
    assert snapshots[0].estimated_machine_cost == 6000.0
    assert snapshots[0].estimated_total_cost == 8036.0


@pytest.mark.asyncio
async def test_capture_is_idempotent_for_one_print_log_entry(
    db_session,
    printer_factory,
    archive_factory,
    monkeypatch,
):
    _enable_policy(monkeypatch)
    await _configure_krw(db_session)
    printer = await printer_factory()
    archive = await archive_factory(printer.id, with_run=False)
    entry = await write_log_entry(
        db_session,
        archive_id=archive.id,
        status="completed",
        printer_id=printer.id,
        filament_used_grams=50.0,
        cost=1000.0,
    )

    first = await capture_cost_snapshot(db_session, entry)
    second = await capture_cost_snapshot(db_session, entry)
    await db_session.commit()

    assert first is not None
    assert second is not None
    assert first.id == second.id
    count = await db_session.scalar(select(func.count(FarmCostLedgerSnapshot.id)))
    assert count == 1


@pytest.mark.asyncio
async def test_disabled_feature_keeps_print_log_without_snapshot(
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "farm_actual_cost_ledger_enabled", False)

    entry = await write_log_entry(db_session, status="completed", cost=500.0)
    await db_session.commit()

    assert await db_session.get(PrintLogEntry, entry.id) is not None
    assert await db_session.scalar(select(func.count(FarmCostLedgerSnapshot.id))) == 0


@pytest.mark.asyncio
async def test_non_krw_configuration_skips_snapshot_without_losing_print_log(
    db_session,
    monkeypatch,
):
    _enable_policy(monkeypatch)
    await set_setting(db_session, "currency", "USD")
    await set_setting(db_session, "default_filament_cost", "25")
    await set_setting(db_session, "energy_cost_per_kwh", "0.15")
    await db_session.commit()

    entry = await write_log_entry(db_session, status="failed", cost=1.25)
    await db_session.commit()

    assert await db_session.get(PrintLogEntry, entry.id) is not None
    assert await db_session.scalar(select(func.count(FarmCostLedgerSnapshot.id))) == 0
