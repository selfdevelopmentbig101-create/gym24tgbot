"""/api/health (no auth, for uptime checks) and /api/config (app-wide settings)."""
from fastapi import APIRouter, Depends

from api.auth import TelegramIdentity
from api.deps import get_identity
from api.schemas import ConfigOut, HealthOut, LanguageOption, ProfileRules
from config import config
from database.enums import Diet, Equipment, Experience, Goal, Injury, Sex
from services import validation
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
        profile_rules=ProfileRules(
            age=validation.AGE_RANGE,
            height_cm=validation.HEIGHT_RANGE_CM,
            weight_kg=validation.WEIGHT_RANGE_KG,
            training_days=validation.TRAINING_DAYS_RANGE,
            goals=list(Goal), sexes=list(Sex), experience=list(Experience),
            equipment=list(Equipment), injuries=list(Injury), diets=list(Diet),
        ),
    )
