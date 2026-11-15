"""Request and response shapes (validated by pydantic, shown in /api/docs)."""
from typing import Literal

from pydantic import BaseModel, Field

LanguageCode = Literal["en", "ru", "uz"]


class LanguageOption(BaseModel):
    code: LanguageCode
    name: str


class MeOut(BaseModel):
    first_name: str = Field(description="From Telegram's verified initData; not stored")
    language: LanguageCode | None = Field(description="The user's saved choice; null = not chosen yet")
    language_effective: LanguageCode = Field(description="Language to show now")
    disclaimer_accepted: bool
    profile_complete: bool = Field(description="False = show onboarding")


class LanguageIn(BaseModel):
    language: LanguageCode


class ConfigOut(BaseModel):
    app_name: str
    attribution: str = Field(description="Credits for the exercise images (Profile > Credits)")
    languages: list[LanguageOption]


class HealthOut(BaseModel):
    status: Literal["ok"]
