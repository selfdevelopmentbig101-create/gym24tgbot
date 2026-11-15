"""
Stage 4: programs, the split editor, the calendar and the energy system.

    GET    /api/plan                                  current program + days + weekly volume
    POST   /api/plan/days                             add a day (filled with default exercises)
    PATCH  /api/plan/days/{day_id}                    rename / move a day
    DELETE /api/plan/days/{day_id}                    remove a day
    POST   /api/plan/days/{day_id}/exercises          add an exercise (from the library)
    PATCH  /api/plan/exercises/{entry_id}             sets, reps, rest, position
    DELETE /api/plan/exercises/{entry_id}             remove an exercise
    POST   /api/plan/exercises/{entry_id}/substitute  swap (substitute_ids, equipment, injuries)
    GET    /api/programs?tab=current|available|created
    POST   /api/programs                              create a program
    POST   /api/programs/templates/{key}/start        start a built-in program
    GET / PATCH / DELETE /api/programs/{id}
    POST   /api/programs/{id}/activate                make it the current program
    POST   /api/programs/{id}/reset                   back to default days
    GET    /api/calendar?month=YYYY-MM                done / planned / missed / rest
    GET    /api/energy?day={day_id}                   session load + weekly volume, with warnings

Every editor change answers with the updated plan, so the app redraws in one step.
The user always comes from verified initData (get_user); ids in the path are
checked against that user's own data.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, get_user
from api.schemas_plan import DayIn, DayPatch, EntryPatch, ExerciseIn, ProgramIn, ProgramPatch
from database.models import User
from services import library, programs
from services.programs import ProgramError

router = APIRouter(prefix="/api", tags=["plan"])


async def _guard(awaitable):
    """ProgramError -> HTTP error with its code (the app translates the code)."""
    try:
        return await awaitable
    except ProgramError as error:
        raise HTTPException(status_code=error.status, detail=error.code) from None


def _images(request: Request):
    folder = request.app.state.exercise_images
    return lambda exercise_id: library.media(exercise_id, folder).still


async def _plan(request: Request, user: User, session: AsyncSession) -> dict:
    return await _guard(programs.plan_view(session, user, _images(request)))


# ---------- current plan and split editor ----------

@router.get("/plan")
async def get_plan(request: Request, user: User = Depends(get_user),
                   session: AsyncSession = Depends(get_session)) -> dict:
    return await _plan(request, user, session)


@router.post("/plan/days")
async def add_day(body: DayIn, request: Request, user: User = Depends(get_user),
                  session: AsyncSession = Depends(get_session)) -> dict:
    await _guard(programs.add_day(session, user, body.title))
    return await _plan(request, user, session)


@router.patch("/plan/days/{day_id}")
async def update_day(day_id: int, body: DayPatch, request: Request, user: User = Depends(get_user),
                     session: AsyncSession = Depends(get_session)) -> dict:
    await _guard(programs.update_day(session, user, day_id, body.model_dump(exclude_unset=True)))
    return await _plan(request, user, session)


@router.delete("/plan/days/{day_id}")
async def delete_day(day_id: int, request: Request, user: User = Depends(get_user),
                     session: AsyncSession = Depends(get_session)) -> dict:
    await _guard(programs.delete_day(session, user, day_id))
    return await _plan(request, user, session)


@router.post("/plan/days/{day_id}/exercises")
async def add_exercise(day_id: int, body: ExerciseIn, request: Request, user: User = Depends(get_user),
                       session: AsyncSession = Depends(get_session)) -> dict:
    await _guard(programs.add_exercise(session, user, day_id, body.exercise_id,
                                       body.sets, body.rep_min, body.rep_max))
    return await _plan(request, user, session)


@router.patch("/plan/exercises/{entry_id}")
async def update_exercise(entry_id: int, body: EntryPatch, request: Request,
                          user: User = Depends(get_user),
                          session: AsyncSession = Depends(get_session)) -> dict:
    await _guard(programs.update_exercise(session, user, entry_id, body.model_dump(exclude_unset=True)))
    return await _plan(request, user, session)


@router.delete("/plan/exercises/{entry_id}")
async def delete_exercise(entry_id: int, request: Request, user: User = Depends(get_user),
                          session: AsyncSession = Depends(get_session)) -> dict:
    await _guard(programs.delete_exercise(session, user, entry_id))
    return await _plan(request, user, session)


@router.post("/plan/exercises/{entry_id}/substitute")
async def substitute_exercise(entry_id: int, request: Request, user: User = Depends(get_user),
                              session: AsyncSession = Depends(get_session)) -> dict:
    await _guard(programs.substitute_exercise(session, user, entry_id))
    return await _plan(request, user, session)


# ---------- programs ----------

@router.get("/programs")
async def list_programs(tab: Literal["current", "available", "created"] = Query("current"),
                        user: User = Depends(get_user),
                        session: AsyncSession = Depends(get_session)) -> dict:
    return {"tab": tab, "items": await _guard(programs.list_programs(session, user, tab))}


@router.post("/programs", status_code=201)
async def create_program(body: ProgramIn, user: User = Depends(get_user),
                         session: AsyncSession = Depends(get_session)) -> dict:
    program = await _guard(programs.create_program(
        session, user, body.name, body.weeks, body.workouts_per_week, body.goal, body.activate))
    return programs.program_item(program)


@router.post("/programs/templates/{key}/start")
async def start_template(key: str, request: Request, user: User = Depends(get_user),
                         session: AsyncSession = Depends(get_session)) -> dict:
    await _guard(programs.start_template(session, user, key))
    return await _plan(request, user, session)


@router.get("/programs/{program_id}")
async def get_program(program_id: int, user: User = Depends(get_user),
                      session: AsyncSession = Depends(get_session)) -> dict:
    return await _guard(programs.program_detail(session, user, program_id))


@router.patch("/programs/{program_id}")
async def update_program(program_id: int, body: ProgramPatch, user: User = Depends(get_user),
                         session: AsyncSession = Depends(get_session)) -> dict:
    program = await _guard(programs.update_program(session, user, program_id,
                                                   body.model_dump(exclude_unset=True)))
    return programs.program_item(program)


@router.delete("/programs/{program_id}", status_code=204)
async def delete_program(program_id: int, user: User = Depends(get_user),
                         session: AsyncSession = Depends(get_session)) -> Response:
    await _guard(programs.delete_program(session, user, program_id))
    return Response(status_code=204)


@router.post("/programs/{program_id}/activate")
async def activate_program(program_id: int, request: Request, user: User = Depends(get_user),
                           session: AsyncSession = Depends(get_session)) -> dict:
    await _guard(programs.activate_program(session, user, program_id))
    return await _plan(request, user, session)


@router.post("/programs/{program_id}/reset")
async def reset_program(program_id: int, request: Request, user: User = Depends(get_user),
                        session: AsyncSession = Depends(get_session)) -> dict:
    await _guard(programs.reset_program(session, user, program_id))
    return await _plan(request, user, session)


# ---------- calendar and energy ----------

@router.get("/calendar")
async def calendar(month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM"),
                   user: User = Depends(get_user),
                   session: AsyncSession = Depends(get_session)) -> dict:
    year, number = (int(part) for part in month.split("-"))
    return await _guard(programs.calendar(session, user, year, number))


@router.get("/energy")
async def energy(day: int = Query(..., ge=1, description="Plan day id"), user: User = Depends(get_user),
                 session: AsyncSession = Depends(get_session)) -> dict:
    return await _guard(programs.day_energy(session, user, day))
