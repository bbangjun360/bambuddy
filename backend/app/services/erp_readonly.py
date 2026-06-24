from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.erp_readonly import ErpProductionRequest
from backend.app.models.library import LibraryFile

REVIEW_REQUIRED = "REVIEW_REQUIRED"
BLOCKED_MISSING_ARTIFACT = "BLOCKED_MISSING_ARTIFACT"
BLOCKED_INVALID_PROFILE = "BLOCKED_INVALID_PROFILE"
IMPORT_FAILED = "IMPORT_FAILED"

ERP_AUTH_FAILED = "ERP_AUTH_FAILED"
ERP_RATE_LIMITED = "ERP_RATE_LIMITED"
ERP_UPSTREAM_ERROR = "ERP_UPSTREAM_ERROR"
ERP_TIMEOUT = "ERP_TIMEOUT"
ERP_INVALID_PAYLOAD = "ERP_INVALID_PAYLOAD"

SOURCE_SYSTEM = "erpnext"
SUPPORTED_PROFILE_SET_IDS = frozenset({"p1p-pla-fixture-v1"})


class ErpReadOnlyError(Exception):
    def __init__(self, code: str, message: str, *, http_status: int, retryable: bool):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable


@dataclass(frozen=True)
class WorkOrder:
    name: str
    production_item: str
    quantity: int
    erp_status: str | None
    artifact_reference: str | None
    profile_set_id: str | None
    customer: str | None
    payload: dict[str, Any]


class ErpReadOnlyClient:
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

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"token {self.api_token}"
        return headers

    async def fetch_work_order(self, work_order_id: str) -> dict[str, Any]:
        encoded = quote(work_order_id, safe="")
        url = f"{self.base_url}/erp/api/resource/Work%20Order/{encoded}"
        try:
            response = await self._client.get(url, headers=self._headers(), timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise ErpReadOnlyError(ERP_TIMEOUT, "ERP request timed out", http_status=504, retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ErpReadOnlyError(ERP_UPSTREAM_ERROR, "ERP request failed", http_status=502, retryable=True) from exc

        if response.status_code in (401, 403):
            raise ErpReadOnlyError(ERP_AUTH_FAILED, "ERP authentication failed", http_status=401, retryable=False)
        if response.status_code == 429:
            raise ErpReadOnlyError(ERP_RATE_LIMITED, "ERP rate limited request", http_status=503, retryable=True)
        if response.status_code >= 500:
            raise ErpReadOnlyError(ERP_UPSTREAM_ERROR, f"ERP server error HTTP {response.status_code}", http_status=502, retryable=True)
        if response.status_code >= 400:
            raise ErpReadOnlyError(ERP_UPSTREAM_ERROR, f"ERP returned HTTP {response.status_code}", http_status=502, retryable=True)

        try:
            payload = response.json()
        except ValueError as exc:
            raise ErpReadOnlyError(ERP_INVALID_PAYLOAD, "ERP returned non-JSON payload", http_status=422, retryable=False) from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            raise ErpReadOnlyError(ERP_INVALID_PAYLOAD, "ERP returned invalid Work Order envelope", http_status=422, retryable=False)
        return payload["data"]


def _nonempty_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def validate_work_order(payload: dict[str, Any], requested_work_order_id: str) -> WorkOrder:
    if not isinstance(payload, dict):
        raise ErpReadOnlyError(ERP_INVALID_PAYLOAD, "ERP Work Order payload must be an object", http_status=422, retryable=False)

    name = _nonempty_str(payload.get("name"))
    production_item = _nonempty_str(payload.get("production_item"))
    qty = payload.get("qty")

    if not name:
        raise ErpReadOnlyError(ERP_INVALID_PAYLOAD, "ERP Work Order is missing name", http_status=422, retryable=False)
    if name != requested_work_order_id:
        raise ErpReadOnlyError(ERP_INVALID_PAYLOAD, "ERP Work Order name did not match request", http_status=422, retryable=False)
    if not production_item:
        raise ErpReadOnlyError(ERP_INVALID_PAYLOAD, "ERP Work Order is missing production_item", http_status=422, retryable=False)
    if not isinstance(qty, int | float) or isinstance(qty, bool) or not math.isfinite(float(qty)) or qty <= 0:
        raise ErpReadOnlyError(ERP_INVALID_PAYLOAD, "ERP Work Order has invalid qty", http_status=422, retryable=False)

    return WorkOrder(
        name=name,
        production_item=production_item,
        quantity=int(qty),
        erp_status=_nonempty_str(payload.get("status")),
        artifact_reference=_nonempty_str(payload.get("custom_artifact_reference")),
        profile_set_id=_nonempty_str(payload.get("custom_profile_set_id")),
        customer=_nonempty_str(payload.get("customer")),
        payload=payload,
    )


def artifact_source_url(reference: str) -> str:
    return f"erp://artifact/{reference}"


async def _find_request(db: AsyncSession, work_order_id: str) -> ErpProductionRequest | None:
    result = await db.execute(
        select(ErpProductionRequest).where(
            ErpProductionRequest.source_system == SOURCE_SYSTEM,
            ErpProductionRequest.external_work_order_id == work_order_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_or_create_request(db: AsyncSession, work_order_id: str) -> ErpProductionRequest:
    request = await _find_request(db, work_order_id)
    if request is not None:
        return request
    request = ErpProductionRequest(
        source_system=SOURCE_SYSTEM,
        external_work_order_id=work_order_id,
        status=IMPORT_FAILED,
        executable=False,
    )
    db.add(request)
    await db.flush()
    return request


async def _resolve_artifact(db: AsyncSession, reference: str | None) -> LibraryFile | None:
    if not reference:
        return None
    result = await db.execute(
        LibraryFile.active().where(
            LibraryFile.source_type == "erp_artifact",
            LibraryFile.source_url == artifact_source_url(reference),
        )
    )
    return result.scalar_one_or_none()


async def import_work_order_payload(
    db: AsyncSession,
    *,
    requested_work_order_id: str,
    payload: dict[str, Any],
) -> ErpProductionRequest:
    work_order = validate_work_order(payload, requested_work_order_id)
    request = await _get_or_create_request(db, work_order.name)
    artifact = await _resolve_artifact(db, work_order.artifact_reference)

    if work_order.profile_set_id not in SUPPORTED_PROFILE_SET_IDS:
        status = BLOCKED_INVALID_PROFILE
        review_reason = "ERP Work Order references a missing or unsupported profile set"
    elif artifact is None:
        status = BLOCKED_MISSING_ARTIFACT
        review_reason = "ERP Work Order artifact reference is not mapped to a Bambuddy library file"
    else:
        status = REVIEW_REQUIRED
        review_reason = "ERP Work Order imported for human review"

    request.production_item = work_order.production_item
    request.quantity = work_order.quantity
    request.erp_status = work_order.erp_status
    request.artifact_reference = work_order.artifact_reference
    request.profile_set_id = work_order.profile_set_id
    request.customer = work_order.customer
    request.library_file_id = artifact.id if artifact is not None else None
    request.status = status
    request.review_reason = review_reason
    request.executable = False
    request.retryable = False
    request.last_error_code = None
    request.last_error_message = None
    request.import_attempts = (request.import_attempts or 0) + 1
    request.erp_payload = work_order.payload
    await db.flush()
    await db.refresh(request)
    return request


async def record_import_failure(
    db: AsyncSession,
    *,
    requested_work_order_id: str,
    error: ErpReadOnlyError,
) -> ErpProductionRequest:
    request = await _get_or_create_request(db, requested_work_order_id)
    request.status = IMPORT_FAILED
    request.review_reason = error.message
    request.executable = False
    request.retryable = error.retryable
    request.last_error_code = error.code
    request.last_error_message = error.message
    request.import_attempts = (request.import_attempts or 0) + 1
    await db.flush()
    await db.refresh(request)
    return request
