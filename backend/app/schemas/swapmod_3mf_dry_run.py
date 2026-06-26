from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Swapmod3mfDryRunPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_path: str = Field(min_length=1)
    swapmod_path: str = Field(min_length=1)
    dry_run: bool = True
    expected_printer_model_family: str | None = None
