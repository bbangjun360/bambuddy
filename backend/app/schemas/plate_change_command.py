from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlateChangeCommandSequence(str, Enum):
    A1_MINI_PLATE_CHANGE_DRY_RUN = "A1_MINI_PLATE_CHANGE_DRY_RUN"
    A1_MINI_PLATE_CHANGE_CANDIDATE_V1 = "A1_MINI_PLATE_CHANGE_CANDIDATE_V1"


class PlateChangeDryRunCommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1)
    target_printer_ids: list[str] = Field(default_factory=list)
    command_sequence: PlateChangeCommandSequence
    dry_run: bool = True
    operator_approved: bool = False
    operator_approval_phrase: str | None = None
    metadata: dict[str, Any] | None = None
