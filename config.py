"""
Central configuration. All secrets come from environment variables
(loaded from a .env file in development). Nothing secret is hard-coded here.
"""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _int_list(raw: str) -> list[int]:
    """Turn "1, 2,3" into [1, 2, 3], ignoring blanks."""
    return [int(part) for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class Config:
    bot_token: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+aiosqlite:///gymbot.db")
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())
    rate_limit_max: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_MAX", "8")))
    rate_limit_window: float = field(
        default_factory=lambda: float(os.getenv("RATE_LIMIT_WINDOW", "5"))
    )
    # Exact attribution text for the RepDB exercise images, shown in /about.
    exercise_image_attribution: str = field(
        default_factory=lambda: os.getenv(
            "EXERCISE_IMAGE_ATTRIBUTION",
            "Exercise images from the RepDB dataset, used under its license.",
        )
    )
    admin_ids: list[int] = field(default_factory=lambda: _int_list(os.getenv("ADMIN_IDS", "")))


config = Config()
