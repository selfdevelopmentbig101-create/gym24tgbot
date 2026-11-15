"""
Stage 7: the Home tab.

    GET /api/home   greeting part of day, next workout (or the one in progress),
                    this week's summary, today's calories/protein, latest weight
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, get_user
from database.models import User
from services import home

router = APIRouter(prefix="/api", tags=["home"])


@router.get("/home")
async def get_home(user: User = Depends(get_user), session: AsyncSession = Depends(get_session)) -> dict:
    if user.profile is None:
        raise HTTPException(status_code=409, detail="profile_required")
    return await home.home_view(session, user)
