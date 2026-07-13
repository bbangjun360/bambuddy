from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import RequirePermissionIfAuthEnabled
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.permissions import Permission
from backend.app.schemas.erp_draft_write import (
    ErpDraftReconciliationResponse,
    ErpDraftWriteRecordResponse,
    ErpDraftWriteRequest,
)
from backend.app.services.erp_draft_write import (
    ErpDraftWriteClient,
    ErpDraftWriteError,
    create_draft_for_request,
    reconcile_draft_record,
)

router = APIRouter(prefix="/erp-draft-write", tags=["erp-draft-write"])


def get_erp_draft_client() -> ErpDraftWriteClient | None:
    if not settings.farm_erp_draft_posting_enabled:
        return None
    return ErpDraftWriteClient(
        settings.farm_erp_base_url,
        settings.farm_erp_api_token,
        api_prefix=settings.farm_erp_api_prefix,
        timeout=settings.farm_erp_timeout_seconds,
    )


def _ensure_enabled() -> None:
    if not settings.farm_erp_draft_posting_enabled:
        raise HTTPException(status_code=404, detail="ERP draft write is disabled")


def _error_detail(exc: ErpDraftWriteError) -> dict:
    return {
        "code": exc.code,
        "message": exc.message,
        "retryable": exc.retryable,
        "draft_write_id": exc.draft_write_id,
    }


@router.post("/production-requests/{request_id}/drafts", response_model=ErpDraftWriteRecordResponse)
async def create_draft_write(
    request_id: int,
    body: ErpDraftWriteRequest,
    db: AsyncSession = Depends(get_db),
    erp_client: ErpDraftWriteClient | None = Depends(get_erp_draft_client),
    _: object | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_UPDATE),
):
    _ensure_enabled()
    if erp_client is None:
        raise HTTPException(status_code=404, detail="ERP draft write is disabled")
    try:
        record = await create_draft_for_request(
            db,
            source_request_id=request_id,
            event_uuid=body.event_uuid,
            print_run_id=body.print_run_id,
            quantity_completed=body.quantity_completed,
            completed_at=body.completed_at,
            client=erp_client,
            erp_timezone=settings.farm_erp_timezone,
        )
        await db.commit()
        await db.refresh(record)
    except ErpDraftWriteError as exc:
        await db.commit()
        raise HTTPException(status_code=exc.http_status, detail=_error_detail(exc)) from exc
    finally:
        close = getattr(erp_client, "close", None)
        if close is not None:
            await close()
    return record


@router.post("/drafts/{event_uuid}/reconcile", response_model=ErpDraftReconciliationResponse)
async def reconcile_draft_write(
    event_uuid: str,
    db: AsyncSession = Depends(get_db),
    erp_client: ErpDraftWriteClient | None = Depends(get_erp_draft_client),
    _: object | None = RequirePermissionIfAuthEnabled(Permission.SETTINGS_UPDATE),
):
    _ensure_enabled()
    if erp_client is None:
        raise HTTPException(status_code=404, detail="ERP draft write is disabled")
    try:
        result = await reconcile_draft_record(db, event_uuid=event_uuid, client=erp_client)
        await db.commit()
    except ErpDraftWriteError as exc:
        await db.commit()
        raise HTTPException(status_code=exc.http_status, detail=_error_detail(exc)) from exc
    finally:
        close = getattr(erp_client, "close", None)
        if close is not None:
            await close()
    return ErpDraftReconciliationResponse(
        event_uuid=result.event_uuid,
        status=result.status,
        matched=result.matched,
        mismatches=result.mismatches,
        erp_document_name=result.erp_document_name,
    )
