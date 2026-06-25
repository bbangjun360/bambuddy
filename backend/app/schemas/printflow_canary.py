from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PrintFlowCanaryReadinessRequest(BaseModel):
    check_key: str = Field(min_length=1)
    dry_run: bool = True
    audit_only: bool = True
    operator_approved: bool = False
    mock_scenario: str = "ready"
    printer_alias: str | None = None
    cycle_alias: str | None = None
    metadata: dict[str, Any] | None = None


class PrintFlowRealCanaryRunRequest(BaseModel):
    idempotency_key: str = Field(min_length=1)
    job_id: str | None = None
    target_printer_ids: list[str] = Field(default_factory=list)
    dry_run: bool = True
    audit_only: bool = True
    operator_approved: bool = False
    operator_approval_phrase: str | None = None
    metadata: dict[str, Any] | None = None
