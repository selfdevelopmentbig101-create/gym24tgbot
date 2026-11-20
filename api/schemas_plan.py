"""Request bodies for Stage 4 (programs and the split editor). Validated by pydantic."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from database.enums import Equipment, Experience, Injury

Goal = Literal["strength", "hypertrophy", "endurance"]


class _In(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class ProgramIn(_In):
    """POST /api/programs (the create-program screen)."""
    name: str = Field(min_length=1, max_length=40)
    weeks: int = Field(8, ge=4, le=16)
    workouts_per_week: int = Field(ge=2, le=6)
    goal: Goal = "hypertrophy"
    activate: bool = Field(False, description="Make it the current program right away")


class ProgramPatch(_In):
    name: str | None = Field(None, max_length=40, description="Empty or null = the default name")
    weeks: int | None = Field(None, ge=4, le=16)


class DayIn(_In):
    title: str | None = Field(None, max_length=30)


class DayPatch(_In):
    title: str | None = Field(None, max_length=30, description="Empty or null = the default name")
    position: int | None = Field(None, ge=0, le=6, description="New place in the week (0 = first)")


class PlanPreviewIn(_In):
    """POST /api/plan/preview: the split the onboarding would build for these answers."""
    experience: Experience
    equipment: Equipment
    injuries: list[Injury] = Field(default_factory=list, max_length=len(Injury))
    days: int = Field(ge=2, le=6, description="Workouts per week (the split follows from it)")


class ExerciseIn(_In):
    exercise_id: str = Field(min_length=1, max_length=80)
    sets: int | None = Field(None, ge=1, le=10)
    rep_min: int | None = Field(None, ge=1, le=180)
    rep_max: int | None = Field(None, ge=1, le=180)


class EntryPatch(_In):
    sets: int | None = Field(None, ge=1, le=10)
    rep_min: int | None = Field(None, ge=1, le=180)
    rep_max: int | None = Field(None, ge=1, le=180)
    rest_seconds: int | None = Field(None, ge=15, le=600)
    position: int | None = Field(None, ge=0, le=11, description="New place in the day (0 = first)")
