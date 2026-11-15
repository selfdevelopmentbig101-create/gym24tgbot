"""/api/health (no auth, for uptime checks) and /api/config (app-wide settings)."""
from fastapi import APIRouter, Depends

from api.auth import TelegramIdentity
from api.deps import get_identity
from api.schemas import ConfigOut, HealthOut, LanguageOption
from config import config
from utils.texts import LANGUAGE_NAMES, SUPPORTED_LANGUAGES

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    """Is the API running? Returns no user data, so it needs no login."""
    return HealthOut(status="ok")


@router.get("/config", response_model=ConfigOut)
async def app_config(_: TelegramIdentity = Depends(get_identity)) -> ConfigOut:
    return ConfigOut(
        app_name="Gym24",
        attribution=config.exercise_image_attribution,
        languages=[LanguageOption(code=c, name=LANGUAGE_NAMES[c]) for c in SUPPORTED_LANGUAGES],
    )
