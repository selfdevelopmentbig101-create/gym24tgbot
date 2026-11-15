"""
Save, load and change workout programs in the database.

A user can have several programs; exactly one is current (is_current). The bot's
Workout and Plan screens use the current one (get_plan), so they work unchanged.
"""
import logging
from datetime import date

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import PlanDay, PlanExercise, User, WorkoutPlan
from services.exercises import UserFilter, load_catalog, pick_substitute
from services.plan_generator import SPLITS, PlanSpec, generate_plan

logger = logging.getLogger(__name__)

# Changing any of these profile fields regenerates the plan.
PLAN_FIELDS = {"experience", "training_days", "equipment", "injuries"}
TEMPLATE_DAYS = tuple(sorted(SPLITS))  # built-in programs: 2-6 days a week


def _owned(user: User):
    return select(WorkoutPlan).where(WorkoutPlan.user_id == user.id)


async def get_plan(session: AsyncSession, user: User) -> WorkoutPlan | None:
    """The current program."""
    return await session.scalar(_owned(user).where(WorkoutPlan.is_current.is_(True))
                                .order_by(WorkoutPlan.id.desc()))


async def get_program(session: AsyncSession, user: User, program_id: int) -> WorkoutPlan | None:
    """Any of the user's programs (None if it isn't theirs)."""
    return await session.scalar(_owned(user).where(WorkoutPlan.id == program_id))


async def list_programs(session: AsyncSession, user: User) -> list[WorkoutPlan]:
    return list(await session.scalars(
        _owned(user).order_by(WorkoutPlan.is_current.desc(), WorkoutPlan.id.desc())))


def _days_from_spec(spec: PlanSpec) -> list[PlanDay]:
    days = []
    for day_index, day in enumerate(spec.days):
        plan_day = PlanDay(day_index=day_index, name_key=day.name_key, suffix=day.suffix)
        for position, item in enumerate(day.exercises):
            plan_day.exercises.append(PlanExercise(
                position=position, exercise_id=item.exercise_id, sets=item.sets,
                rep_min=item.rep_min, rep_max=item.rep_max, timed=item.timed,
                rest_seconds=item.rest_seconds,
            ))
        days.append(plan_day)
    return days


async def _spec(session: AsyncSession, user: User, days: int, goal: str) -> PlanSpec | None:
    if user.profile is None:
        raise ValueError("User has no profile")
    catalog = await load_catalog(session)
    if not catalog:
        logger.error("No exercises in the database; run import_exercises.py")
        return None
    return generate_plan(list(catalog.values()), UserFilter.from_profile(user.profile), days, goal)


async def _reload(session: AsyncSession, program: WorkoutPlan) -> WorkoutPlan:
    """Reload so program.days[...].exercises[...].exercise are all populated."""
    program_id = program.id
    session.expunge(program)
    return await session.scalar(select(WorkoutPlan).where(WorkoutPlan.id == program_id))


async def _fill_from_template(session: AsyncSession, user: User, program: WorkoutPlan,
                              days: int) -> bool:
    """Replace the program's days with a fresh template plan for the profile."""
    spec = await _spec(session, user, days, program.goal)
    if spec is None:
        return False
    if program.id is not None:
        await session.execute(delete(PlanDay).where(PlanDay.plan_id == program.id))
        await session.refresh(program, ["days"])
    program.split, program.template_days, program.kind, program.edited = spec.split, days, "template", False
    program.days.extend(_days_from_spec(spec))
    return True


async def make_current(session: AsyncSession, user: User, program: WorkoutPlan) -> None:
    await session.execute(update(WorkoutPlan).where(WorkoutPlan.user_id == user.id,
                                                    WorkoutPlan.id != program.id)
                          .values(is_current=False))
    if not program.is_current or program.started_on is None:
        program.started_on = date.today()
    program.is_current = True


async def generate_for_user(session: AsyncSession, user: User,
                            days: int | None = None) -> WorkoutPlan | None:
    """
    A fresh template program for the profile (or `days` a week), made current.
    A current template program is rebuilt in place; a custom one is kept in the
    user's saved programs and a new one is created.
    """
    if days is None:
        days = user.profile.training_days if user.profile else 3
    current = await get_plan(session, user)
    if current is not None and current.kind == "template":
        program = current
    else:
        program = WorkoutPlan(user_id=user.id, split="", is_current=True, days=[])
    if not await _fill_from_template(session, user, program, days):
        return None
    if program.id is None:
        session.add(program)
        await session.flush()
    await make_current(session, user, program)
    await session.commit()
    logger.info("Plan generated (%s, %s days)", program.split, len(program.days))
    return await _reload(session, program)


async def rebuild_for_profile(session: AsyncSession, user: User, changed: set[str]) -> bool:
    """
    After profile changes: rebuild the current program if it's an unedited template
    and a plan-relevant field changed. Programs the user built or edited are left alone.
    Returns True if it was rebuilt (or created because there was none).
    """
    if not changed & PLAN_FIELDS:
        return False
    current = await get_plan(session, user)
    if current is None:
        return await generate_for_user(session, user) is not None
    if current.kind != "template" or current.edited:
        return False
    days = user.profile.training_days if "training_days" in changed else current.template_days
    return await generate_for_user(session, user, days) is not None


async def get_or_create_plan(session: AsyncSession, user: User) -> WorkoutPlan | None:
    return await get_plan(session, user) or await generate_for_user(session, user)


async def get_plan_exercise(session: AsyncSession, user: User,
                            plan_exercise_id: int) -> PlanExercise | None:
    """A plan entry, only if it belongs to this user's current plan."""
    return await session.scalar(
        select(PlanExercise)
        .join(PlanDay, PlanExercise.day_id == PlanDay.id)
        .join(WorkoutPlan, PlanDay.plan_id == WorkoutPlan.id)
        .where(PlanExercise.id == plan_exercise_id, WorkoutPlan.user_id == user.id,
               WorkoutPlan.is_current.is_(True))
        # Load the whole day (needed for Next and position), avoiding lazy loads.
        .options(selectinload(PlanExercise.day).selectinload(PlanDay.exercises)
                 .selectinload(PlanExercise.exercise))
    )


async def substitute_in_plan(session: AsyncSession, user: User,
                             entry: PlanExercise) -> PlanExercise | None:
    """Swap a plan entry for a suitable substitute. Returns None if there's none."""
    catalog = await load_catalog(session)
    current = catalog.get(entry.exercise_id) or entry.exercise
    day = await session.get(PlanDay, entry.day_id)
    in_day = {e.exercise_id for e in day.exercises}
    substitute = pick_substitute(current, catalog, UserFilter.from_profile(user.profile),
                                 exclude_ids=in_day)
    if substitute is None:
        return None
    entry.exercise_id = substitute.id
    entry.exercise = substitute
    # A swap isn't a structural edit: profile changes may still rebuild the program.
    await session.commit()
    logger.info("Plan exercise substituted")
    return entry
