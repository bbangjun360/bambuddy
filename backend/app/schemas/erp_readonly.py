from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ErpProductionRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_system: str
    external_work_order_id: str
    production_item: str | None
    quantity: int | None
    erp_status: str | None
    artifact_reference: str | None
    profile_set_id: str | None
    customer: str | None
    library_file_id: int | None
    status: str
    review_reason: str | None
    executable: bool
    retryable: bool
    last_error_code: str | None
    last_error_message: str | None
    import_attempts: int
    created_at: datetime
    updated_at: datetime
