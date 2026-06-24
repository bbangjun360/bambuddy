from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ErpDraftWriteRequest(BaseModel):
    event_uuid: str = Field(min_length=1, max_length=128)
    print_run_id: str | None = Field(default=None, max_length=128)
    quantity_completed: int = Field(gt=0)
    completed_at: datetime | None = None


class ErpDraftWriteRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_request_id: int
    event_uuid: str
    print_run_id: str | None
    status: str
    retryable: bool
    dead_letter: bool
    attempts: int
    erp_document_name: str | None
    erp_doctype: str | None
    erp_docstatus: int | None
    erp_status: str | None
    last_error_code: str | None
    last_error_message: str | None
    request_payload: dict | None
    response_payload: dict | None
    reconciliation_status: str | None
    reconciliation_mismatches: list[str]
    created_at: datetime
    updated_at: datetime


class ErpDraftReconciliationResponse(BaseModel):
    event_uuid: str
    status: str
    matched: bool
    mismatches: list[str]
    erp_document_name: str | None
