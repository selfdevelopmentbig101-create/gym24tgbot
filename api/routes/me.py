"""/api/me: who is using the Mini App, and their language (shared with the bot)."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import TelegramIdentity
from api.deps import get_identity, get_session, get_user
from api.schemas import LanguageIn, MeOut
from database.models import User
from services import users
from utils.texts import resolve_language

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/me", tags=["me"])


def _me(user: User, identity: TelegramIdentity) -> MeOut:
    return MeOut(
        first_name=identity.first_name,
        language=user.language,
        # Not chosen yet: follow the Telegram app language, like the bot does.
        language_effective=user.language or resolve_language(identity.language_code),
        disclaimer_accepted=user.disclaimer_accepted_at is not None,
        profile_complete=user.profile is not None,
    )


@router.get("", response_model=MeOut)
async def get_me(user: User = Depends(get_user),
                 identity: TelegramIdentity = Depends(get_identity)) -> MeOut:
    return _me(user, identity)


@router.patch("/language", response_model=MeOut)
async def set_language(body: LanguageIn, user: User = Depends(get_user),
                       identity: TelegramIdentity = Depends(get_identity),
                       session: AsyncSession = Depends(get_session)) -> MeOut:
    """Same field the bot's /language command changes (users.language)."""
    await users.set_language(session, user, body.language)
    logger.info("Language changed from the Mini App")
    return _me(user, identity)
