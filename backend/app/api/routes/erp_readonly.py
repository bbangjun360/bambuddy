from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.permissions import Permission
from backend.app.models.erp_readonly import ErpProductionRequest
from backend.app.schemas.erp_readonly import ErpProductionRequestResponse
from backend.app.services.erp_readonly import (
    ErpReadOnlyClient,
    ErpReadOnlyError,
    import_work_order_payload,
    record_import_failure,
)

router = APIRouter(prefix="/erp-readonly", tags=["erp-readonly"])


def get_erp_client() -> ErpReadOnlyClient | None:
    if not settings.farm_erp_import_enabled:
        return None
    return ErpReadOnlyClient(
        settings.farm_erp_base_url,
        settings.farm_erp_api_token,
        api_prefix=settings.farm_erp_api_prefix,
        timeout=settings.farm_erp_timeout_seconds,
    )


def _ensure_enabled() -> None:
    if not settings.farm_erp_import_enabled:
        raise HTTPException(status_code=404, detail="ERP read-only import is disabled")


@router.post("/work-orders/{work_order_id}/import", response_model=ErpProductionRequestResponse)
async def import_work_order(
    work_order_id: str,
    db: AsyncSession = Depends(get_db),
    erp_client: ErpReadOnlyClient | None = Depends(get_erp_client),
    _: object | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_UPDATE),
):
    _ensure_enabled()
    if erp_client is None:
        raise HTTPException(status_code=404, detail="ERP read-only import is disabled")
    try:
        payload = await erp_client.fetch_work_order(work_order_id)
        request = await import_work_order_payload(db, requested_work_order_id=work_order_id, payload=payload)
        await db.commit()
        await db.refresh(request)
    except ErpReadOnlyError as exc:
        request = await record_import_failure(db, requested_work_order_id=work_order_id, error=exc)
        await db.commit()
        request_id = request.id
        raise HTTPException(
            status_code=exc.http_status,
            detail={
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "request_id": request_id,
            },
        ) from exc
    finally:
        close = getattr(erp_client, "close", None)
        if close is not None:
            await close()
    return request


@router.get("/production-requests", response_model=list[ErpProductionRequestResponse])
async def list_production_requests(
    external_work_order_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: object | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_READ),
):
    statement = select(ErpProductionRequest).order_by(ErpProductionRequest.id)
    if external_work_order_id:
        statement = statement.where(ErpProductionRequest.external_work_order_id == external_work_order_id)
    result = await db.execute(statement)
    return list(result.scalars())


@router.get("/production-requests/{request_id}", response_model=ErpProductionRequestResponse)
async def get_production_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    _: object | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_READ),
):
    request = await db.get(ErpProductionRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="ERP production request not found")
    return request
