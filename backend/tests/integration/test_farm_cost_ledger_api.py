"""WP-114 read-only actual cost ledger API tests."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.config import settings
from backend.app.models.farm_cost_ledger import FarmCostLedgerSnapshot
from backend.app.models.print_log import PrintLogEntry


async def _seed_run(
    db_session,
    *,
    archive_id: int,
    printer_id: int,
    status: str,
    attempt_number: int,
    actual_material_cost: float | None,
    actual_energy_cost: float | None,
    actual_energy_kwh: float | None,
    duration_seconds: int | None,
    estimated_total_cost: float | None = 8036.0,
) -> None:
    created_at = datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc) + timedelta(hours=attempt_number)
    run = PrintLogEntry(
        archive_id=archive_id,
        print_name="Ledger Part",
        printer_name="Ledger Printer",
        printer_id=printer_id,
        status=status,
        duration_seconds=duration_seconds,
        filament_used_grams=40.0 if status == "failed" else 100.0,
        cost=actual_material_cost,
        energy_kwh=actual_energy_kwh,
        energy_cost=actual_energy_cost,
        created_at=created_at,
    )
    db_session.add(run)
    await db_session.flush()
    db_session.add(
        FarmCostLedgerSnapshot(
            print_log_entry_id=run.id,
            archive_id=archive_id,
            attempt_number=attempt_number,
            attempt_kind="original" if attempt_number == 1 else "reprint",
            policy_version="kr-farm-2026-07",
            currency="KRW",
            estimated_filament_grams=100.0,
            estimated_duration_seconds=7200,
            material_rate_per_kg=20000.0,
            energy_rate_per_kwh=180.0,
            estimated_power_kw=0.1,
            machine_rate_per_hour=3000.0,
            estimated_material_cost=2000.0,
            estimated_energy_kwh=0.2,
            estimated_energy_cost=36.0,
            estimated_machine_cost=6000.0,
            estimated_total_cost=estimated_total_cost,
            captured_at=created_at,
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_ledger_is_hidden_when_feature_is_disabled(async_client, monkeypatch):
    monkeypatch.setattr(settings, "farm_actual_cost_ledger_enabled", False)

    response = await async_client.get("/api/v1/farm-cost-ledger")

    assert response.status_code == 404
    assert "disabled" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ledger_reconciles_original_failed_and_reprint_costs(
    async_client,
    db_session,
    printer_factory,
    archive_factory,
    monkeypatch,
):
    monkeypatch.setattr(settings, "farm_actual_cost_ledger_enabled", True)
    printer = await printer_factory(name="Ledger Printer")
    archive = await archive_factory(printer.id, with_run=False)
    await _seed_run(
        db_session,
        archive_id=archive.id,
        printer_id=printer.id,
        status="completed",
        attempt_number=1,
        actual_material_cost=2200.0,
        actual_energy_cost=39.6,
        actual_energy_kwh=0.22,
        duration_seconds=7500,
    )
    await _seed_run(
        db_session,
        archive_id=archive.id,
        printer_id=printer.id,
        status="failed",
        attempt_number=2,
        actual_material_cost=800.0,
        actual_energy_cost=10.8,
        actual_energy_kwh=0.06,
        duration_seconds=1800,
    )
    await _seed_run(
        db_session,
        archive_id=archive.id,
        printer_id=printer.id,
        status="completed",
        attempt_number=3,
        actual_material_cost=2000.0,
        actual_energy_cost=36.0,
        actual_energy_kwh=0.2,
        duration_seconds=7200,
    )

    response = await async_client.get("/api/v1/farm-cost-ledger?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "KRW"
    assert body["total"] == 3
    assert [row["attempt_kind"] for row in body["items"]] == [
        "reprint",
        "reprint",
        "original",
    ]
    summary = body["summary"]
    assert summary["total_run_count"] == 3
    assert summary["failed_run_count"] == 1
    assert summary["reprint_run_count"] == 2
    assert summary["incomplete_run_count"] == 0
    assert summary["actual_material_cost"] == pytest.approx(5000.0)
    assert summary["actual_energy_cost"] == pytest.approx(86.4)
    assert summary["actual_machine_cost"] == pytest.approx(13750.0)
    assert summary["actual_total_cost"] == pytest.approx(18836.4)
    assert summary["failed_actual_total_cost"] == pytest.approx(2310.8)
    assert summary["reprint_actual_total_cost"] == pytest.approx(10346.8)


@pytest.mark.asyncio
async def test_ledger_summary_reconciles_to_rounded_row_amounts(
    async_client,
    db_session,
    printer_factory,
    archive_factory,
    monkeypatch,
):
    monkeypatch.setattr(settings, "farm_actual_cost_ledger_enabled", True)
    printer = await printer_factory()
    archive = await archive_factory(printer.id, with_run=False)

    for attempt_number in (1, 2):
        await _seed_run(
            db_session,
            archive_id=archive.id,
            printer_id=printer.id,
            status="completed",
            attempt_number=attempt_number,
            actual_material_cost=0.004,
            actual_energy_cost=0.0,
            actual_energy_kwh=0.0,
            duration_seconds=0,
            estimated_total_cost=0.0,
        )
    await _seed_run(
        db_session,
        archive_id=archive.id,
        printer_id=printer.id,
        status="completed",
        attempt_number=3,
        actual_material_cost=0.005,
        actual_energy_cost=0.005,
        actual_energy_kwh=0.0,
        duration_seconds=0,
        estimated_total_cost=0.0,
    )

    response = await async_client.get("/api/v1/farm-cost-ledger?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert [item["actual_material_cost"] for item in body["items"]] == [0.01, 0.0, 0.0]
    assert [item["actual_energy_cost"] for item in body["items"]] == [0.01, 0.0, 0.0]
    assert [item["actual_total_cost"] for item in body["items"]] == [0.02, 0.0, 0.0]
    assert body["summary"]["actual_material_cost"] == sum(item["actual_material_cost"] for item in body["items"])
    assert body["summary"]["actual_energy_cost"] == sum(item["actual_energy_cost"] for item in body["items"])
    assert body["summary"]["actual_total_cost"] == sum(item["actual_total_cost"] for item in body["items"])


@pytest.mark.asyncio
async def test_ledger_filters_reprints_and_marks_missing_energy_incomplete(
    async_client,
    db_session,
    printer_factory,
    archive_factory,
    monkeypatch,
):
    monkeypatch.setattr(settings, "farm_actual_cost_ledger_enabled", True)
    printer = await printer_factory()
    archive = await archive_factory(printer.id, with_run=False)
    await _seed_run(
        db_session,
        archive_id=archive.id,
        printer_id=printer.id,
        status="failed",
        attempt_number=2,
        actual_material_cost=500.0,
        actual_energy_cost=None,
        actual_energy_kwh=None,
        duration_seconds=900,
    )

    response = await async_client.get("/api/v1/farm-cost-ledger?attempt_kind=reprint&status=failed&limit=1&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["actual_total_cost"] is None
    assert body["items"][0]["variance_cost"] is None
    assert body["items"][0]["cost_complete"] is False
    assert body["items"][0]["missing_actual_components"] == ["energy"]
    assert body["summary"]["incomplete_run_count"] == 1
    assert body["summary"]["actual_material_cost"] == 500.0
    assert body["summary"]["actual_total_cost"] == 0.0


@pytest.mark.asyncio
async def test_ledger_summary_keeps_actual_total_when_estimate_is_incomplete(
    async_client,
    db_session,
    printer_factory,
    archive_factory,
    monkeypatch,
):
    monkeypatch.setattr(settings, "farm_actual_cost_ledger_enabled", True)
    printer = await printer_factory()
    archive = await archive_factory(printer.id, with_run=False)
    await _seed_run(
        db_session,
        archive_id=archive.id,
        printer_id=printer.id,
        status="completed",
        attempt_number=1,
        actual_material_cost=2000.0,
        actual_energy_cost=36.0,
        actual_energy_kwh=0.2,
        duration_seconds=7200,
        estimated_total_cost=None,
    )

    response = await async_client.get("/api/v1/farm-cost-ledger")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["actual_total_cost"] == 8036.0
    assert body["items"][0]["variance_cost"] is None
    assert body["items"][0]["cost_complete"] is False
    assert body["summary"]["incomplete_run_count"] == 1
    assert body["summary"]["actual_total_cost"] == 8036.0
    assert body["summary"]["variance_cost"] == 0.0
