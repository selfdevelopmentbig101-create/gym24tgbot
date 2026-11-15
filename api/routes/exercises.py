"""/api/exercises: the exercise library (search, filters, detail, substitutes)."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import TelegramIdentity
from api.deps import get_identity, get_session, get_user
from api.schemas import ExerciseDetail, ExerciseItem, ExerciseList, ExerciseMedia, MediaReport
from database.models import Exercise, User
from services import library
from services.exercise_import import DIFFICULTIES
from services.exercises import UserFilter, get_injury_rules, is_available, load_catalog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/exercises", tags=["exercises"])


def _user_filter(user: User) -> UserFilter | None:
    return UserFilter.from_profile(user.profile) if user.profile is not None else None


def _item(ex: Exercise, request: Request, user: UserFilter | None) -> ExerciseItem:
    return ExerciseItem(
        id=ex.id, name=ex.name, muscle_group=ex.muscle_group,
        secondary_muscles=list(ex.secondary_muscles or []), equipment=ex.equipment,
        difficulty=ex.difficulty, movement_type=ex.movement_type, home_friendly=bool(ex.home_friendly),
        image=library.media(ex.id, request.app.state.exercise_images).still,
        fits=None if user is None else is_available(ex, user, get_injury_rules()),
    )


@router.get("", response_model=ExerciseList)
async def list_exercises(
    request: Request,
    q: str = Query("", max_length=library.MAX_QUERY, description="Name or muscle, any language"),
    muscle: str | None = Query(None, max_length=40, description="Primary or secondary muscle"),
    equipment: str | None = Query(None, max_length=40),
    difficulty: str | None = Query(None, max_length=20),
    home: bool = Query(False, description="Home-friendly only"),
    fits: bool = Query(False, description="Only exercises that fit my profile"),
    user: User = Depends(get_user),
    session: AsyncSession = Depends(get_session),
) -> ExerciseList:
    catalog = list((await load_catalog(session)).values())
    user_filter = _user_filter(user)
    found = library.search(catalog, library.Filters(q=q, muscle=muscle, equipment=equipment,
                                                    difficulty=difficulty, home=home, fits=fits),
                           user_filter)
    muscles: list[str] = []
    for ex in catalog:
        if ex.muscle_group not in muscles:
            muscles.append(ex.muscle_group)
    return ExerciseList(
        items=[_item(ex, request, user_filter) for ex in found],
        total=len(catalog),
        muscles=muscles,
        equipment=sorted({ex.equipment for ex in catalog}),
        difficulties=[d for d in DIFFICULTIES if any(ex.difficulty == d for ex in catalog)],
    )


# Declared before /{exercise_id}, so "media-report" isn't taken for an exercise id.
@router.get("/media-report", response_model=MediaReport)
async def media_report(request: Request, identity: TelegramIdentity = Depends(get_identity),
                       session: AsyncSession = Depends(get_session)) -> MediaReport:
    """Admins only (ADMIN_IDS): which exercises still need images."""
    if identity.telegram_id not in request.app.state.admin_ids:
        raise HTTPException(status_code=403, detail="admins_only")
    catalog = list((await load_catalog(session)).values())
    return MediaReport(**library.media_report(catalog, request.app.state.exercise_images))


@router.get("/{exercise_id}", response_model=ExerciseDetail)
async def get_exercise(exercise_id: str, request: Request, user: User = Depends(get_user),
                       session: AsyncSession = Depends(get_session)) -> ExerciseDetail:
    catalog = await load_catalog(session)
    ex = catalog.get(exercise_id)
    if ex is None:
        raise HTTPException(status_code=404, detail="no_exercise")
    user_filter = _user_filter(user)
    m = library.media(ex.id, request.app.state.exercise_images)
    return ExerciseDetail(
        **_item(ex, request, user_filter).model_dump(),
        media=ExerciseMedia(kind=m.kind, start=m.start, peak=m.peak, still=m.still),
        visual_type=ex.visual_type or "images",
        form_tips=(ex.form_tips or "").strip() or None,
        reasons=[] if user_filter is None else library.unavailable_reasons(ex, user_filter),
        substitutes=[_item(s, request, user_filter)
                     for s in library.substitutes(ex, catalog, user_filter)],
    )
