from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PlateChange3mfPostprocessPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(min_length=1)
    dry_run: bool = True
    create_output_artifact: bool = False
    real_sample_output_review: bool = False
    output_dir: str | None = None
