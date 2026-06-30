from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SwapmodA1MiniDirectCanaryChecklist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_present: bool = False
    printer_visible: bool = False
    emergency_stop_ready: bool = False
    power_cutoff_ready: bool = False
    a1_mini_confirmed: bool = False
    swapmod_hardware_installed: bool = False
    bed_area_clear: bool = False
    plate_stack_ready: bool = False
    no_other_job_running: bool = False
    dry_run_gate_reviewed: bool = False


class SwapmodA1MiniDirectCanaryTransportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canary_key: str = Field(min_length=1, max_length=128)
    printer_id: int
    step: Literal["RELEASE_PLATE", "LOAD_NEXT_PLATE"]
    operator_approved: bool = False
    operator_approval_phrase: str | None = Field(default=None, max_length=512)
    checklist: SwapmodA1MiniDirectCanaryChecklist
