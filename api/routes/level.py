"""
Stage 6: level, XP, character, achievements and deleting your data from the Mini App.

    GET    /api/me/level       level, XP, next level, streak, energy, mood, stats
    GET    /api/achievements   every achievement with progress (earned ones are unlocked first)
    DELETE /api/me             delete ALL your data (body: {"confirm": "DELETE"}), same as /deleteme
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import TelegramIdentity
from api.deps import get_identity, get_session, get_user
from database.models import User
from services import levels, users

router = APIRouter(prefix="/api", tags=["level"])


class DeleteIn(BaseModel):
    confirm: Literal["DELETE"]   # anything else is refused (422), so a stray tap can't delete


def _require_profile(user: User) -> None:
    if user.profile is None:
        raise HTTPException(status_code=409, detail="profile_required")


@router.get("/me/level")
async def get_level(user: User = Depends(get_user), session: AsyncSession = Depends(get_session)) -> dict:
    _require_profile(user)
    return await levels.level_view(session, user)


@router.get("/achievements")
async def get_achievements(user: User = Depends(get_user),
                           session: AsyncSession = Depends(get_session)) -> dict:
    _require_profile(user)
    return await levels.achievements_view(session, user)


@router.delete("/me", status_code=204)
async def delete_me(body: DeleteIn, identity: TelegramIdentity = Depends(get_identity),
                    session: AsyncSession = Depends(get_session)) -> Response:
    """Deletes the user row; every table that belongs to the user cascades (tests/test_privacy.py)."""
    await users.delete_user_data(session, identity.telegram_id)
    return Response(status_code=204)
