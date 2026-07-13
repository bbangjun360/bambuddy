from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from math import isfinite
from typing import Any

from sqlalchemy import Numeric, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.archive import PrintArchive
from backend.app.models.farm_cost_ledger import FarmCostLedgerSnapshot
from backend.app.models.print_log import PrintLogEntry
from backend.app.schemas.farm_cost_ledger import (
    FarmCostLedgerItem,
    FarmCostLedgerResponse,
    FarmCostLedgerSummary,
)

logger = logging.getLogger(__name__)

FAILED_STATUSES = ("failed", "aborted")
CANCELLED_STATUSES = ("stopped", "cancelled", "skipped")
ATTEMPT_KINDS = ("original", "reprint", "unlinked")


@dataclass(frozen=True)
class CostPolicy:
    currency: str
    material_rate_per_kg: float | None
    energy_rate_per_kwh: float
    estimated_power_kw: float
    machine_rate_per_hour: float
    version: str

    @property
    def errors(self) -> list[str]:
        errors: list[str] = []
        if self.currency != "KRW":
            errors.append("currency_not_krw")
        if not isfinite(self.energy_rate_per_kwh) or self.energy_rate_per_kwh <= 0:
            errors.append("energy_rate_not_positive")
        if not isfinite(self.estimated_power_kw) or self.estimated_power_kw <= 0:
            errors.append("estimated_power_not_positive")
        if not isfinite(self.machine_rate_per_hour) or self.machine_rate_per_hour <= 0:
            errors.append("machine_rate_not_positive")
        if not self.version:
            errors.append("policy_version_missing")
        return errors


def _as_nonnegative_float(value: str | float | None) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if isfinite(parsed) and parsed >= 0 else None


def _money(value: float | Decimal | None) -> float | None:
    if value is None:
        return None
    try:
        return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return None


def _sum_money(*values: float | None) -> float | None:
    if any(value is None for value in values):
        return None
    return _money(sum(Decimal(str(value)) for value in values if value is not None))


def _sql_money(value: Any) -> Any:
    """Round one ledger row before SQL aggregation on SQLite and PostgreSQL."""
    return func.round(cast(value, Numeric(24, 8)), 2)


async def _load_policy(db: AsyncSession, entry: PrintLogEntry) -> CostPolicy:
    from backend.app.api.routes.settings import get_setting

    currency = ((await get_setting(db, "currency")) or "USD").strip().upper()
    energy_rate = _as_nonnegative_float(await get_setting(db, "energy_cost_per_kwh")) or 0.0
    default_material_rate = _as_nonnegative_float(await get_setting(db, "default_filament_cost"))
    effective_material_rate = default_material_rate
    if entry.cost is not None and entry.filament_used_grams and entry.filament_used_grams > 0:
        effective_material_rate = entry.cost * 1000.0 / entry.filament_used_grams

    return CostPolicy(
        currency=currency,
        material_rate_per_kg=effective_material_rate,
        energy_rate_per_kwh=energy_rate,
        estimated_power_kw=float(settings.farm_cost_ledger_estimated_power_kw),
        machine_rate_per_hour=float(settings.farm_cost_ledger_machine_rate_per_hour_krw),
        version=settings.farm_cost_ledger_policy_version.strip(),
    )


async def capture_cost_snapshot(
    db: AsyncSession,
    entry: PrintLogEntry,
) -> FarmCostLedgerSnapshot | None:
    """Capture immutable estimate/rate context without changing the run row."""
    if not settings.farm_actual_cost_ledger_enabled:
        return None

    existing = await db.scalar(
        select(FarmCostLedgerSnapshot).where(FarmCostLedgerSnapshot.print_log_entry_id == entry.id)
    )
    if existing is not None:
        return existing

    policy = await _load_policy(db, entry)
    if policy.errors:
        logger.warning(
            "farm_cost_ledger_snapshot_skipped print_log_entry_id=%s reasons=%s",
            entry.id,
            ",".join(policy.errors),
        )
        return None

    archive = await db.get(PrintArchive, entry.archive_id) if entry.archive_id is not None else None
    estimated_filament_grams = archive.filament_used_grams if archive is not None else None
    estimated_duration_seconds = archive.print_time_seconds if archive is not None else None

    attempt_number: int | None = None
    attempt_kind = "unlinked"
    if entry.archive_id is not None:
        attempt_number = int(
            await db.scalar(
                select(func.count(PrintLogEntry.id)).where(
                    PrintLogEntry.archive_id == entry.archive_id,
                    PrintLogEntry.id <= entry.id,
                )
            )
            or 1
        )
        attempt_kind = "original" if attempt_number == 1 else "reprint"

    estimated_material_cost = None
    if estimated_filament_grams is not None and policy.material_rate_per_kg is not None:
        estimated_material_cost = _money(estimated_filament_grams / 1000.0 * policy.material_rate_per_kg)

    estimated_energy_kwh = None
    estimated_energy_cost = None
    estimated_machine_cost = None
    if estimated_duration_seconds is not None:
        estimated_hours = estimated_duration_seconds / 3600.0
        estimated_energy_kwh = round(estimated_hours * policy.estimated_power_kw, 6)
        estimated_energy_cost = _money(estimated_energy_kwh * policy.energy_rate_per_kwh)
        estimated_machine_cost = _money(estimated_hours * policy.machine_rate_per_hour)

    snapshot = FarmCostLedgerSnapshot(
        print_log_entry_id=entry.id,
        archive_id=entry.archive_id,
        attempt_number=attempt_number,
        attempt_kind=attempt_kind,
        policy_version=policy.version,
        currency=policy.currency,
        material_rate_per_kg=policy.material_rate_per_kg,
        energy_rate_per_kwh=policy.energy_rate_per_kwh,
        estimated_power_kw=policy.estimated_power_kw,
        machine_rate_per_hour=policy.machine_rate_per_hour,
        estimated_filament_grams=estimated_filament_grams,
        estimated_duration_seconds=estimated_duration_seconds,
        estimated_material_cost=estimated_material_cost,
        estimated_energy_kwh=estimated_energy_kwh,
        estimated_energy_cost=estimated_energy_cost,
        estimated_machine_cost=estimated_machine_cost,
        estimated_total_cost=_sum_money(
            estimated_material_cost,
            estimated_energy_cost,
            estimated_machine_cost,
        ),
    )
    db.add(snapshot)
    await db.flush()
    logger.info(
        "farm_cost_ledger_snapshot_captured print_log_entry_id=%s attempt_kind=%s policy_version=%s",
        entry.id,
        attempt_kind,
        policy.version,
    )
    return snapshot


def _build_item(
    snapshot: FarmCostLedgerSnapshot,
    run: PrintLogEntry,
) -> FarmCostLedgerItem:
    actual_material_cost = _money(run.cost)
    actual_energy_cost = _money(run.energy_cost)
    actual_machine_cost = None
    if run.duration_seconds is not None:
        actual_machine_cost = _money(run.duration_seconds / 3600.0 * snapshot.machine_rate_per_hour)

    missing: list[str] = []
    if run.cost is None:
        missing.append("material")
    if run.energy_cost is None:
        missing.append("energy")
    if actual_machine_cost is None:
        missing.append("machine_time")

    actual_total_cost = _sum_money(actual_material_cost, actual_energy_cost, actual_machine_cost)
    variance_cost = None
    if actual_total_cost is not None and snapshot.estimated_total_cost is not None:
        variance_cost = _money(actual_total_cost - snapshot.estimated_total_cost)

    return FarmCostLedgerItem(
        id=snapshot.id,
        print_log_entry_id=run.id,
        archive_id=snapshot.archive_id,
        print_name=run.print_name,
        printer_name=run.printer_name,
        printer_id=run.printer_id,
        status=run.status,
        attempt_number=snapshot.attempt_number,
        attempt_kind=snapshot.attempt_kind,
        policy_version=snapshot.policy_version,
        currency=snapshot.currency,
        estimated_filament_grams=snapshot.estimated_filament_grams,
        estimated_duration_seconds=snapshot.estimated_duration_seconds,
        estimated_material_cost=snapshot.estimated_material_cost,
        estimated_energy_kwh=snapshot.estimated_energy_kwh,
        estimated_energy_cost=snapshot.estimated_energy_cost,
        estimated_machine_cost=snapshot.estimated_machine_cost,
        estimated_total_cost=snapshot.estimated_total_cost,
        actual_filament_grams=run.filament_used_grams,
        actual_duration_seconds=run.duration_seconds,
        actual_material_cost=actual_material_cost,
        actual_energy_kwh=run.energy_kwh,
        actual_energy_cost=actual_energy_cost,
        actual_machine_cost=actual_machine_cost,
        actual_total_cost=actual_total_cost,
        variance_cost=variance_cost,
        cost_complete=actual_total_cost is not None and snapshot.estimated_total_cost is not None,
        missing_actual_components=missing,
        captured_at=snapshot.captured_at,
        run_created_at=run.created_at,
    )


async def list_cost_ledger(
    db: AsyncSession,
    *,
    status: str | None = None,
    attempt_kind: str | None = None,
    printer_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> FarmCostLedgerResponse:
    conditions = []
    if status is not None:
        conditions.append(PrintLogEntry.status == status)
    if attempt_kind is not None:
        conditions.append(FarmCostLedgerSnapshot.attempt_kind == attempt_kind)
    if printer_id is not None:
        conditions.append(PrintLogEntry.printer_id == printer_id)
    if date_from is not None:
        conditions.append(FarmCostLedgerSnapshot.captured_at >= date_from)
    if date_to is not None:
        conditions.append(FarmCostLedgerSnapshot.captured_at <= date_to)

    join_condition = FarmCostLedgerSnapshot.print_log_entry_id == PrintLogEntry.id
    total = int(
        await db.scalar(
            select(func.count(FarmCostLedgerSnapshot.id)).join(PrintLogEntry, join_condition).where(*conditions)
        )
        or 0
    )

    rows = await db.execute(
        select(FarmCostLedgerSnapshot, PrintLogEntry)
        .join(PrintLogEntry, join_condition)
        .where(*conditions)
        .order_by(FarmCostLedgerSnapshot.captured_at.desc(), FarmCostLedgerSnapshot.id.desc())
        .offset(offset)
        .limit(limit)
    )
    items = [_build_item(snapshot, run) for snapshot, run in rows.all()]

    actual_material = _sql_money(PrintLogEntry.cost)
    actual_energy = _sql_money(PrintLogEntry.energy_cost)
    actual_machine = case(
        (
            PrintLogEntry.duration_seconds.isnot(None),
            _sql_money(PrintLogEntry.duration_seconds / 3600.0 * FarmCostLedgerSnapshot.machine_rate_per_hour),
        ),
        else_=None,
    )
    actual_components_complete = and_(
        PrintLogEntry.cost.isnot(None),
        PrintLogEntry.energy_cost.isnot(None),
        PrintLogEntry.duration_seconds.isnot(None),
    )
    actual_total = case(
        (
            actual_components_complete,
            actual_material + actual_energy + actual_machine,
        ),
        else_=None,
    )
    variance = case(
        (
            and_(
                actual_components_complete,
                FarmCostLedgerSnapshot.estimated_total_cost.isnot(None),
            ),
            _sql_money(actual_total - FarmCostLedgerSnapshot.estimated_total_cost),
        ),
        else_=None,
    )
    incomplete = or_(
        PrintLogEntry.cost.is_(None),
        PrintLogEntry.energy_cost.is_(None),
        PrintLogEntry.duration_seconds.is_(None),
        FarmCostLedgerSnapshot.estimated_total_cost.is_(None),
    )
    summary_row = (
        await db.execute(
            select(
                func.count(FarmCostLedgerSnapshot.id).label("total_run_count"),
                func.sum(case((PrintLogEntry.status == "completed", 1), else_=0)).label("completed_run_count"),
                func.sum(case((PrintLogEntry.status.in_(FAILED_STATUSES), 1), else_=0)).label("failed_run_count"),
                func.sum(case((PrintLogEntry.status.in_(CANCELLED_STATUSES), 1), else_=0)).label("cancelled_run_count"),
                func.sum(case((FarmCostLedgerSnapshot.attempt_kind == "original", 1), else_=0)).label(
                    "original_run_count"
                ),
                func.sum(case((FarmCostLedgerSnapshot.attempt_kind == "reprint", 1), else_=0)).label(
                    "reprint_run_count"
                ),
                func.sum(case((incomplete, 1), else_=0)).label("incomplete_run_count"),
                func.sum(func.coalesce(_sql_money(FarmCostLedgerSnapshot.estimated_material_cost), 0)).label(
                    "estimated_material_cost"
                ),
                func.sum(func.coalesce(_sql_money(FarmCostLedgerSnapshot.estimated_energy_cost), 0)).label(
                    "estimated_energy_cost"
                ),
                func.sum(func.coalesce(_sql_money(FarmCostLedgerSnapshot.estimated_machine_cost), 0)).label(
                    "estimated_machine_cost"
                ),
                func.sum(func.coalesce(_sql_money(FarmCostLedgerSnapshot.estimated_total_cost), 0)).label(
                    "estimated_total_cost"
                ),
                func.sum(func.coalesce(actual_material, 0)).label("actual_material_cost"),
                func.sum(func.coalesce(actual_energy, 0)).label("actual_energy_cost"),
                func.sum(func.coalesce(actual_machine, 0)).label("actual_machine_cost"),
                func.sum(func.coalesce(actual_total, 0)).label("actual_total_cost"),
                func.sum(func.coalesce(variance, 0)).label("variance_cost"),
                func.sum(
                    case(
                        (PrintLogEntry.status.in_(FAILED_STATUSES), func.coalesce(actual_total, 0)),
                        else_=0,
                    )
                ).label("failed_actual_total_cost"),
                func.sum(
                    case(
                        (
                            FarmCostLedgerSnapshot.attempt_kind == "reprint",
                            func.coalesce(actual_total, 0),
                        ),
                        else_=0,
                    )
                ).label("reprint_actual_total_cost"),
            )
            .join(PrintLogEntry, join_condition)
            .where(*conditions)
        )
    ).one()
    values = summary_row._mapping
    summary = FarmCostLedgerSummary(
        total_run_count=int(values["total_run_count"] or 0),
        completed_run_count=int(values["completed_run_count"] or 0),
        failed_run_count=int(values["failed_run_count"] or 0),
        cancelled_run_count=int(values["cancelled_run_count"] or 0),
        original_run_count=int(values["original_run_count"] or 0),
        reprint_run_count=int(values["reprint_run_count"] or 0),
        incomplete_run_count=int(values["incomplete_run_count"] or 0),
        estimated_material_cost=_money(values["estimated_material_cost"]) or 0.0,
        estimated_energy_cost=_money(values["estimated_energy_cost"]) or 0.0,
        estimated_machine_cost=_money(values["estimated_machine_cost"]) or 0.0,
        estimated_total_cost=_money(values["estimated_total_cost"]) or 0.0,
        actual_material_cost=_money(values["actual_material_cost"]) or 0.0,
        actual_energy_cost=_money(values["actual_energy_cost"]) or 0.0,
        actual_machine_cost=_money(values["actual_machine_cost"]) or 0.0,
        actual_total_cost=_money(values["actual_total_cost"]) or 0.0,
        variance_cost=_money(values["variance_cost"]) or 0.0,
        failed_actual_total_cost=_money(values["failed_actual_total_cost"]) or 0.0,
        reprint_actual_total_cost=_money(values["reprint_actual_total_cost"]) or 0.0,
    )
    return FarmCostLedgerResponse(
        currency="KRW",
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        summary=summary,
    )
