from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SwapmodBedReadinessRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_key: str = Field(min_length=1, max_length=128)
    printer_id: int
