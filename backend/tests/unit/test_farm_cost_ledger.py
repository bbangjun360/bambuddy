"""WP-114 snapshot capture tests."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from backend.app.api.routes.settings import set_setting
from backend.app.core.config import settings
from backend.app.models.farm_cost_ledger import FarmCostLedgerSnapshot
from backend.app.models.print_log import PrintLogEntry
from backend.app.services import farm_cost_ledger
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "setting_name",
    (
        "farm_cost_ledger_machine_rate_per_hour_krw",
        "farm_cost_ledger_estimated_power_kw",
    ),
)
async def test_nonfinite_policy_rate_skips_snapshot_without_losing_print_log(
    db_session,
    monkeypatch,
    setting_name,
):
    _enable_policy(monkeypatch)
    await _configure_krw(db_session)
    monkeypatch.setattr(settings, setting_name, float("inf"))

    entry = await write_log_entry(db_session, status="completed", cost=500.0)
    await db_session.commit()

    assert await db_session.get(PrintLogEntry, entry.id) is not None
    assert await db_session.scalar(select(func.count(FarmCostLedgerSnapshot.id))) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actual_cost", "actual_grams"),
    (
        (float("inf"), 10.0),
        (-1.0, 10.0),
        (200.0, float("inf")),
        (200.0, -1.0),
        (200.0, float("nan")),
    ),
)
async def test_invalid_effective_material_rate_skips_snapshot_without_losing_print_log(
    db_session,
    printer_factory,
    archive_factory,
    monkeypatch,
    actual_cost,
    actual_grams,
):
    _enable_policy(monkeypatch)
    await _configure_krw(db_session)
    printer = await printer_factory()
    archive = await archive_factory(printer.id, with_run=False)

    entry = await write_log_entry(
        db_session,
        archive_id=archive.id,
        status="completed",
        filament_used_grams=actual_grams,
        cost=actual_cost,
    )
    await db_session.commit()

    assert await db_session.get(PrintLogEntry, entry.id) is not None
    assert await db_session.scalar(select(func.count(FarmCostLedgerSnapshot.id))) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("archive_field", "invalid_value", "missing_fields"),
    (
        (
            "filament_used_grams",
            -1.0,
            ("estimated_filament_grams", "estimated_material_cost"),
        ),
        (
            "filament_used_grams",
            float("inf"),
            ("estimated_filament_grams", "estimated_material_cost"),
        ),
        (
            "print_time_seconds",
            -1,
            (
                "estimated_duration_seconds",
                "estimated_energy_kwh",
                "estimated_energy_cost",
                "estimated_machine_cost",
            ),
        ),
    ),
)
async def test_invalid_archive_estimate_evidence_is_captured_as_missing(
    db_session,
    printer_factory,
    archive_factory,
    monkeypatch,
    archive_field,
    invalid_value,
    missing_fields,
):
    _enable_policy(monkeypatch)
    await _configure_krw(db_session)
    printer = await printer_factory()
    archive = await archive_factory(
        printer.id,
        with_run=False,
        filament_used_grams=100.0,
        print_time_seconds=7200,
    )
    setattr(archive, archive_field, invalid_value)
    await db_session.flush()

    await write_log_entry(
        db_session,
        archive_id=archive.id,
        status="completed",
        filament_used_grams=10.0,
        cost=200.0,
    )
    await db_session.commit()

    snapshot = await db_session.scalar(select(FarmCostLedgerSnapshot))
    assert snapshot is not None
    for field in missing_fields:
        assert getattr(snapshot, field) is None
    assert snapshot.estimated_total_cost is None


def test_timezone_aware_filter_boundary_normalizes_to_naive_utc():
    normalize = farm_cost_ledger._normalize_db_datetime
    kst = timezone(timedelta(hours=9))

    normalized = normalize(datetime(2026, 7, 14, 9, 30, tzinfo=kst))

    assert normalized == datetime(2026, 7, 14, 0, 30)
    assert normalized.tzinfo is None
    naive = datetime(2026, 7, 14, 0, 30)
    assert normalize(naive) == naive


@pytest.mark.asyncio
async def test_postgres_capture_scope_uses_archive_advisory_lock():
    lock_scope = farm_cost_ledger._lock_capture_scope
    db = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        execute=AsyncMock(),
    )
    entry = SimpleNamespace(id=99, archive_id=42)

    await lock_scope(db, entry)

    statement, params = db.execute.await_args.args
    assert str(statement) == "SELECT pg_advisory_xact_lock(11405, :scope_key)"
    assert params == {"scope_key": 42}


@pytest.mark.asyncio
async def test_postgres_unlinked_capture_uses_print_log_scope():
    lock_scope = farm_cost_ledger._lock_capture_scope
    db = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        execute=AsyncMock(),
    )

    await lock_scope(db, SimpleNamespace(id=99, archive_id=None))

    statement, params = db.execute.await_args.args
    assert str(statement) == "SELECT pg_advisory_xact_lock(11406, :scope_key)"
    assert params == {"scope_key": 99}


@pytest.mark.asyncio
async def test_sqlite_capture_scope_does_not_issue_postgres_sql():
    lock_scope = farm_cost_ledger._lock_capture_scope
    db = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
        execute=AsyncMock(),
    )

    await lock_scope(db, SimpleNamespace(id=99, archive_id=42))

    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_linked_log_locks_attempt_scope_before_insert(monkeypatch):
    events: list[object] = []

    class NestedTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class RecordingSession:
        def add(self, entry):
            events.append("add")
            self.entry = entry

        async def flush(self):
            events.append("flush")
            self.entry.id = 99

        def begin_nested(self):
            return NestedTransaction()

    async def record_archive_lock(_db, archive_id):
        events.append(("lock", archive_id))

    async def record_capture(_db, _entry, *, archive_scope_locked=False):
        events.append(("capture", archive_scope_locked))

    _enable_policy(monkeypatch)
    monkeypatch.setattr(
        farm_cost_ledger,
        "lock_cost_ledger_archive",
        record_archive_lock,
        raising=False,
    )
    monkeypatch.setattr(farm_cost_ledger, "capture_cost_snapshot", record_capture)

    await write_log_entry(RecordingSession(), archive_id=42, status="completed")

    assert events == [
        ("lock", 42),
        "add",
        "flush",
        ("capture", True),
    ]
