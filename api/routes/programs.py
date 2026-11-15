"""
/api/programs, /api/days, /api/calendar, /api/energy: the Plan tab.

Every program, day and exercise is looked up through the verified user, so one
user can never read or change another user's programs (404, not 403, so ids
aren't confirmed to exist).
"""
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session, get_user
from api.routes.exercises import exercise_item
from api.schemas import (CalendarDayOut, CalendarOut, DayCreate, DayPatch, EnergyOut, ItemCreate,
                         ItemPatch, PlanDayOut, PlanItemOut, ProgramCreate, ProgramDetail,
                         ProgramPatch, ProgramsOut, ProgramSummary, SubstituteIn, TemplateOut)
from database.models import PlanDay, PlanExercise, User, WorkoutPlan
from services import plans, programs
from services.exercises import UserFilter
from services.plan_generator import SPLITS
from services.programs import ProgramError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["programs"])


def _fail(error: ProgramError) -> HTTPException:
    return HTTPException(status_code=error.status, detail=error.code)


def _profile_required(user: User) -> None:
    if user.profile is None:
        raise HTTPException(status_code=409, detail="no_profile")


def _filter(user: User) -> UserFilter | None:
    return UserFilter.from_profile(user.profile) if user.profile else None


def _day_out(day: PlanDay, request: Request, user_filter: UserFilter | None, with_items: bool) -> PlanDayOut:
    load = programs.day_load(day)
    custom = day.name_key.startswith("~")
    return PlanDayOut(
        id=day.id, program_id=day.plan_id, index=day.day_index,
        name_key="custom" if custom else day.name_key,
        suffix=day.suffix, name=day.name_key[1:] if custom else None,
        exercises=[PlanItemOut(id=item.id, exercise=exercise_item(item.exercise, request, user_filter),
                               sets=item.sets, rep_min=item.rep_min, rep_max=item.rep_max,
                               timed=item.timed, rest_seconds=item.rest_seconds)
                   for item in day.exercises] if with_items else [],
        sets=load.sets, minutes=load.minutes,
    )


async def _summary(session: AsyncSession, user: User, program: WorkoutPlan, request: Request,
                   detail: bool = False):
    p = await programs.progress(session, user, program)
    user_filter = _filter(user)
    fields = dict(
        id=program.id, name=program.name, split=program.split, kind=program.kind,
        template_days=program.template_days, goal=program.goal, weeks=program.weeks,
        workouts_per_week=len(program.days), is_current=program.is_current, edited=program.edited,
        started_on=program.started_on, ends_on=p.ends_on, week=p.week, completed=p.completed,
        total=p.total, next_day_index=p.next_day_index,
        day_names=[_day_out(d, request, user_filter, False) for d in program.days],
    )
    if detail:
        return ProgramDetail(**fields, days=[_day_out(d, request, user_filter, True) for d in program.days])
    return ProgramSummary(**fields)


async def _program(program_id: int, user: User, session: AsyncSession) -> WorkoutPlan:
    program = await plans.get_program(session, user, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="no_program")
    return program


async def _day(day_id: int, user: User, session: AsyncSession) -> tuple[WorkoutPlan, PlanDay]:
    day = await session.get(PlanDay, day_id)
    program = await plans.get_program(session, user, day.plan_id) if day is not None else None
    if program is None:
        raise HTTPException(status_code=404, detail="no_day")
    return program, next(d for d in program.days if d.id == day_id)


def _item(day: PlanDay, item_id: int) -> PlanExercise:
    item = next((i for i in day.exercises if i.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="no_item")
    return item


async def _detail(session: AsyncSession, user: User, program: WorkoutPlan, request: Request) -> ProgramDetail:
    return await _summary(session, user, await programs.reload(session, program), request, detail=True)


async def _day_detail(session: AsyncSession, user: User, program: WorkoutPlan, day_id: int,
                      request: Request) -> PlanDayOut:
    program = await programs.reload(session, program)
    return _day_out(next(d for d in program.days if d.id == day_id), request, _filter(user), True)


# ---------- Programs ----------

@router.get("/programs", response_model=ProgramsOut)
async def list_programs(request: Request, user: User = Depends(get_user),
                        session: AsyncSession = Depends(get_session)) -> ProgramsOut:
    """Current, Created (saved) and Available (built-in) programs."""
    current, created = None, []
    for program in await plans.list_programs(session, user):
        summary = await _summary(session, user, program, request)
        if program.is_current and current is None:
            current = summary
        else:
            created.append(summary)
    profile_days = user.profile.training_days if user.profile else None
    available = [TemplateOut(days=days, split=split, recommended=days == profile_days,
                             day_keys=[key for _, key, _ in layout])
                 for days, (split, layout) in sorted(SPLITS.items())]
    return ProgramsOut(current=current, created=created, available=available)


@router.post("/programs", response_model=ProgramDetail, status_code=201)
async def create_program(body: ProgramCreate, request: Request, user: User = Depends(get_user),
                         session: AsyncSession = Depends(get_session)) -> ProgramDetail:
    """Custom (empty days to fill) or from a built-in program (template_days)."""
    _profile_required(user)
    try:
        if body.template_days is not None:
            program = await programs.create_from_template(session, user, body.template_days, body.goal,
                                                          body.weeks, body.name, body.activate)
        else:
            program = await programs.create_custom(session, user, body.name or "", body.weeks,
                                                   body.workouts_per_week, body.goal, body.activate)
    except ProgramError as error:
        raise _fail(error) from None
    return await _summary(session, user, program, request, detail=True)


@router.get("/programs/{program_id}", response_model=ProgramDetail)
async def get_program(program_id: int, request: Request, user: User = Depends(get_user),
                      session: AsyncSession = Depends(get_session)) -> ProgramDetail:
    return await _summary(session, user, await _program(program_id, user, session), request, detail=True)


@router.patch("/programs/{program_id}", response_model=ProgramDetail)
async def patch_program(program_id: int, body: ProgramPatch, request: Request,
                        user: User = Depends(get_user),
                        session: AsyncSession = Depends(get_session)) -> ProgramDetail:
    """Rename (null = split name), weeks, training goal (re-sets sets/reps/rest for it)."""
    _profile_required(user)
    program = await _program(program_id, user, session)
    sent = body.model_dump(exclude_unset=True)
    try:
        program = await programs.update_program(
            session, program, user, name=sent.get("name"),
            clear_name="name" in sent and sent["name"] is None,
            weeks=sent.get("weeks"), goal=sent.get("goal"))
    except ProgramError as error:
        raise _fail(error) from None
    return await _summary(session, user, program, request, detail=True)


@router.delete("/programs/{program_id}", status_code=204)
async def delete_program(program_id: int, user: User = Depends(get_user),
                         session: AsyncSession = Depends(get_session)) -> None:
    try:
        await programs.delete_program(session, await _program(program_id, user, session))
    except ProgramError as error:
        raise _fail(error) from None


@router.post("/programs/{program_id}/activate", response_model=ProgramDetail)
async def activate_program(program_id: int, request: Request, user: User = Depends(get_user),
                           session: AsyncSession = Depends(get_session)) -> ProgramDetail:
    """Make it the current program (the bot's Workout and Plan follow it)."""
    try:
        program = await programs.activate(session, user, await _program(program_id, user, session))
    except ProgramError as error:
        raise _fail(error) from None
    return await _summary(session, user, program, request, detail=True)


@router.post("/programs/{program_id}/reset", response_model=ProgramDetail)
async def reset_program(program_id: int, request: Request, user: User = Depends(get_user),
                        session: AsyncSession = Depends(get_session)) -> ProgramDetail:
    """Built-in programs only: pick exercises again for the current profile."""
    _profile_required(user)
    try:
        program = await programs.reset(session, user, await _program(program_id, user, session))
    except ProgramError as error:
        raise _fail(error) from None
    return await _summary(session, user, program, request, detail=True)


# ---------- Days ----------

@router.post("/programs/{program_id}/days", response_model=ProgramDetail, status_code=201)
async def add_day(program_id: int, body: DayCreate, request: Request, user: User = Depends(get_user),
                  session: AsyncSession = Depends(get_session)) -> ProgramDetail:
    program = await _program(program_id, user, session)
    try:
        await programs.add_day(session, program, body.name)
    except ProgramError as error:
        raise _fail(error) from None
    return await _detail(session, user, program, request)


async def _program_day(program_id: int, day_id: int, user: User, session: AsyncSession):
    program, day = await _day(day_id, user, session)
    if program.id != program_id:
        raise HTTPException(status_code=404, detail="no_day")
    return program, day


@router.patch("/programs/{program_id}/days/{day_id}", response_model=ProgramDetail)
async def patch_day(program_id: int, day_id: int, body: DayPatch, request: Request,
                    user: User = Depends(get_user),
                    session: AsyncSession = Depends(get_session)) -> ProgramDetail:
    """Rename and/or move to `position` (0-based)."""
    program, day = await _program_day(program_id, day_id, user, session)
    try:
        await programs.update_day(session, program, day, name=body.name, position=body.position)
    except ProgramError as error:
        raise _fail(error) from None
    return await _detail(session, user, program, request)


@router.delete("/programs/{program_id}/days/{day_id}", response_model=ProgramDetail)
async def delete_day(program_id: int, day_id: int, request: Request, user: User = Depends(get_user),
                     session: AsyncSession = Depends(get_session)) -> ProgramDetail:
    program, day = await _program_day(program_id, day_id, user, session)
    try:
        await programs.delete_day(session, program, day)
    except ProgramError as error:
        raise _fail(error) from None
    return await _detail(session, user, program, request)


# ---------- Exercises in a day ----------

@router.get("/days/{day_id}", response_model=PlanDayOut)
async def get_day(day_id: int, request: Request, user: User = Depends(get_user),
                  session: AsyncSession = Depends(get_session)) -> PlanDayOut:
    program, _ = await _day(day_id, user, session)
    return await _day_detail(session, user, program, day_id, request)


@router.post("/days/{day_id}/exercises", response_model=PlanDayOut, status_code=201)
async def add_exercise(day_id: int, body: ItemCreate, request: Request, user: User = Depends(get_user),
                       session: AsyncSession = Depends(get_session)) -> PlanDayOut:
    """Add from the library; sets, reps and rest follow the program's training goal."""
    _profile_required(user)
    program, day = await _day(day_id, user, session)
    try:
        await programs.add_exercise(session, user, program, day, body.exercise_id)
    except ProgramError as error:
        raise _fail(error) from None
    return await _day_detail(session, user, program, day_id, request)


@router.patch("/days/{day_id}/exercises/{item_id}", response_model=PlanDayOut)
async def patch_exercise(day_id: int, item_id: int, body: ItemPatch, request: Request,
                         user: User = Depends(get_user),
                         session: AsyncSession = Depends(get_session)) -> PlanDayOut:
    """Sets, reps (seconds for timed exercises), rest, and/or position."""
    program, day = await _day(day_id, user, session)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    try:
        await programs.update_exercise(session, program, day, _item(day, item_id), changes)
    except ProgramError as error:
        raise _fail(error) from None
    return await _day_detail(session, user, program, day_id, request)


@router.delete("/days/{day_id}/exercises/{item_id}", response_model=PlanDayOut)
async def delete_exercise(day_id: int, item_id: int, request: Request, user: User = Depends(get_user),
                          session: AsyncSession = Depends(get_session)) -> PlanDayOut:
    program, day = await _day(day_id, user, session)
    await programs.delete_exercise(session, program, day, _item(day, item_id))
    return await _day_detail(session, user, program, day_id, request)


@router.post("/days/{day_id}/exercises/{item_id}/substitute", response_model=PlanDayOut)
async def substitute(day_id: int, item_id: int, body: SubstituteIn, request: Request,
                     user: User = Depends(get_user),
                     session: AsyncSession = Depends(get_session)) -> PlanDayOut:
    """Swap for a chosen exercise, or the best one for the user's equipment and injuries."""
    _profile_required(user)
    program, day = await _day(day_id, user, session)
    try:
        await programs.substitute(session, user, program, day, _item(day, item_id), body.exercise_id)
    except ProgramError as error:
        raise _fail(error) from None
    return await _day_detail(session, user, program, day_id, request)


# ---------- Calendar and load ----------

@router.get("/calendar", response_model=CalendarOut)
async def get_calendar(month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
                       user: User = Depends(get_user),
                       session: AsyncSession = Depends(get_session)) -> CalendarOut:
    """done / missed / planned / rest for each day of the month (default: this month)."""
    today = date.today()
    year, mon = (int(month[:4]), int(month[5:])) if month else (today.year, today.month)
    if not 2000 <= year <= 2100:
        raise HTTPException(status_code=422, detail="bad_month")
    days, schedule = await programs.calendar(session, user, year, mon)
    return CalendarOut(
        month=f"{year:04d}-{mon:02d}",
        days=[CalendarDayOut(date=d.day, status=d.status) for d in days],
        schedule=schedule,
        done=sum(d.status == "done" for d in days),
        planned=sum(d.day.weekday() in schedule for d in days),
    )


@router.get("/energy", response_model=EnergyOut)
async def get_energy(day: int, user: User = Depends(get_user),
                     session: AsyncSession = Depends(get_session)) -> EnergyOut:
    """Training load for a day and the program week, with warnings (never blocking)."""
    program, plan_day = await _day(day, user, session)
    return EnergyOut(**programs.energy(program, plan_day))
