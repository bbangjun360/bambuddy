import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.permissions import Permission
from backend.app.schemas.farm_cost_ledger import FarmCostLedgerResponse
from backend.app.services.farm_cost_ledger import list_cost_ledger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/farm-cost-ledger", tags=["farm-cost-ledger"])


def _ensure_enabled() -> None:
    if not settings.farm_actual_cost_ledger_enabled:
        raise HTTPException(status_code=404, detail="Farm actual cost ledger is disabled")


@router.get("", response_model=FarmCostLedgerResponse)
async def get_farm_cost_ledger(
    status: Literal["completed", "failed", "aborted", "stopped", "cancelled", "skipped"] | None = None,
    attempt_kind: Literal["original", "reprint", "unlinked"] | None = None,
    printer_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: object | None = RequirePermissionIfAuthEnabled(Permission.STATS_READ),
) -> FarmCostLedgerResponse:
    """Return immutable estimate snapshots joined to per-run actual costs."""
    _ensure_enabled()
    response = await list_cost_ledger(
        db,
        status=status,
        attempt_kind=attempt_kind,
        printer_id=printer_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    logger.info(
        "farm_cost_ledger_read total=%s returned=%s offset=%s",
        response.total,
        len(response.items),
        offset,
    )
    return response
