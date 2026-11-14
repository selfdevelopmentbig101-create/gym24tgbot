"""Save, load and change workout plans in the database."""
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import PlanDay, PlanExercise, User, WorkoutPlan
from services.exercises import UserFilter, load_catalog, pick_substitute
from services.plan_generator import generate_plan

logger = logging.getLogger(__name__)

# Changing any of these profile fields regenerates the plan.
PLAN_FIELDS = {"experience", "training_days", "equipment", "injuries"}


async def get_plan(session: AsyncSession, user: User) -> WorkoutPlan | None:
    return await session.scalar(select(WorkoutPlan).where(WorkoutPlan.user_id == user.id))


async def generate_for_user(session: AsyncSession, user: User) -> WorkoutPlan | None:
    """Create a fresh plan from the profile, replacing any existing one."""
    if user.profile is None:
        raise ValueError("User has no profile")
    catalog = await load_catalog(session)
    if not catalog:
        logger.error("No exercises in the database; run import_exercises.py")
        return None

    spec = generate_plan(list(catalog.values()), UserFilter.from_profile(user.profile),
                         user.profile.training_days)

    await session.execute(delete(WorkoutPlan).where(WorkoutPlan.user_id == user.id))
    plan = WorkoutPlan(user_id=user.id, split=spec.split)
    for day_index, day in enumerate(spec.days):
        plan_day = PlanDay(day_index=day_index, name_key=day.name_key, suffix=day.suffix)
        for position, item in enumerate(day.exercises):
            plan_day.exercises.append(PlanExercise(
                position=position, exercise_id=item.exercise_id, sets=item.sets,
                rep_min=item.rep_min, rep_max=item.rep_max, timed=item.timed,
                rest_seconds=item.rest_seconds,
            ))
        plan.days.append(plan_day)
    session.add(plan)
    await session.commit()
    logger.info("Plan generated (%s, %s days)", spec.split, len(spec.days))
    # Reload so plan.days[...].exercises[...].exercise are all populated.
    session.expunge(plan)
    return await get_plan(session, user)


async def get_or_create_plan(session: AsyncSession, user: User) -> WorkoutPlan | None:
    return await get_plan(session, user) or await generate_for_user(session, user)


async def get_plan_exercise(session: AsyncSession, user: User,
                            plan_exercise_id: int) -> PlanExercise | None:
    """A plan entry, only if it belongs to this user's current plan."""
    return await session.scalar(
        select(PlanExercise)
        .join(PlanDay, PlanExercise.day_id == PlanDay.id)
        .join(WorkoutPlan, PlanDay.plan_id == WorkoutPlan.id)
        .where(PlanExercise.id == plan_exercise_id, WorkoutPlan.user_id == user.id)
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
    await session.commit()
    logger.info("Plan exercise substituted")
    return entry
