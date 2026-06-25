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
