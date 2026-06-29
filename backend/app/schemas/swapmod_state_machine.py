from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SwapmodStateMachineCycleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_key: str = Field(min_length=1, max_length=128)
    printer_id: int | None = None
    source_print_run_id: str | None = Field(default=None, max_length=128)


class SwapmodOperatorTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_key: str = Field(min_length=1, max_length=128)
    cycle_key: str = Field(min_length=1, max_length=128)
    printer_id: int | None = None
    source_print_run_id: str | None = Field(default=None, max_length=128)
    operator_intent: Literal["START_SWAPMOD_PLATE_CHANGE"]


class SwapmodVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_key: str = Field(min_length=1, max_length=128)
    verification_source: Literal["manual", "camera_mock"]
    verification_result: Literal["pass", "fail"]
    note: str | None = Field(default=None, max_length=512)


class SwapmodTransportStepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport_key: str = Field(min_length=1, max_length=128)
    step: Literal["RELEASE_PLATE", "LOAD_NEXT_PLATE"]
    mock_result: Literal["success", "failure", "timeout"] = "success"
    note: str | None = Field(default=None, max_length=512)


class SwapmodCanaryExecutionChecklist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_present: bool = False
    canary_device_named: bool = False
    camera_ready: bool = False
    build_plate_clear: bool = False
    emergency_stop_reachable: bool = False
    dry_run_transport_verified: bool = False


class SwapmodCanaryExecutionGateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_key: str = Field(min_length=1, max_length=128)
    canary_printer_alias: str = Field(min_length=1, max_length=128)
    requested_action: Literal["EVALUATE_ONLY", "ARM_DRY_RUN"] = "EVALUATE_ONLY"
    operator_approved: bool = False
    operator_approval_phrase: str | None = Field(default=None, max_length=256)
    checklist: SwapmodCanaryExecutionChecklist


class SwapmodStateMachineEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=128)
    event: str = Field(min_length=1, max_length=64)
    step: str | None = Field(default=None, max_length=64)
    verification_source: str | None = Field(default=None, max_length=64)
    verification_result: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=512)
