"""Service for writing independent print log entries.

Log entries are written to a separate table and never touch archives or queue items.
"""

import logging
from datetime import datetime
from math import isfinite

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.models.print_log import PrintLogEntry

logger = logging.getLogger(__name__)


async def backfill_log_entry_energy(
    db: AsyncSession,
    *,
    print_log_entry_id: int,
    energy_kwh: float,
    energy_cost: float,
) -> bool:
    """Attach delayed smart-plug evidence to the exact completed run."""
    if not isfinite(energy_kwh) or energy_kwh < 0 or not isfinite(energy_cost) or energy_cost < 0:
        logger.warning(
            "print_log_energy_backfill_rejected print_log_entry_id=%s",
            print_log_entry_id,
        )
        return False

    entry = await db.get(PrintLogEntry, print_log_entry_id)
    if entry is None:
        logger.warning(
            "print_log_energy_backfill_missing print_log_entry_id=%s",
            print_log_entry_id,
        )
        return False

    effective_energy_cost = energy_cost
    from backend.app.models.farm_cost_ledger import FarmCostLedgerSnapshot
    from backend.app.services.farm_cost_ledger import MAX_LEDGER_COMPONENT_VALUE

    snapshot = await db.scalar(
        select(FarmCostLedgerSnapshot).where(FarmCostLedgerSnapshot.print_log_entry_id == print_log_entry_id)
    )
    if snapshot is not None:
        rate = snapshot.energy_rate_per_kwh
        if not isfinite(rate) or rate <= 0 or rate >= MAX_LEDGER_COMPONENT_VALUE:
            logger.warning(
                "print_log_energy_backfill_policy_invalid print_log_entry_id=%s",
                print_log_entry_id,
            )
            return False
        effective_energy_cost = round(energy_kwh * rate, 3)
        if not isfinite(effective_energy_cost) or effective_energy_cost >= MAX_LEDGER_COMPONENT_VALUE:
            logger.warning(
                "print_log_energy_backfill_cost_invalid print_log_entry_id=%s",
                print_log_entry_id,
            )
            return False
        if effective_energy_cost != energy_cost:
            logger.info(
                "print_log_energy_backfill_snapshot_rate_applied print_log_entry_id=%s policy_version=%s",
                print_log_entry_id,
                snapshot.policy_version,
            )

    entry.energy_kwh = energy_kwh
    entry.energy_cost = effective_energy_cost
    return True


async def write_log_entry(
    db: AsyncSession,
    *,
    status: str,
    archive_id: int | None = None,
    print_name: str | None = None,
    printer_name: str | None = None,
    printer_id: int | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    filament_type: str | None = None,
    filament_color: str | None = None,
    filament_used_grams: float | None = None,
    cost: float | None = None,
    energy_kwh: float | None = None,
    energy_cost: float | None = None,
    failure_reason: str | None = None,
    thumbnail_path: str | None = None,
    created_by_id: int | None = None,
    created_by_username: str | None = None,
) -> PrintLogEntry:
    """Write a print log entry."""
    duration = None
    if started_at and completed_at:
        duration = int((completed_at - started_at).total_seconds())

    capture_ledger = settings.farm_actual_cost_ledger_enabled
    archive_scope_locked = False
    if capture_ledger and archive_id is not None:
        try:
            from backend.app.services.farm_cost_ledger import lock_cost_ledger_archive

            # Attempt order is the print-log insertion order. Acquire the
            # archive lock before this row can become visible to a competitor.
            async with db.begin_nested():
                await lock_cost_ledger_archive(db, archive_id)
            archive_scope_locked = True
        except Exception:
            capture_ledger = False
            logger.exception(
                "farm_cost_ledger_scope_lock_failed archive_id=%s",
                archive_id,
            )

    entry = PrintLogEntry(
        archive_id=archive_id,
        print_name=print_name,
        printer_name=printer_name,
        printer_id=printer_id,
        status=status,
        started_at=started_at,
        completed_at=completed_at,
        duration_seconds=duration,
        filament_type=filament_type,
        filament_color=filament_color,
        filament_used_grams=filament_used_grams,
        cost=cost,
        energy_kwh=energy_kwh,
        energy_cost=energy_cost,
        failure_reason=failure_reason,
        thumbnail_path=thumbnail_path,
        created_by_id=created_by_id,
        created_by_username=created_by_username,
    )
    db.add(entry)
    await db.flush()

    # Farm extension: preserve estimate/rate context next to this immutable
    # actual run. A SAVEPOINT isolates ledger failures so accounting metadata
    # can never erase the canonical print-log event.
    if capture_ledger:
        try:
            from backend.app.services.farm_cost_ledger import capture_cost_snapshot

            async with db.begin_nested():
                await capture_cost_snapshot(
                    db,
                    entry,
                    archive_scope_locked=archive_scope_locked,
                )
        except Exception:
            logger.exception(
                "farm_cost_ledger_snapshot_failed print_log_entry_id=%s",
                entry.id,
            )
    return entry
