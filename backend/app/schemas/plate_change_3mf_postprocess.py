from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PlateChange3mfPostprocessPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(min_length=1)
    dry_run: bool = True
    create_output_artifact: bool = False
    real_sample_output_review: bool = False
    output_dir: str | None = None

class PlateChange3mfCanaryUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_printer_ids: list[str] = Field(min_length=1)
    artifact_path: str = Field(min_length=1)
    artifact_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[A-Fa-f0-9]{64}$")
    operator_confirmation_phrase: str = Field(min_length=1)


class PlateChange3mfCanaryStartChecklist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator_present: bool
    printer_visible: bool
    emergency_stop_ready: bool
    power_cutoff_ready: bool
    bed_clear_confirmed: bool
    correct_plate_confirmed: bool
    no_other_job_running: bool
    fire_risk_area_clear: bool


class PlateChange3mfCanaryStartRequest(PlateChange3mfCanaryUploadRequest):
    checklist: PlateChange3mfCanaryStartChecklist
