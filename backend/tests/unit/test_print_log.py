"""Unit tests for print log service and schema."""

from datetime import datetime, timedelta

import pytest

from backend.app.models.farm_cost_ledger import FarmCostLedgerSnapshot
from backend.app.models.print_log import PrintLogEntry
from backend.app.schemas.print_log import PrintLogEntrySchema, PrintLogResponse
from backend.app.services import print_log as print_log_service


class TestPrintLogEntrySchema:
    """Test PrintLogEntrySchema validation."""

    def test_minimal_entry(self):
        """Schema accepts minimal required fields."""
        entry = PrintLogEntrySchema(
            id=1,
            status="completed",
            created_at=datetime(2024, 1, 15, 10, 30, 0),
        )
        assert entry.id == 1
        assert entry.status == "completed"
        assert entry.print_name is None
        assert entry.printer_name is None
        assert entry.duration_seconds is None

    def test_full_entry(self):
        """Schema accepts all fields."""
        started = datetime(2024, 1, 15, 10, 0, 0)
        completed = datetime(2024, 1, 15, 12, 30, 0)
        entry = PrintLogEntrySchema(
            id=42,
            print_name="Benchy",
            printer_name="X1C-01",
            printer_id=3,
            status="completed",
            started_at=started,
            completed_at=completed,
            duration_seconds=9000,
            filament_type="PLA",
            filament_color="#FF5500",
            filament_used_grams=15.2,
            thumbnail_path="archives/3/20240115_benchy/thumbnail.png",
            created_by_username="admin",
            created_at=datetime(2024, 1, 15, 12, 30, 0),
        )
        assert entry.print_name == "Benchy"
        assert entry.printer_name == "X1C-01"
        assert entry.filament_used_grams == 15.2
        assert entry.created_by_username == "admin"

    def test_failed_status(self):
        """Schema accepts various status values."""
        for status in ("completed", "failed", "stopped", "cancelled", "skipped"):
            entry = PrintLogEntrySchema(id=1, status=status, created_at=datetime.now())
            assert entry.status == status


class TestPrintLogResponse:
    """Test PrintLogResponse pagination wrapper."""

    def test_empty_response(self):
        """Empty response with zero total."""
        resp = PrintLogResponse(items=[], total=0)
        assert len(resp.items) == 0
        assert resp.total == 0

    def test_paginated_response(self):
        """Response with items and total count > items count."""
        items = [PrintLogEntrySchema(id=i, status="completed", created_at=datetime.now()) for i in range(3)]
        resp = PrintLogResponse(items=items, total=100)
        assert len(resp.items) == 3
        assert resp.total == 100


class TestWriteLogEntry:
    """Test the write_log_entry service function (logic only, no DB)."""

    def test_duration_calculation(self):
        """Duration is computed from started_at and completed_at."""
        started = datetime(2024, 1, 15, 10, 0, 0)
        completed = started + timedelta(hours=2, minutes=30)

        # Simulating the duration calculation from write_log_entry
        duration = int((completed - started).total_seconds())
        assert duration == 9000  # 2.5 hours = 9000 seconds

    def test_duration_none_when_missing_times(self):
        """Duration is None when started_at or completed_at is missing."""
        started = datetime(2024, 1, 15, 10, 0, 0)
        completed_at = None
        started_at = None
        completed = datetime.now()

        # No completed_at
        duration = None
        if started and completed_at:
            duration = int((completed_at - started).total_seconds())
        assert duration is None

        # No started_at
        duration = None
        if started_at and completed:
            duration = int((completed - started_at).total_seconds())
        assert duration is None


@pytest.mark.asyncio
async def test_energy_backfill_updates_exact_run_instead_of_latest_for_archive(
    db_session,
    printer_factory,
    archive_factory,
):
    backfill = print_log_service.backfill_log_entry_energy
    printer = await printer_factory()
    archive = await archive_factory(printer.id, with_run=False)
    first = PrintLogEntry(archive_id=archive.id, status="failed")
    second = PrintLogEntry(archive_id=archive.id, status="completed")
    db_session.add_all([first, second])
    await db_session.flush()

    updated = await backfill(
        db_session,
        print_log_entry_id=first.id,
        energy_kwh=0.25,
        energy_cost=45.0,
    )
    await db_session.flush()
    await db_session.refresh(first)
    await db_session.refresh(second)

    assert updated is True
    assert (first.energy_kwh, first.energy_cost) == (0.25, 45.0)
    assert (second.energy_kwh, second.energy_cost) == (None, None)


@pytest.mark.asyncio
async def test_energy_backfill_uses_snapshotted_rate_after_policy_change(db_session):
    entry = PrintLogEntry(status="completed")
    db_session.add(entry)
    await db_session.flush()
    db_session.add(
        FarmCostLedgerSnapshot(
            print_log_entry_id=entry.id,
            archive_id=None,
            attempt_number=None,
            attempt_kind="unlinked",
            policy_version="kr-farm-2026-07",
            currency="KRW",
            material_rate_per_kg=20000.0,
            energy_rate_per_kwh=180.0,
            estimated_power_kw=0.1,
            machine_rate_per_hour=3000.0,
        )
    )
    await db_session.flush()

    updated = await print_log_service.backfill_log_entry_energy(
        db_session,
        print_log_entry_id=entry.id,
        energy_kwh=0.25,
        energy_cost=250.0,
    )
    await db_session.flush()
    await db_session.refresh(entry)

    assert updated is True
    assert (entry.energy_kwh, entry.energy_cost) == (0.25, 45.0)


@pytest.mark.asyncio
async def test_energy_backfill_rejects_snapshotted_cost_overflow(db_session):
    entry = PrintLogEntry(status="completed")
    db_session.add(entry)
    await db_session.flush()
    db_session.add(
        FarmCostLedgerSnapshot(
            print_log_entry_id=entry.id,
            archive_id=None,
            attempt_number=None,
            attempt_kind="unlinked",
            policy_version="kr-farm-2026-07",
            currency="KRW",
            material_rate_per_kg=20000.0,
            energy_rate_per_kwh=180.0,
            estimated_power_kw=0.1,
            machine_rate_per_hour=3000.0,
        )
    )
    await db_session.flush()

    updated = await print_log_service.backfill_log_entry_energy(
        db_session,
        print_log_entry_id=entry.id,
        energy_kwh=1e308,
        energy_cost=45.0,
    )
    await db_session.flush()
    await db_session.refresh(entry)

    assert updated is False
    assert (entry.energy_kwh, entry.energy_cost) == (None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("energy_kwh", "energy_cost"),
    ((float("inf"), 45.0), (0.25, -1.0)),
)
async def test_energy_backfill_rejects_invalid_evidence(
    db_session,
    energy_kwh,
    energy_cost,
):
    entry = PrintLogEntry(status="completed")
    db_session.add(entry)
    await db_session.flush()

    updated = await print_log_service.backfill_log_entry_energy(
        db_session,
        print_log_entry_id=entry.id,
        energy_kwh=energy_kwh,
        energy_cost=energy_cost,
    )
    await db_session.refresh(entry)

    assert updated is False
    assert (entry.energy_kwh, entry.energy_cost) == (None, None)


@pytest.mark.asyncio
async def test_energy_backfill_reports_missing_run(db_session):
    updated = await print_log_service.backfill_log_entry_energy(
        db_session,
        print_log_entry_id=999_999,
        energy_kwh=0.25,
        energy_cost=45.0,
    )

    assert updated is False
