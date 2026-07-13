from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SwapmodSequenceActionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1, max_length=96, pattern=r"^[a-z0-9-]+$")
    feedrate: int = Field(ge=1, le=30000)


class SwapmodSequenceCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: Literal["RELEASE_PLATE", "LOAD_NEXT_PLATE"]
    base_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[A-Fa-f0-9]{64}$")
    actions: list[SwapmodSequenceActionUpdate] = Field(min_length=1, max_length=100)

    @field_validator("actions")
    @classmethod
    def require_unique_action_ids(cls, actions: list[SwapmodSequenceActionUpdate]) -> list[SwapmodSequenceActionUpdate]:
        action_ids = [action.action_id for action in actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("action IDs must be unique")
        return actions
