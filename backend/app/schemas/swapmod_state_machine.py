from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SwapmodStateMachineCycleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_key: str = Field(min_length=1, max_length=128)
    printer_id: int | None = None
    source_print_run_id: str | None = Field(default=None, max_length=128)


class SwapmodStateMachineEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=128)
    event: str = Field(min_length=1, max_length=64)
    step: str | None = Field(default=None, max_length=64)
    verification_source: str | None = Field(default=None, max_length=64)
    verification_result: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=512)
