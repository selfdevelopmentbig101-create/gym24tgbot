"""Request bodies for Stage 5 (workout-day screen and live logger). Validated by pydantic."""
from typing import Literal

from pydantic import BaseModel, Field


class StartIn(BaseModel):
    day_index: int = Field(ge=0, le=6, description="Plan day to train (0 = first)")
    force: bool = Field(False, description="End an unfinished workout and start this one")


class SetIn(BaseModel):
    index: int = Field(ge=0, le=30, description="Exercise position in the workout")
    weight_kg: float = Field(ge=0, le=500, description="0 = bodyweight only")
    reps: int = Field(ge=1, le=600, description="Seconds for holds like the plank")
    rpe: float | None = Field(None, ge=1, le=10, description="How hard it felt (optional)")
    warmup: bool = False


class SetPatch(BaseModel):
    weight_kg: float | None = Field(None, ge=0, le=500)
    reps: int | None = Field(None, ge=1, le=600)
    rpe: float | None = Field(None, ge=1, le=10, description="null clears it")


class ItemPatch(BaseModel):
    note: str | None = Field(None, max_length=200, description="Short note for this exercise; empty clears it")
    group: Literal["A", "B", "C", "D"] | None = Field(None, description="Superset group; null = none")
