"""Characterize the per-run cost records that WP-114 builds on."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.app.models.print_log import PrintLogEntry
from backend.app.services.print_log import write_log_entry


@pytest.mark.asyncio
async def test_failed_attempt_and_reprint_keep_separate_actual_cost_rows(
    db_session,
    printer_factory,
    archive_factory,
):
    """A reprint must not overwrite the failed attempt's actual costs."""
    printer = await printer_factory(name="Cost Ledger Test Printer")
    archive = await archive_factory(
        printer.id,
        with_run=False,
        print_name="Cost Ledger Part",
        filament_used_grams=100.0,
        print_time_seconds=7200,
    )
    started_at = datetime(2026, 7, 13, 9, 0, tzinfo=timezone.utc)

    failed = await write_log_entry(
        db_session,
        archive_id=archive.id,
        status="failed",
        print_name=archive.print_name,
        printer_name=printer.name,
        printer_id=printer.id,
        started_at=started_at,
        completed_at=started_at + timedelta(minutes=30),
        filament_used_grams=40.0,
        cost=800.0,
        energy_kwh=0.2,
        energy_cost=36.0,
        failure_reason="adhesionFailure",
    )
    reprint = await write_log_entry(
        db_session,
        archive_id=archive.id,
        status="completed",
        print_name=archive.print_name,
        printer_name=printer.name,
        printer_id=printer.id,
        started_at=started_at + timedelta(hours=1),
        completed_at=started_at + timedelta(hours=3),
        filament_used_grams=100.0,
        cost=2000.0,
        energy_kwh=0.7,
        energy_cost=126.0,
    )
    await db_session.commit()

    rows = list(
        (
            await db_session.execute(
                select(PrintLogEntry).where(PrintLogEntry.archive_id == archive.id).order_by(PrintLogEntry.id)
            )
        )
        .scalars()
        .all()
    )

    assert failed.id != reprint.id
    assert [(row.status, row.cost, row.energy_cost) for row in rows] == [
        ("failed", 800.0, 36.0),
        ("completed", 2000.0, 126.0),
    ]
    assert [row.duration_seconds for row in rows] == [1800, 7200]
    assert sum(row.cost or 0 for row in rows) == 2800.0
    assert sum(row.energy_cost or 0 for row in rows) == 162.0
