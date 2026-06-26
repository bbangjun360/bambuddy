from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.erp_draft_write import ErpDraftWriteRecord
from backend.app.models.erp_readonly import ErpProductionRequest
from backend.app.services.erp_readonly import REVIEW_REQUIRED

DRAFT_WRITE_PENDING = "DRAFT_WRITE_PENDING"
DRAFT_CREATED = "DRAFT_CREATED"
DRAFT_ALREADY_EXISTS = "DRAFT_ALREADY_EXISTS"
DRAFT_WRITE_RETRYABLE_FAILURE = "DRAFT_WRITE_RETRYABLE_FAILURE"
DRAFT_WRITE_FAILED = "DRAFT_WRITE_FAILED"
DRAFT_WRITE_BLOCKED = "DRAFT_WRITE_BLOCKED"
DRAFT_WRITE_DISABLED = "DRAFT_WRITE_DISABLED"

ERP_DRAFT_AUTH_FAILED = "ERP_DRAFT_AUTH_FAILED"
ERP_DRAFT_RATE_LIMITED = "ERP_DRAFT_RATE_LIMITED"
ERP_DRAFT_UPSTREAM_ERROR = "ERP_DRAFT_UPSTREAM_ERROR"
ERP_DRAFT_TIMEOUT = "ERP_DRAFT_TIMEOUT"
ERP_DRAFT_INVALID_PAYLOAD = "ERP_DRAFT_INVALID_PAYLOAD"
ERP_DRAFT_NOT_FOUND = "ERP_DRAFT_NOT_FOUND"
ERP_DRAFT_SOURCE_NOT_FOUND = "ERP_DRAFT_SOURCE_NOT_FOUND"

RECONCILIATION_MATCHED = "MATCHED"
RECONCILIATION_MISMATCH = "MISMATCH"

DOCTYPE = "Farm Draft Result"

logger = logging.getLogger(__name__)


class ErpDraftWriteError(Exception):
    def __init__(self, code: str, message: str, *, http_status: int, retryable: bool, draft_write_id: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable
        self.draft_write_id = draft_write_id


@dataclass(frozen=True)
class DraftDocument:
    name: str
    farm_event_id: str
    docstatus: int
    status: str | None
    production_request_id: int | None
    external_work_order_id: str | None
    production_item: str | None
    quantity_completed: int | None
    payload: dict[str, Any]
    doctype: str = DOCTYPE


@dataclass(frozen=True)
class DraftWriteClientResult:
    document: DraftDocument
    created: bool
    recovered_after_timeout: bool = False


@dataclass(frozen=True)
class ReconciliationResult:
    event_uuid: str
    status: str
    matched: bool
    mismatches: list[str]
    erp_document_name: str | None


def _nonempty_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


class ErpDraftWriteClient:
    def __init__(
        self,
        base_url: str,
        api_token: str | None,
        *,
        timeout: float = 5.0,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout
        self._client = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = http_client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _headers(self, *, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        if self.api_token:
            headers["Authorization"] = f"token {self.api_token}"
        return headers

    def _resource_url(self) -> str:
        return f"{self.base_url}/erp/api/resource/{quote(DOCTYPE, safe='')}"

    async def create_or_lookup_draft_result(self, payload: dict[str, Any], *, idempotency_key: str) -> DraftWriteClientResult:
        try:
            document = await self.create_draft_result(payload, idempotency_key=idempotency_key)
            return DraftWriteClientResult(document=document, created=True, recovered_after_timeout=False)
        except ErpDraftWriteError as exc:
            if exc.code != ERP_DRAFT_TIMEOUT:
                raise
            try:
                document = await self.lookup_draft_result(str(payload.get("farm_event_id") or idempotency_key))
            except ErpDraftWriteError:
                raise exc
            return DraftWriteClientResult(document=document, created=False, recovered_after_timeout=True)

    async def create_draft_result(self, payload: dict[str, Any], *, idempotency_key: str) -> DraftDocument:
        try:
            response = await self._client.post(
                self._resource_url(),
                json=payload,
                headers=self._headers(idempotency_key=idempotency_key),
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise ErpDraftWriteError(ERP_DRAFT_TIMEOUT, "ERP draft request timed out", http_status=504, retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ErpDraftWriteError(ERP_DRAFT_UPSTREAM_ERROR, "ERP draft request failed", http_status=502, retryable=True) from exc
        return self._document_from_response(response)

    async def lookup_draft_result(self, farm_event_id: str) -> DraftDocument:
        try:
            response = await self._client.get(
                self._resource_url(),
                params={"farm_event_id": farm_event_id},
                headers=self._headers(),
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise ErpDraftWriteError(ERP_DRAFT_TIMEOUT, "ERP draft lookup timed out", http_status=504, retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ErpDraftWriteError(ERP_DRAFT_UPSTREAM_ERROR, "ERP draft lookup failed", http_status=502, retryable=True) from exc
        return self._document_from_response(response)

    def _document_from_response(self, response: httpx.Response) -> DraftDocument:
        if response.status_code in (401, 403):
            raise ErpDraftWriteError(ERP_DRAFT_AUTH_FAILED, "ERP draft authentication failed", http_status=401, retryable=False)
        if response.status_code == 429:
            raise ErpDraftWriteError(ERP_DRAFT_RATE_LIMITED, "ERP draft rate limited", http_status=503, retryable=True)
        if response.status_code == 404:
            raise ErpDraftWriteError(ERP_DRAFT_NOT_FOUND, "ERP draft document not found", http_status=404, retryable=True)
        if response.status_code >= 500:
            raise ErpDraftWriteError(ERP_DRAFT_UPSTREAM_ERROR, f"ERP draft server error HTTP {response.status_code}", http_status=502, retryable=True)
        if response.status_code >= 400:
            raise ErpDraftWriteError(ERP_DRAFT_UPSTREAM_ERROR, f"ERP draft returned HTTP {response.status_code}", http_status=502, retryable=True)

        try:
            envelope = response.json()
        except ValueError as exc:
            raise ErpDraftWriteError(ERP_DRAFT_INVALID_PAYLOAD, "ERP draft returned non-JSON payload", http_status=422, retryable=False) from exc
        if not isinstance(envelope, dict) or not isinstance(envelope.get("data"), dict):
            raise ErpDraftWriteError(ERP_DRAFT_INVALID_PAYLOAD, "ERP draft returned invalid envelope", http_status=422, retryable=False)
        return validate_draft_document(envelope["data"])


def validate_draft_document(payload: dict[str, Any]) -> DraftDocument:
    name = _nonempty_str(payload.get("name"))
    farm_event_id = _nonempty_str(payload.get("farm_event_id"))
    docstatus = payload.get("docstatus")
    quantity = payload.get("quantity_completed")
    if not name:
        raise ErpDraftWriteError(ERP_DRAFT_INVALID_PAYLOAD, "ERP draft is missing name", http_status=422, retryable=False)
    if not farm_event_id:
        raise ErpDraftWriteError(ERP_DRAFT_INVALID_PAYLOAD, "ERP draft is missing farm_event_id", http_status=422, retryable=False)
    if docstatus != 0:
        raise ErpDraftWriteError(ERP_DRAFT_INVALID_PAYLOAD, "ERP draft is not in Draft state", http_status=422, retryable=False)
    if quantity is not None and (not isinstance(quantity, int | float) or isinstance(quantity, bool) or quantity <= 0):
        raise ErpDraftWriteError(ERP_DRAFT_INVALID_PAYLOAD, "ERP draft quantity is invalid", http_status=422, retryable=False)
    return DraftDocument(
        name=name,
        farm_event_id=farm_event_id,
        docstatus=int(docstatus),
        status=_nonempty_str(payload.get("status")),
        production_request_id=payload.get("production_request_id") if isinstance(payload.get("production_request_id"), int) else None,
        external_work_order_id=_nonempty_str(payload.get("external_work_order_id")),
        production_item=_nonempty_str(payload.get("production_item")),
        quantity_completed=int(quantity) if quantity is not None else None,
        payload=payload,
        doctype=_nonempty_str(payload.get("doctype")) or DOCTYPE,
    )


def _review_safe(source: ErpProductionRequest) -> bool:
    return source.status == REVIEW_REQUIRED and source.executable is False and source.library_file_id is not None


def _completed_at_iso(value: datetime | None) -> str:
    stamp = value or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.isoformat()


def _payload_for(source: ErpProductionRequest, *, event_uuid: str, quantity_completed: int, completed_at: datetime | None) -> dict[str, Any]:
    return {
        "farm_event_id": event_uuid,
        "production_request_id": source.id,
        "external_work_order_id": source.external_work_order_id,
        "production_item": source.production_item,
        "quantity_completed": quantity_completed,
        "completed_at": _completed_at_iso(completed_at),
    }


async def _find_record(db: AsyncSession, event_uuid: str) -> ErpDraftWriteRecord | None:
    result = await db.execute(select(ErpDraftWriteRecord).where(ErpDraftWriteRecord.event_uuid == event_uuid))
    return result.scalar_one_or_none()


async def _new_record(
    db: AsyncSession,
    *,
    source_request_id: int,
    event_uuid: str,
    print_run_id: str | None,
) -> ErpDraftWriteRecord:
    record = ErpDraftWriteRecord(
        source_request_id=source_request_id,
        event_uuid=event_uuid,
        print_run_id=print_run_id,
        status=DRAFT_WRITE_PENDING,
        retryable=False,
        dead_letter=False,
        attempts=0,
        reconciliation_mismatches=[],
    )
    db.add(record)
    await db.flush()
    return record


async def create_draft_for_request(
    db: AsyncSession,
    *,
    source_request_id: int,
    event_uuid: str,
    print_run_id: str | None,
    quantity_completed: int,
    completed_at: datetime | None,
    client: ErpDraftWriteClient,
) -> ErpDraftWriteRecord:
    source = await db.get(ErpProductionRequest, source_request_id)
    if source is None:
        raise ErpDraftWriteError(ERP_DRAFT_SOURCE_NOT_FOUND, "ERP production request not found", http_status=404, retryable=False)

    record = await _find_record(db, event_uuid)
    if record is None:
        record = await _new_record(db, source_request_id=source.id, event_uuid=event_uuid, print_run_id=print_run_id)
    elif record.erp_document_name:
        record.status = DRAFT_ALREADY_EXISTS
        record.retryable = False
        record.dead_letter = False
        await db.flush()
        await db.refresh(record)
        return record

    if not _review_safe(source):
        record.status = DRAFT_WRITE_BLOCKED
        record.retryable = False
        record.dead_letter = True
        record.last_error_code = DRAFT_WRITE_BLOCKED
        record.last_error_message = "ERP production request is not review-safe for draft write"
        await db.flush()
        await db.refresh(record)
        logger.info("ERP draft write blocked", extra={"event_uuid": event_uuid, "source_request_id": source.id})
        return record

    payload = _payload_for(source, event_uuid=event_uuid, quantity_completed=quantity_completed, completed_at=completed_at)
    record.status = DRAFT_WRITE_PENDING
    record.retryable = False
    record.dead_letter = False
    record.last_error_code = None
    record.last_error_message = None
    record.request_payload = payload
    record.attempts = int(record.attempts or 0) + 1
    await db.flush()

    try:
        result = await client.create_or_lookup_draft_result(payload, idempotency_key=event_uuid)
    except ErpDraftWriteError as exc:
        record.status = DRAFT_WRITE_RETRYABLE_FAILURE if exc.retryable else DRAFT_WRITE_FAILED
        record.retryable = exc.retryable
        record.dead_letter = not exc.retryable
        record.last_error_code = exc.code
        record.last_error_message = exc.message
        await db.flush()
        await db.refresh(record)
        exc.draft_write_id = record.id
        logger.info(
            "ERP draft write failed",
            extra={"event_uuid": event_uuid, "status": record.status, "error_code": exc.code, "retryable": exc.retryable},
        )
        raise

    document = result.document
    record.status = DRAFT_CREATED if result.created else DRAFT_ALREADY_EXISTS
    record.retryable = False
    record.dead_letter = False
    record.erp_document_name = document.name
    record.erp_doctype = document.doctype
    record.erp_docstatus = document.docstatus
    record.erp_status = document.status
    record.response_payload = document.payload
    record.last_error_code = None
    record.last_error_message = None
    await db.flush()
    await db.refresh(record)
    logger.info(
        "ERP draft write recorded",
        extra={"event_uuid": event_uuid, "status": record.status, "erp_document_name": document.name},
    )
    return record


async def reconcile_draft_record(db: AsyncSession, *, event_uuid: str, client: ErpDraftWriteClient) -> ReconciliationResult:
    record = await _find_record(db, event_uuid)
    if record is None:
        raise ErpDraftWriteError(ERP_DRAFT_NOT_FOUND, "ERP draft write record not found", http_status=404, retryable=False)
    if not record.erp_document_name:
        raise ErpDraftWriteError(ERP_DRAFT_NOT_FOUND, "ERP draft write has no ERP document", http_status=404, retryable=False)

    document = await client.lookup_draft_result(event_uuid)
    expected_payload = record.request_payload or {}
    mismatches: list[str] = []
    if document.name != record.erp_document_name:
        mismatches.append("erp_document_name")
    if document.farm_event_id != record.event_uuid:
        mismatches.append("event_uuid")
    if document.docstatus != 0:
        mismatches.append("docstatus")
    if document.production_request_id != record.source_request_id:
        mismatches.append("production_request_id")
    if document.quantity_completed != expected_payload.get("quantity_completed"):
        mismatches.append("quantity_completed")

    status = RECONCILIATION_MATCHED if not mismatches else RECONCILIATION_MISMATCH
    record.reconciliation_status = status
    record.reconciliation_mismatches = mismatches
    await db.flush()
    await db.refresh(record)
    return ReconciliationResult(
        event_uuid=event_uuid,
        status=status,
        matched=not mismatches,
        mismatches=mismatches,
        erp_document_name=record.erp_document_name,
    )
