from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SwapmodCanaryPreflightChecklist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_present: bool
    printer_visible: bool
    emergency_stop_ready: bool
    power_cutoff_ready: bool
    bed_clear_confirmed: bool
    correct_plate_confirmed: bool
    no_other_job_running: bool
    swapmod_hardware_installed: bool
    plate_stack_loaded: bool
    original_print_finished: bool
    bed_state_reviewed: bool


class SwapmodCanaryPreflightPackageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run_plan: dict[str, Any]
    candidate_id: str = Field(min_length=1)
    target_printer_id: str = Field(min_length=1)
    expected_printer_model_family: str = Field(min_length=1)
    checklist: SwapmodCanaryPreflightChecklist
    operator_confirmation_phrase: str = Field(min_length=1)
