"""User and profile storage. Every function takes an AsyncSession, so callers
control the transaction."""
import logging

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.enums import Diet, Equipment, Experience, Goal, Injury, Sex
from database.models import Profile, User, utcnow
from services import validation
from utils.texts import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

# Optional profile fields: may be left out of save_profile().
OPTIONAL_PROFILE_FIELDS = ("target_weight_kg",)

PROFILE_FIELDS = (
    "goal", "age", "sex", "height_cm", "weight_kg", "experience",
    "training_days", "equipment", "injuries", "diet",
)


def clean_profile_value(field_name: str, value):
    """Validate one profile field. Raises ValidationError or ValueError."""
    converters = {
        "goal": Goal,
        "sex": Sex,
        "experience": Experience,
        "equipment": Equipment,
        "diet": Diet,
        "age": validation.validate_age,
        "height_cm": validation.validate_height,
        "weight_kg": validation.validate_weight,
        "training_days": validation.validate_training_days,
        # Optional (Mini App onboarding); None clears it.
        "target_weight_kg": lambda v: None if v is None else validation.validate_target_weight(v),
        # Keep only known injury codes, without duplicates, in a stable order.
        "injuries": lambda items: sorted({Injury(i).value for i in items or []}),
    }
    if field_name not in converters:
        raise ValueError(f"Unknown profile field: {field_name}")
    return converters[field_name](value)


async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    user = await get_user(session, telegram_id)
    if user is None:
        # profile=None marks the relationship as loaded, so reading user.profile
        # later doesn't trigger a lazy load (not allowed with async SQLAlchemy).
        # language stays None until the user picks one.
        user = User(telegram_id=telegram_id, profile=None)
        session.add(user)
        await session.commit()
        logger.info("New user registered (internal id=%s)", user.id)
    return user


async def set_language(session: AsyncSession, user: User, code: str) -> User:
    """Save the user's chosen language (used by both the bot and the API)."""
    if code not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {code}")
    user.language = code
    await session.commit()
    return user


async def accept_disclaimer(session: AsyncSession, user: User) -> None:
    user.disclaimer_accepted_at = utcnow()
    await session.commit()


async def save_profile(session: AsyncSession, user: User, data: dict) -> Profile:
    """Create or fully replace the profile. `data` must contain every field."""
    missing = [name for name in PROFILE_FIELDS if name not in data]
    if missing:
        raise ValueError(f"Missing profile fields: {missing}")
    clean = {name: clean_profile_value(name, data[name]) for name in PROFILE_FIELDS}
    clean.update({name: clean_profile_value(name, data[name])
                  for name in OPTIONAL_PROFILE_FIELDS if name in data})

    if user.profile is None:
        user.profile = Profile(**clean)
    else:
        for name, value in clean.items():
            setattr(user.profile, name, value)
    await session.commit()
    return user.profile


async def update_profile_field(
    session: AsyncSession, user: User, field_name: str, value
) -> Profile:
    if user.profile is None:
        raise ValueError("User has no profile yet")
    old = getattr(user.profile, field_name)
    setattr(user.profile, field_name, clean_profile_value(field_name, value))
    if field_name == "goal" and getattr(user.profile, field_name) != old:
        # Calorie tweaks were tuned for the old goal: start fresh.
        user.profile.calorie_adjust = 0
    await session.commit()
    return user.profile


async def delete_user_data(session: AsyncSession, telegram_id: int) -> bool:
    """Delete the user and, via ON DELETE CASCADE, everything they own."""
    result = await session.execute(delete(User).where(User.telegram_id == telegram_id))
    await session.commit()
    deleted = result.rowcount > 0
    if deleted:
        logger.info("User data deleted on request")
    return deleted


async def count_users(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(User)) or 0
