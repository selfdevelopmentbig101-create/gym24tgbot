"""
Stage 5: the Train tab (workout-day screen and live logger).

    GET    /api/train                                    active workout + every program day (last time's numbers)
    POST   /api/workouts                                 start a plan day (409 workout_active unless force)
    GET    /api/workouts/{id}                            live state
    POST   /api/workouts/{id}/sets                       log a set (kg, reps, optional RPE, warm-up)
    PATCH  /api/workouts/{id}/sets/{set_id}              fix a set
    DELETE /api/workouts/{id}/sets/{set_id}              remove a set
    PATCH  /api/workouts/{id}/items/{index}              note, superset group (A1/B1 labels)
    POST   /api/workouts/{id}/items/{index}/substitute   swap before any set is logged
    POST   /api/workouts/{id}/finish                     summary: PRs, next-time suggestions

The rest timer runs in the app (no server needed). The workout id in the path is
always checked against the logged-in user (from verified initData).
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, get_user
from api.schemas_train import ItemPatch, SetIn, SetPatch, StartIn
from database.models import User
from services import library, train, workouts
from services.programs import ProgramError
from services.train import TrainError

router = APIRouter(prefix="/api", tags=["train"])


async def _guard(awaitable):
    """Known errors -> HTTP errors with a code the app translates."""
    try:
        return await awaitable
    except (TrainError, ProgramError) as error:
        raise HTTPException(status_code=error.status, detail=error.code) from None
    except workouts.LogError as error:
        raise HTTPException(status_code=422, detail=error.text_key) from None


def _images(request: Request):
    folder = request.app.state.exercise_images
    return lambda exercise_id: library.media(exercise_id, folder).still


async def _view(request: Request, user: User, session: AsyncSession, ws) -> dict:
    return await train.workout_view(session, user, ws, _images(request))


@router.get("/train")
async def overview(request: Request, user: User = Depends(get_user),
                   session: AsyncSession = Depends(get_session)) -> dict:
    return await _guard(train.overview(session, user, _images(request)))


@router.post("/workouts", status_code=201)
async def start(body: StartIn, request: Request, user: User = Depends(get_user),
                session: AsyncSession = Depends(get_session)) -> dict:
    ws = await _guard(train.start_workout(session, user, body.day_index, body.force))
    return await _view(request, user, session, ws)


@router.get("/workouts/{workout_id}")
async def get_workout(workout_id: int, request: Request, user: User = Depends(get_user),
                      session: AsyncSession = Depends(get_session)) -> dict:
    ws = await _guard(train.open_workout(session, user, workout_id, editable=False))
    return await _view(request, user, session, ws)


@router.post("/workouts/{workout_id}/sets", status_code=201)
async def log_set(workout_id: int, body: SetIn, request: Request, user: User = Depends(get_user),
                  session: AsyncSession = Depends(get_session)) -> dict:
    ws = await _guard(train.open_workout(session, user, workout_id))
    entry = await _guard(workouts.log_set(session, user, ws, body.weight_kg, body.reps,
                                          index=body.index, rpe=body.rpe, warmup=body.warmup))
    logged = {**train.set_dict(entry), "estimate": entry.estimate, "previous_best": entry.previous_best}
    return {"set": logged, "workout": await _view(request, user, session, ws)}


@router.patch("/workouts/{workout_id}/sets/{set_id}")
async def edit_set(workout_id: int, set_id: int, body: SetPatch, request: Request,
                   user: User = Depends(get_user), session: AsyncSession = Depends(get_session)) -> dict:
    ws = await _guard(train.open_workout(session, user, workout_id))
    await _guard(workouts.edit_set(session, user, ws, set_id, body.model_dump(exclude_unset=True)))
    return await _view(request, user, session, ws)


@router.delete("/workouts/{workout_id}/sets/{set_id}")
async def delete_set(workout_id: int, set_id: int, request: Request, user: User = Depends(get_user),
                     session: AsyncSession = Depends(get_session)) -> dict:
    ws = await _guard(train.open_workout(session, user, workout_id))
    await _guard(workouts.delete_set(session, ws, set_id))
    return await _view(request, user, session, ws)


@router.patch("/workouts/{workout_id}/items/{index}")
async def update_item(workout_id: int, index: int, body: ItemPatch, request: Request,
                      user: User = Depends(get_user), session: AsyncSession = Depends(get_session)) -> dict:
    ws = await _guard(train.open_workout(session, user, workout_id))
    await _guard(workouts.update_item(session, ws, index, body.model_dump(exclude_unset=True)))
    return await _view(request, user, session, ws)


@router.post("/workouts/{workout_id}/items/{index}/substitute")
async def substitute(workout_id: int, index: int, request: Request, user: User = Depends(get_user),
                     session: AsyncSession = Depends(get_session)) -> dict:
    ws = await _guard(train.open_workout(session, user, workout_id))
    await _guard(train.substitute_item(session, user, ws, index))
    return await _view(request, user, session, ws)


@router.post("/workouts/{workout_id}/finish")
async def finish(workout_id: int, user: User = Depends(get_user),
                 session: AsyncSession = Depends(get_session)) -> dict:
    ws = await _guard(train.open_workout(session, user, workout_id))
    return await _guard(train.finish_workout(session, user, ws))
